"""Opt-in library backend. No CLI entry point and no persistent installer.

Uses real OpenOCD commands, not the simulator's synthetic acknowledgements.
Authorization is supplied by a future reviewed hardware session, never by diagnostics.
"""
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from toonrooter.assets import validate_inventory
from toonrooter.boot.compatibility import SUPPORTED_VERSIONS, analyze_bootloader
from toonrooter.boot.sequence import shell_boot_commands
from toonrooter.boot.uboot import UBootSession, version
from toonrooter.deployment import openocd_profile
from toonrooter.hardware.config_review import review_chain
from toonrooter.hardware.openocd import OpenOCD, OpenOCDError, Query, parse_adapters
from toonrooter.hardware.serial import CaptureLimit, SerialTransport, TransportError, finite_timeout


@dataclass(frozen=True)
class BootAuthorization:
    uart_commands: bool = False
    reset_registers_ram: bool = False
    execute_reviewed_image: bool = False
    boot_linux_shell: bool = False


# No caller-controlled Tcl, addresses, adapter configuration or target IDs.
# reset init deliberately invokes the reviewed SDRAM/clock handler: reset halt
# alone does not run reset-init, despite the legacy Python sequence assuming it.
BOOTSTRAP = """
gdb_port disabled
tcl_port disabled
telnet_port disabled
if {[catch {
    source adapter.cfg
    transport select jtag
    source board.cfg
    init
    if {[jtag cget imx27.cpu -idcode] != 0x07926121} {error "Wrong CPU TAP"}
    if {[jtag cget imx27.etb -idcode] != 0x1b900f0f} {error "Wrong ETB TAP"}
    echo TOON_BOOT:identified
    soft_reset_halt
    sleep 100
    reset init
    if {[imx27.cpu curstate] ne "halted"} {error "CPU not halted"}
    echo TOON_BOOT:initialized
    load_image boot.bin 0xa1f00000 bin
    verify_image boot.bin 0xa1f00000 bin
    echo TOON_BOOT:verified
    resume 0xa1f00000
    echo TOON_BOOT:resumed
}]} {
    echo TOON_BOOT:failed
    shutdown error
} else {
    shutdown
}
"""


class Pi3JtagBoot:
    def __init__(self, repository: Path, *, client=None):
        self.repository = repository
        self.client = client

    def start(self, authorization: BootAuthorization, *, model: str, timeout=60.0):
        """Reset/initialize/load/verify/resume. Interruptions stop host I/O, not target effects."""
        if not (authorization.reset_registers_ram and authorization.execute_reviewed_image):
            raise PermissionError("Separate reset/RAM and reviewed-image execution approval required")
        if model.rstrip("\x00\n") != "Raspberry Pi 3 Model B Rev 1.2":
            raise ValueError("Only the reviewed Pi 3 Model B Rev 1.2 profile is supported")
        finite_timeout(timeout)
        inventory = validate_inventory(self.repository)
        image = analyze_bootloader(self.repository)
        if not image["soc_evidence"] or not image["version_evidence"]:
            raise ValueError("Incompatible bootloader")
        review_chain()
        client = self.client or OpenOCD()
        adapters = parse_adapters(client.query(Query.ADAPTERS).decode("ascii", "strict"))
        state, detail = openocd_profile(client.query(Query.VERSION).decode("ascii", "strict"),
                                       " ".join(adapters), "bcm2835gpio")
        if state != "PASS":
            raise OpenOCDError(detail)
        with TemporaryDirectory(prefix="toonrooter-boot-") as directory:
            root = Path(directory)
            (root / "target").mkdir()
            (root / "target/imx27.cfg").write_bytes(files("toonrooter").joinpath(
                "data/openocd-0.12.0/target/imx27.cfg").read_bytes())
            # Fixed relative files prevent Tcl interpolation of user paths and mutation
            # of repository assets after validation. No system target script is used.
            (root / "adapter.cfg").write_bytes(inventory["assets/adapters/rpi3.cfg"])
            (root / "board.cfg").write_bytes(inventory["assets/boards/ed20.cfg"])
            (root / "boot.bin").write_bytes(inventory["assets/u-boot.bin"])
            (root / "boot.cfg").write_text(BOOTSTRAP)
            output = client._run(("-s", directory, "-f", "boot.cfg"),
                                 cwd=directory, timeout=timeout, limit=65536)
        stages = re.findall(rb"^TOON_BOOT:([^\r\n]+)\r?$", output, re.MULTILINE)
        if stages != [b"identified", b"initialized", b"verified", b"resumed"]:
            raise OpenOCDError("Incomplete or unexpected JTAG bootstrap evidence; target state unknown")
        return tuple(stage.decode() for stage in stages)


