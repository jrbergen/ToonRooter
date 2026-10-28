"""Byte parsing and narrowly allowlisted U-Boot observation, never bootstrapping."""
import re
from dataclasses import dataclass
from enum import Enum

from toonrooter.hardware.serial import CaptureLimit, TransportError, finite_timeout


class Effect(Enum):
    OBSERVATION = "observation"
    VOLATILE = "CPU/RAM modification"
    BOOT = "boot-affecting"
    ENVIRONMENT = "persistent environment"
    STORAGE = "flash/filesystem"


# Classification is evidence inventory, not an executable command allowlist.
LEGACY_EFFECTS = {
    "printenv": Effect.OBSERVATION, "load_image": Effect.VOLATILE,
    "setenv addmisc": Effect.BOOT, "run boot_nand": Effect.BOOT,
    "saveenv": Effect.ENVIRONMENT, "payload": Effect.STORAGE,
}


def version(data: bytes) -> str | None:
    match = re.search(rb"(?:^|\n)U-Boot ([A-Za-z0-9_.-]+)(?:[ \r\n])", data)
    return match[1].decode("ascii") if match else None


def prompt(data: bytes) -> bool:
    # Only a standalone final prompt, not a substring inside a line.
    return re.search(rb"(?:^|\n)U-Boot> ?$", data) is not None


@dataclass(frozen=True)
class Event:
    timestamp: float
    direction: str
    size: int


class UBootSession:
    def __init__(self, transport, *, limit=65536):
        if not 0 < limit <= 1048576:
            raise ValueError("Invalid response limit")
        self.transport, self.limit = transport, limit
        # Metadata only: environment output may contain credentials.
        self.transcript: list[Event] = []
        self.ready = False

    def _event(self, direction, size):
        if len(self.transcript) < 1024:
            self.transcript.append(Event(self.transport.clock(), direction, size))

    def wait_prompt(self, *, timeout=5.0) -> bytes:
        deadline = self.transport.clock() + finite_timeout(timeout)
        result = bytearray()
        self.ready = False
        while len(result) < self.limit:
            chunk = self.transport.read(1, deadline)
            if chunk:
                result.extend(chunk)
                self._event("rx", len(chunk))
            elif prompt(bytes(result)):
                # Require an idle read after a complete line-boundary candidate.
                # A prompt-like prefix followed immediately by output is not a prompt.
                self.ready = True
                return bytes(result)
        raise CaptureLimit("U-Boot response limit exceeded")

    def environment(self, *, timeout=5.0) -> bytes:
        """Explicit interactive operation, not a passive probe.

        Require prior prompt synchronization and echoed printenv plus addmisc evidence.
        A returned prompt alone does not establish successful command completion.
        """
        if not self.ready:
            raise TransportError("Synchronize with a known prompt first")
        self.ready = False
        self.transport.write(b"printenv\n", timeout=timeout)
        self._event("tx", len(b"printenv\n"))
        try:
            response = self.wait_prompt(timeout=timeout)
            if not re.search(rb"^ ?printenv\r?\n", response):
                raise TransportError("Missing command echo")
            if not re.search(rb"(?:^|\n)addmisc=[^\r\n]+", response):
                raise TransportError("Environment response not verified")
            return response
        except BaseException:
            self.ready = False
            raise
