"""Native UART method selection and temporary-root orchestration.

The actual environment must match the verified R8 profile or a reviewed snapshot. Persistent
installation remains a distinct, unimplemented operation.
"""
from dataclasses import asdict, dataclass
from pathlib import Path

from toonrooter.boot.live import (
    BootAuthorization,
    BootConsole,
    Pi3JtagBoot,
    environment_values,
    validate_boot_environment,
)
from toonrooter.boot.uboot import PASSWORDS
from toonrooter.hardware.serial import SerialTransport, TransportError, finite_timeout


class JtagAvailable(TransportError):
    """Advice only. Raising this never starts OpenOCD."""


def select_method(method, observed_version, *, jtag_supported=False):
    if method not in {"auto", "uart", "jtag"}:
        raise ValueError("Unknown rooting method")
    if method == "jtag":
        if not jtag_supported:
            raise TransportError("JTAG requires the supported Pi3 profile and repository")
        return "jtag"
    if PASSWORDS.get(observed_version):
        return "uart"
    if method == "auto" and jtag_supported:
        raise JtagAvailable("No known UART password for this version. JTAG is available: "
                            "select --method jtag with separate reset/RAM and image approvals. "
                            "No JTAG fallback was executed.")
    raise TransportError("No known UART password for this version; no boot changes performed")


@dataclass(frozen=True)
class TemporaryRootResult:
    method: str
    uboot_version: str
    password_evidence: str
    temporary_root: bool = True
    proc_available: bool = True
    permanent_root: bool = False
    installation_performed: bool = False
    ssh_verified: bool = False


def temporary_root(serial_path, authorization: BootAuthorization, *, method="auto",
                   reviewed_environment: bytes | None = None, repository: Path | None = None,
                   model="", timeout=90.0, serial_factory=None, jtag_backend=None,
                   on_open=None):
    """Open UART before power-on/resume, no automatic JTAG retry after any failure."""
    finite_timeout(timeout)
    if not (authorization.uart_commands and authorization.change_boot_arguments
            and authorization.boot_linux_shell):
        raise PermissionError("UART, temporary boot-argument and modified-boot approvals required")
    if reviewed_environment is not None:
        validate_boot_environment(environment_values(reviewed_environment))
    supported = (model == "Raspberry Pi 3 Model B Rev 1.2" and repository is not None)
    if method == "jtag":
        select_method(method, None, jtag_supported=supported)
        if not (authorization.reset_registers_ram and authorization.execute_reviewed_image):
            raise PermissionError("Separate JTAG reset/RAM and image-execution approvals required")
        if reviewed_environment is None:
            raise TransportError("JTAG root requires a reviewed RAM-image environment snapshot")
    elif method not in {"auto", "uart"}:
        raise ValueError("Unknown rooting method")
    with SerialTransport.open(serial_path, transmit=True, factory=serial_factory) as transport:
        if on_open:
            on_open()
        if method == "jtag":
            (jtag_backend or Pi3JtagBoot(repository)).start(authorization, model=model)
        console = BootConsole(transport)
        observed = console.session.read_version(timeout=timeout)
        selected = select_method(method, observed, jtag_supported=supported)
        console.login(authorization, observed_version=observed, timeout=15)
        console.linux_shell(authorization, reviewed_environment=reviewed_environment,
                            timeout=timeout)
        console.verify_root(timeout=10)
        console.ensure_proc(timeout=10)
        evidence = ("user-verified R8 on ED2.4 / qb2/uni/6.4.5-0" if observed == "2010.09-R8"
                    else "historically documented; unverified on our hardware")
        return asdict(TemporaryRootResult(selected, observed, evidence))
