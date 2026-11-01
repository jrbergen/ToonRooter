"""Explicitly authorized boot backend shared by UART and JTAG methods.

Uses real OpenOCD commands, not the simulator's synthetic acknowledgements.
Authorization is supplied by a future reviewed hardware session, never by diagnostics.
"""
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from toonrooter.assets import validate_inventory
from toonrooter.boot.compatibility import analyze_bootloader
from toonrooter.boot.profiles import R8_ENVIRONMENT
from toonrooter.boot.uboot import UBootSession, prompt
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
    change_boot_arguments: bool = False


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

    def login(self, authorization: BootAuthorization, *, timeout=90.0, observed_version=None):
        if not authorization.uart_commands:
            raise PermissionError("Interactive UART approval required")
        found = observed_version or self.session.read_version(timeout=timeout)
        self.session.authenticate(found, timeout=timeout)
        self.uboot_version = found
        return found

    def linux_shell(self, authorization: BootAuthorization, *, reviewed_environment: bytes | None = None,
                    timeout=90.0):
        """Require the verified R8 profile or a previously reviewed full environment.

        run boot_nand invokes target-defined macros; a prompt/version alone cannot
        authorize their effects. No generic command API is exposed.
        """
        if not (authorization.uart_commands and authorization.change_boot_arguments
                and authorization.boot_linux_shell):
            raise PermissionError("UART, boot-argument and Linux shell boot approvals required")
        finite_timeout(timeout)
        environment = self.session.environment(timeout=10)
        actual = environment_values(environment)
        if reviewed_environment is None:
            if (getattr(self, "uboot_version", None) != "2010.09-R8"
                    or any(actual.get(k) != v for k, v in R8_ENVIRONMENT.items())):
                raise TransportError("Environment does not match verified R8 profile; "
                                     "supply a separately reviewed environment snapshot")
        elif actual != environment_values(reviewed_environment):
            raise TransportError("Environment differs from separately reviewed boot macros")
        validate_boot_environment(actual)
        original = actual.get(b"addmisc", b"")
        if not actual.get(b"boot_nand") or not original.startswith(b"setenv bootargs "):
            raise TransportError("Missing or nonmatching boot environment")
        if b"init=" in original:
            raise TransportError("Environment already overrides init; review required")
        # Only preserve literal macro text; backslash each U-Boot metacharacter.
        # R8 hardware confirmed escaped dollar AND braces. Never expand ${...} now.
        if not re.fullmatch(rb"[A-Za-z0-9_ /.,:=+{}$;-]+", original):
            raise TransportError("Unsupported addmisc syntax")
        value = original + b" init=/bin/sh"
        command = b"setenv addmisc " + re.sub(rb"([$;{}])", rb"\\\1", value)
        boot = b"run boot_nand"
        self.transport.write(command + b"\n")
        response = self.session.wait_prompt(timeout=10)
        if response.replace(b"\r", b"").rstrip(b" ") != command + b"\nU-Boot>":
            raise TransportError("Unexpected setenv response")
        changed = environment_values(self.session.environment(timeout=10))
        expected = {**actual, b"addmisc": value}
        if changed != expected:
            raise TransportError("Volatile environment update not verified")
        self.transport.write(boot + b"\n")
        self.session.ready = False
        self._shell_prompt(timeout=timeout)

    def _shell_prompt(self, *, timeout):
        deadline = self.transport.clock() + finite_timeout(timeout)
        data = bytearray()
        while len(data) < 65536:
            chunk = self.transport.read(1, deadline)
            data.extend(chunk)
            if not chunk and re.search(rb"(?:^|\n)/ # ?$", data):
                return bytes(data)
        raise CaptureLimit("Linux console response limit exceeded")

    def verify_root(self, *, timeout=10):
        self.transport.write(b"id; printf '\\nTR:ID:%s\\n' \"$?\"\n")
        data = self._shell_prompt(timeout=timeout)
        if (re.findall(rb"^TR:ID:([0-9]+)\r?$", data, re.MULTILINE) != [b"0"]
                or not re.search(rb"^uid=0\(root\)(?: |\r?$)", data, re.MULTILINE)):
            raise TransportError("Root identity not verified; no permanent installation performed")

    def ensure_proc(self, *, timeout=10):
        self.transport.write(
            b"if [ ! -r /proc/self/stat ]; then mount -t proc proc /proc; fi; "
            b"test -r /proc/self/stat; printf '\\nTR:PROC:%s\\n' \"$?\"\n")
        data = self._shell_prompt(timeout=timeout)
        if re.findall(rb"^TR:PROC:([0-9]+)\r?$", data, re.MULTILINE) != [b"0"]:
            raise TransportError("proc filesystem unavailable; temporary shell requires inspection")


def environment_values(data):
    """Canonical key/value comparison; tolerate CRLF, order and prompt spacing.

    A file can contain plain name=value lines or a complete printenv response.
    Reject duplicate variables and unexpected lines without exposing their contents.
    """
    result = {}
    for line in data.replace(b"\r", b"").split(b"\n"):
        if not line or line.strip() == b"printenv" or prompt(line):
            continue
        if re.fullmatch(rb"Environment size: [0-9]+/[0-9]+ bytes", line):
            continue
        match = re.fullmatch(rb"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if not match or match[1] in result:
            raise TransportError("Malformed or duplicate boot environment variable")
        result[match[1]] = match[2]
    return result


def validate_boot_environment(values):
    """Review boundary for the temporary boot path: no persistent commands.

    The reviewed snapshot binds actual values. Recursively inspect all run macros;
    unknown commands, dynamic run targets and loops require their own implementation.
    """
    seen = set()
    active = set()
    def visit(name):
        if len(active) >= 32 or name in active or name not in values:
            raise TransportError("Missing or recursive boot macro")
        if name in seen:
            return
        active.add(name)
        if not re.fullmatch(rb"[A-Za-z0-9_ /.,:=+{}$;@()-]+", values[name]):
            raise TransportError("Unsupported boot macro syntax")
        for command in values[name].split(b";"):
            words = command.split()
            if not words:
                continue
            if words[0] == b"run" and len(words) > 1:
                for child in words[1:]:
                    if not re.fullmatch(rb"[A-Za-z_][A-Za-z0-9_]*", child):
                        raise TransportError("Dynamic boot macro requires review")
                    visit(child)
            elif ((words[:2] == [b"setenv", b"bootargs"] and len(words) > 2)
                  or (len(words) >= 4 and words[0] == b"nand"
                      and words[1] in {b"read", b"read.jffs2", b"read.e"})
                  or (words[0] == b"bootm" and len(words) > 1)):
                pass
            else:
                raise TransportError("Unsupported boot macro command; no boot changes performed")
        active.remove(name)
        seen.add(name)
    visit(b"boot_nand")
    if b"addmisc" not in seen:
        raise TransportError("boot_nand does not invoke addmisc")


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