class BootConsole:
    """Explicit interactive console. Never writes saveenv, NAND or filesystems."""
    def __init__(self, transport):
        self.transport = transport
        self.session = UBootSession(transport)

    def login(self, authorization: BootAuthorization, *, timeout=15.0):
        if not authorization.uart_commands:
            raise PermissionError("Interactive UART approval required")
        deadline = self.transport.clock() + finite_timeout(timeout)
        line = bytearray()
        for _ in range(65536):
            chunk = self.transport.read(1, deadline)
            line.extend(chunk)
            if chunk == b"\n":
                found = version(bytes(line))
                if found:
                    if found not in SUPPORTED_VERSIONS:
                        raise TransportError("Unsupported U-Boot version")
                    # Historical password window: transmit immediately after banner.
                    password = {"2010.09": b"toon", "2010.09-R6": b"f4E9J",
                                "2010.09-R8": b"3BHf2"}[found]
                    self.transport.write(password, timeout=max(.001, deadline-self.transport.clock()))
                    self.session.wait_prompt(timeout=max(.001, deadline-self.transport.clock()))
                    return found
                line.clear()
        raise CaptureLimit("U-Boot banner limit exceeded")

    def linux_shell(self, authorization: BootAuthorization, *, reviewed_environment: bytes,
                    timeout=90.0):
        """Require exact, previously reviewed environment, including all boot macros.

        run boot_nand invokes target-defined macros; a prompt/version alone cannot
        authorize their effects. No generic command API is exposed.
        """
        if not (authorization.uart_commands and authorization.boot_linux_shell):
            raise PermissionError("UART and Linux shell boot approval required")
        finite_timeout(timeout)
        environment = self.session.environment(timeout=10)
        if environment != reviewed_environment:
            raise TransportError("Environment differs from separately reviewed boot macros")
        values = re.findall(rb"^addmisc=([^\r\n]+)\r?$", environment, re.MULTILINE)
        if len(values) != 1 or not re.search(rb"^boot_nand=.+", environment, re.MULTILINE):
            raise TransportError("Missing or ambiguous boot environment")
        command, boot, _ = shell_boot_commands(values[0]).split(b"\n")
        self.transport.write(command + b"\n")
        response = self.session.wait_prompt(timeout=10)
        if response.replace(b"\r", b"").rstrip(b" ") != command + b"\nU-Boot>":
            raise TransportError("Unexpected setenv response")
        # Read back the environment before executing any boot macro.
        changed = self.session.environment(timeout=10)
        expected = environment.replace(b"addmisc=" + values[0],
                                       b"addmisc=" + values[0] + b" init=/bin/sh", 1)
        if changed != expected:
            raise TransportError("Volatile environment update not verified")
        self.transport.write(boot + b"\n")
        self.session.ready = False
        deadline = self.transport.clock() + timeout
        data = bytearray()
        while len(data) < 65536:
            chunk = self.transport.read(1, deadline)
            data.extend(chunk)
            if not chunk and re.search(rb"(?:^|\n)/ # $", data):
                return  # Console evidence only; not installed/rooted/SSH verified.
        raise CaptureLimit("Linux console response limit exceeded")


def boot_to_console(repository, serial_path, authorization, *, model, jtag=False,
                    reviewed_environment=None, serial_factory=None, jtag_backend=None):
    """Open UART before resuming U-Boot; retain its early output; always close it.

    jtag=False prefers existing startup/console; no automatic fallback or retry.
    Omitting reviewed_environment stops at U-Boot without booting Linux.
    """
    if not authorization.uart_commands:
        raise PermissionError("Interactive UART approval required")
    if jtag and not (authorization.reset_registers_ram and authorization.execute_reviewed_image):
        raise PermissionError("JTAG reset/RAM and image execution approval required")
    with SerialTransport.open(serial_path, transmit=True, factory=serial_factory) as transport:
        if jtag:
            (jtag_backend or Pi3JtagBoot(repository)).start(authorization, model=model)
        console = BootConsole(transport)
        found = console.login(authorization)
        if reviewed_environment is not None:
            console.linux_shell(authorization, reviewed_environment=reviewed_environment)
        return {"uboot_version": found, "linux_console": reviewed_environment is not None,
                "hardware_validated": False, "installation_performed": False}
