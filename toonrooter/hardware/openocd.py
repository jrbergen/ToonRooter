"""Fixed host-only queries and an internal bounded process runner."""
import os
import selectors
import shutil
import signal
import subprocess
import time
from enum import Enum

from .serial import finite_timeout


class OpenOCDError(RuntimeError):
    pass


class Query(Enum):
    VERSION = ("--version",)
    ADAPTERS = ("-c", ("noinit; echo TOON_ADAPTERS_BEGIN; echo [adapter list]; "
                "echo TOON_ADAPTERS_END; shutdown"))


class OpenOCD:
    def __init__(self, executable=None, *, spawn=subprocess.Popen, clock=time.monotonic):
        self.executable = executable or shutil.which("openocd")
        if not self.executable or not os.path.isabs(self.executable):
            raise OpenOCDError("OpenOCD executable must resolve to an absolute path")
        self.spawn, self.clock = spawn, clock

    def query(self, query: Query, *, timeout=5.0, limit=65536) -> bytes:
        if not isinstance(query, Query):
            raise OpenOCDError("Only fixed host queries are allowed; target scripts disabled")
        return self._run(query.value, timeout=timeout, limit=limit)

    def _run(self, arguments, *, timeout=5.0, limit=65536, cwd="/"):
        """Internal bounded process runner; callers must construct fixed operations."""
        finite_timeout(timeout)
        if not 0 < limit <= 1048576:
            raise ValueError("Invalid log limit")
        proc = self.spawn([self.executable, *arguments], stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          start_new_session=True, cwd=cwd, env={"PATH": "/usr/bin:/bin"})
        output = bytearray()
        try:
            deadline = self.clock() + timeout
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - self.clock()
                    if remaining <= 0:
                        raise OpenOCDError("OpenOCD query timed out")
                    if not selector.select(min(remaining, 0.1)):
                        continue
                    chunk = os.read(proc.stdout.fileno(), min(4096, limit + 1 - len(output)))
                    if not chunk:
                        break
                    output.extend(chunk)
                    if len(output) > limit:
                        raise OpenOCDError("OpenOCD log limit exceeded")
            try:
                code = proc.wait(timeout=max(0.001, deadline - self.clock()))
            except subprocess.TimeoutExpired as exc:
                raise OpenOCDError("OpenOCD did not exit before deadline") from exc
            if code:
                raise OpenOCDError(f"OpenOCD process failed (exit {code}); no automatic retry")
            return bytes(output)
        finally:
            # Kill the whole session even if the leader exited but children kept pipes.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            proc.stdout.close()


def require_safe_jtag() -> None:
    raise OpenOCDError(
        "Live JTAG identification disabled: nested target scripts and reset handlers "
        "are not validated as non-halting/non-resetting. No target process started."
    )


def parse_adapters(output: str) -> tuple[str, ...]:
    """Parse only the explicitly delimited Tcl result, never startup banners."""
    import re
    lines = output.replace("\r", "").splitlines()
    if lines.count("TOON_ADAPTERS_BEGIN") != 1 or lines.count("TOON_ADAPTERS_END") != 1:
        raise OpenOCDError("Missing or repeated adapter-list delimiters")
    start, end = lines.index("TOON_ADAPTERS_BEGIN"), lines.index("TOON_ADAPTERS_END")
    if end != start + 2 or not re.fullmatch(r"[a-zA-Z0-9_ \t]+", lines[start + 1]):
        raise OpenOCDError("Unexpected adapter-list result")
    result = tuple(lines[start + 1].split())
    if not result or len(set(result)) != len(result):
        raise OpenOCDError("Invalid compiled adapter list")
    return result
