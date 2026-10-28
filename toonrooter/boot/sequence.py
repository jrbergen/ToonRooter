"""Evidence-checked simulation of the legacy boot plan. No live backend exists."""
import re
from dataclasses import dataclass
from enum import Enum, auto

from toonrooter.assets import audit_configs, validate_inventory
from toonrooter.boot.uboot import prompt, version
from toonrooter.hardware.serial import TransportError, finite_timeout
from toonrooter.safety import OperationKind as Kind


class State(Enum):
    DISCONNECTED = auto()
    HOST_VALIDATED = auto()
    TARGET_IDENTIFIED = auto()
    JTAG_INITIALIZED = auto()
    BOOTLOADER_LOADED_IN_RAM = auto()
    SERIAL_CONSOLE_READY = auto()
    BOOT_ENVIRONMENT_INSPECTED = auto()
    LINUX_CONSOLE_READY = auto()
    FAILED = auto()


@dataclass(frozen=True)
class Step:
    before: State
    after: State
    command: bytes
    kind: Kind
    expected: bytes
    timeout: float = 10.0


# Expected strings are simulator contract evidence, NOT guaranteed OpenOCD responses.
STEPS = (
    Step(State.HOST_VALIDATED, State.TARGET_IDENTIFIED, b"identify",
         Kind.TARGET_VOLATILE, b"SIM:toon1-imx27"),
    Step(State.TARGET_IDENTIFIED, State.JTAG_INITIALIZED,
         b"soft_reset_halt\nreset halt\n", Kind.TARGET_VOLATILE, b"SIM:halted"),
    Step(State.JTAG_INITIALIZED, State.BOOTLOADER_LOADED_IN_RAM,
         b"load_image assets/u-boot.bin 0xa1f00000\n",
         Kind.TARGET_VOLATILE, b"SIM:loaded:166504:0xa1f00000"),
    Step(State.BOOTLOADER_LOADED_IN_RAM, State.SERIAL_CONSOLE_READY,
         b"resume 0xa1f00000\n", Kind.TARGET_VOLATILE, b""),
    Step(State.SERIAL_CONSOLE_READY, State.BOOT_ENVIRONMENT_INSPECTED,
         b"printenv\n", Kind.TARGET_VOLATILE, b""),
    Step(State.BOOT_ENVIRONMENT_INSPECTED, State.LINUX_CONSOLE_READY,
         b"SIM:build-boot-commands-from-inspected-environment", Kind.TARGET_VOLATILE, b"\r\n/ # "),
)


class SimulatedBootEndpoint:
    """Deterministic fixture; never opens serial, sockets or subprocesses."""
    def __init__(self, responses):
        self.responses = iter(responses)
        self.commands = []
        self.closed = False

    def exchange(self, command, *, timeout):
        finite_timeout(timeout)
        self.commands.append(command)
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self):
        self.closed = True


class BootSequence:
    def __init__(self, endpoint: SimulatedBootEndpoint):
        if type(endpoint) is not SimulatedBootEndpoint:
            raise PermissionError("Only simulation is supported; live boot path unreviewed")
        self.endpoint = endpoint
        self.state = State.DISCONNECTED
        self.evidence = "SIMULATED — NOT HARDWARE VALIDATION"
        self.history = []
        self.addmisc = None

    def validate_host(self, root):
        if self.state != State.DISCONNECTED:
            raise TransportError("Invalid initial state")
        validate_inventory(root, operation="simulate")
        audit_configs(root)  # Never upgrades live permission.
        self.state = State.HOST_VALIDATED

    def advance(self):
        step = next((s for s in STEPS if s.before == self.state), None)
        if step is None:
            raise TransportError("No transition permitted")
        try:
            command = step.command
            if step.after == State.LINUX_CONSOLE_READY:
                command = shell_boot_commands(self.addmisc)
            response = self.endpoint.exchange(command, timeout=step.timeout)
            if not isinstance(response, bytes) or len(response) > 65536:
                raise TransportError("Invalid boot response")
            if step.after == State.SERIAL_CONSOLE_READY:
                if version(response) not in {"2010.09", "2010.09-R6", "2010.09-R8"}:
                    raise TransportError("Unsupported bootloader version")
                valid = prompt(response)
            elif step.after == State.BOOT_ENVIRONMENT_INSPECTED:
                lines = response.replace(b"\r", b"").split(b"\n")
                valid = lines[0] == b"printenv" and sum(
                    line.startswith(b"addmisc=") and len(line) > 8 for line in lines
                ) == 1 and prompt(response)
            else:
                valid = response == step.expected
            if not valid:
                raise TransportError("Boot transition evidence mismatch")
            if step.after == State.BOOT_ENVIRONMENT_INSPECTED:
                self.addmisc = next(line[8:] for line in lines if line.startswith(b"addmisc="))
            self.state = step.after
            self.history.append((self.state.name, step.kind.name, len(response)))
        except BaseException:
            self.state = State.FAILED
            self.endpoint.close()
            raise
        if self.state == State.LINUX_CONSOLE_READY:
            self.endpoint.close()


def shell_boot_commands(addmisc: bytes) -> bytes:
    """Conservative legacy command construction; simulation only, no saveenv."""
    if (not isinstance(addmisc, bytes) or not 0 < len(addmisc) <= 4096
            or not re.fullmatch(rb"[A-Za-z0-9_ /.,:=+{}$;-]+", addmisc)):
        raise ValueError("Unsupported addmisc content")
    value = addmisc + b" init=/bin/sh"
    return (b"setenv addmisc " + value.replace(b"$", b"\\$").replace(b";", b"\\;")
            + b"\nrun boot_nand\n")
