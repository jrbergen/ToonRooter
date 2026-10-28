"""Source-derived orchestration exercised only through the in-memory fixture.

There is deliberately no production backend selection or live root CLI.
"""
import re
import secrets
from dataclasses import dataclass

from .assets import audit_configs, validate_inventory
from .boot.compatibility import SUPPORTED_VERSIONS, analyze_bootloader
from .boot.sequence import shell_boot_commands
from .boot.uboot import UBootSession, version
from .hardware.serial import SerialTransport, TransportError
from .legacy_wire import prepare_legacy_wire
from .payload import package

TRANSFER_STATUS = b'printf "\\nTR:TRANSFER:%s\\n" "$?"\n'
VERIFY = (b"test -s /root/.ssh/authorized_keys && test -x /usr/sbin/dropbear "
          b"&& test -x /usr/libexec/sftp-server; "
          b'printf "\\nTR:VERIFY:%s\\n" "$?"\n')


@dataclass(frozen=True)
class Result:
    evidence: str
    phases: tuple[str, ...]
    transfer_integrity: str
    ssh_verified: bool


class RootSimulation:
    def __init__(self, rig):
        from .testing.rooting import SimulatedRig
        if type(rig) is not SimulatedRig:
            raise PermissionError("Only the in-memory simulated rig is enabled")
        self.rig = rig
        self.phases = []
        self.used = False

    def _phase(self, name):
        self.phases.append(name)  # No command arguments, credentials or environment output.

    def _prompt(self, port, expected=b"/ # ", *, timeout=30):
        deadline = port.clock() + timeout
        data = bytearray()
        while len(data) < 65536:
            chunk = port.read(1, deadline)
            if chunk:
                data.extend(chunk)
            elif re.search(rb"(?:^|\n)" + re.escape(expected) + rb"$", data):
                return bytes(data)
        raise TransportError("Response limit exceeded")

    def _banner(self, port, *, timeout=30):
        # Legacy read_uboot_version waits for the version line, then sends the
        # password immediately; do not invent an extra password-prompt wait.
        deadline = port.clock() + timeout
        data = bytearray()
        while len(data) < 65536:
            chunk = port.read(1, deadline)
            data.extend(chunk)
            if chunk == b"\n" and version(bytes(data)) is not None:
                return bytes(data)
        raise TransportError("Boot banner limit exceeded")

    def _status(self, port, label, timeout=30):
        data = self._prompt(port, timeout=timeout)
        found = re.findall(rb"(?:^|\n)TR:" + label + rb":([0-9]+)\r?\n", data)
        if found != [b"0"]:
            raise TransportError("Shell phase status not successful")

    def run(self, root, key, *, authorize_install=False, authorize_reboot=False):
        if self.used:
            raise TransportError("No automatic or repeated rooting attempts")
        self.used = True
        rig = self.rig
        try:
            validate_inventory(root)
            audit_configs(root)
            image = analyze_bootloader(root)
            wire = prepare_legacy_wire(package(root, key))
            if rig.hardware != "toon1-imx27" or rig.openocd_version != "0.12.0":
                raise TransportError("Unsupported simulation hardware/OpenOCD profile")
            self._phase("host-validated")
            with SerialTransport(rig.serial, transmit=True,
                                 clock=lambda: rig.serial.now) as port:
                banner = self._banner(port, timeout=30)
                observed = version(banner)
                if observed not in SUPPORTED_VERSIONS:
                    self._phase("openocd-start")
                    ids = rig.start_openocd()
                    if ids != (0x07926121, 0x1b900f0f):
                        raise TransportError("Unexpected JTAG TAP IDs")
                    self._phase("target-identified")
                    for command in (b"soft_reset_halt", b"reset halt"):
                        if rig.jtag(command) != b"target halted":
                            raise TransportError("Target halt failed")
                    if rig.jtag(b"load_image assets/u-boot.bin 0xa1f00000") != (
                        f"downloaded {image['size']} bytes".encode()
                    ):
                        raise TransportError("Bootloader load failed")
                    self._phase("bootloader-loaded")
                    rig.jtag(b"resume 0xa1f00000")
                    banner = self._banner(port, timeout=30)
                    observed = version(banner)
                if observed not in SUPPORTED_VERSIONS:
                    raise TransportError("Unexpected bootloader version")
                # Historical credentials, never included in phase logs.
                password = {"2010.09": b"toon", "2010.09-R6": b"f4E9J",
                            "2010.09-R8": b"3BHf2"}[observed]
                port.write(password)
                uboot = UBootSession(port)
                uboot.wait_prompt(timeout=10)
                self._phase("uboot-console")
                env = uboot.environment(timeout=10)
                values = re.findall(rb"(?:^|\n)addmisc=([^\r\n]+)", env)
                if len(values) != 1:
                    raise TransportError("Ambiguous addmisc")
                commands = shell_boot_commands(values[0]).splitlines(keepends=True)
                port.write(commands[0])
                uboot.wait_prompt(timeout=10)
                # Prompt indicates synchronization, not verified environment persistence.
                port.write(commands[1])
                self._prompt(port, timeout=60)
                self._phase("linux-console")
                port.write(wire.receiver_command)
                deadline = port.clock() + 60
                for offset in range(0, len(wire.encoded), 1024):
                    remaining = deadline - port.clock()
                    if remaining <= 0:
                        raise TransportError("Transfer timed out")
                    port.write(wire.encoded[offset:offset + 1024], timeout=remaining)
                port.write(b"\x04\n")
                self._prompt(port, timeout=65)
                port.write(TRANSFER_STATUS)
                self._status(port, b"TRANSFER")
                self._phase("payload-transferred")
                if not authorize_install:
                    raise PermissionError("Simulation installation authorization required")
                self._phase("installation-authorized")
                password = secrets.token_hex(12).encode()
                port.write(b'sh payload/patch_toon.sh "' + password +
                           b'"; printf "\\nTR:INSTALL:%s\\n" "$?"\n')
                self._status(port, b"INSTALL", timeout=120)
                self._phase("payload-executed")
                port.write(VERIFY)
                self._status(port, b"VERIFY")
                self._phase("installation-checked")
                if not authorize_reboot:
                    raise PermissionError("Simulation reboot authorization required")
                port.write(b"/etc/init.d/reboot\n")
                if not rig.verify_boot_and_ssh(timeout=120):
                    raise TransportError("Normal boot/SSH verification failed")
                self._phase("boot-and-ssh-checked")
            return Result("SIMULATED ONLY; not hardware validation", tuple(self.phases),
                          "legacy tar exit status only; no target checksum", True)
        finally:
            rig.close()
