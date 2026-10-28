"""Operation classifications. Unsupported state-changing operations fail closed."""
from enum import IntEnum


class Level(IntEnum):
    HOST = 0
    PASSIVE_UART = 1
    JTAG_IDENTIFICATION = 2
    DISRUPTIVE = 3


def authorize(level: Level, *, confirmed=False, compatible=False) -> None:
    if level == Level.JTAG_IDENTIFICATION:
        raise PermissionError("No audited conservative JTAG sequence is available")
    if level == Level.DISRUPTIVE:
        if not confirmed or not compatible:
            raise PermissionError("Requires explicit confirmation and verified compatibility")
        raise PermissionError("Disruptive operations are not enabled in this milestone")


class OperationKind(IntEnum):
    HOST_ONLY = 0
    TARGET_OBSERVATION = 1
    TARGET_VOLATILE = 2
    TARGET_PERSISTENT = 3
