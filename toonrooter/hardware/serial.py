"""Bounded byte transport. Receive-only is a software policy, not electrical isolation."""
import math
import time
from pathlib import Path


class TransportError(RuntimeError):
    pass


class DeadlineExceeded(TransportError):
    pass


class CaptureLimit(TransportError):
    pass


def finite_timeout(value: float) -> float:
    if not math.isfinite(value) or not 0 < value <= 3600:
        raise ValueError("Timeout must be finite and between 0 and 3600 seconds")
    return value


class SerialTransport:
    def __init__(self, device, *, transmit=False, clock=time.monotonic):
        self.device = device
        self.transmit = transmit
        self.clock = clock

    @classmethod
    def open(cls, path: str, *, baudrate=115200, transmit=False, factory=None):
        if not Path(path).is_absolute() or baudrate not in (115200,):
            raise ValueError("Require absolute device path and documented baud rate 115200")
        if factory is None:
            import serial
            factory = serial.Serial
        # Construct closed: set inactive modem lines BEFORE opening.
        device = factory(port=None, baudrate=baudrate, timeout=0.1, write_timeout=0.1,
                         xonxoff=False, rtscts=False, dsrdtr=False, exclusive=True)
        try:
            device.dtr = False
            device.rts = False
            device.port = path
            device.open()
        except BaseException:
            device.close()
            raise
        return cls(device, transmit=transmit)

    def read(self, size: int, deadline: float) -> bytes:
        if not 0 < size <= 1048576:
            raise ValueError("Read size must be between 1 and 1048576")
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise DeadlineExceeded("Serial deadline exceeded")
        self.device.timeout = min(0.1, remaining)
        try:
            return self.device.read(size)
        except OSError as exc:
            raise TransportError("Serial disconnected or unavailable") from exc

    def write(self, data: bytes, *, timeout=5.0) -> None:
        if not self.transmit:
            raise PermissionError("Receive-only transport rejects transmission")
        if not isinstance(data, bytes):
            raise TypeError("Serial writes require bytes")
        if len(data) > 1048576:
            raise ValueError("Write buffer exceeds 1 MiB")
        deadline = self.clock() + finite_timeout(timeout)
        offset = 0
        while offset < len(data):
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise DeadlineExceeded("Serial write deadline exceeded")
            self.device.write_timeout = min(0.1, remaining)
            try:
                count = self.device.write(data[offset:])
            except OSError as exc:
                raise TransportError("Serial write failed; transfer incomplete") from exc
            if not count:
                raise TransportError("Serial write made no progress")
            offset += count

    def collect(self, *, timeout=30.0, limit=65536, on_chunk=None) -> tuple[bytes, str]:
        if not 0 < limit <= 1048576:
            raise ValueError("Capture limit must be between 1 and 1048576 bytes")
        deadline = self.clock() + finite_timeout(timeout)
        result = bytearray()
        while len(result) < limit:
            try:
                chunk = self.read(min(1024, limit - len(result)), deadline)
            except DeadlineExceeded:
                return bytes(result), "timeout"
            if chunk:
                result.extend(chunk)
                if on_chunk:
                    on_chunk(chunk)
        return bytes(result), "capture-limit"

    def close(self):
        self.device.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
