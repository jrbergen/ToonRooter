"""Simulation-only framed transfer with an actual byte receiver.

This protocol requires a receiver absent from the Toon. It is not the legacy
base64-to-tar shell and must not be used against a device.
"""
from enum import Enum, auto

from .hardware.serial import SerialTransport, TransportError, finite_timeout
from .payload import LIMIT, digest, verify


class TransferState(Enum):
    PREPARED = auto()
    STARTED = auto()
    COMPLETED = auto()
    INTEGRITY_VERIFIED = auto()
    FAILED = auto()
    # Intentionally unreachable: no execution API.
    EXECUTION_AUTHORIZED = auto()
    EXECUTION_COMPLETED = auto()
    INSTALLATION_VERIFIED = auto()


class SimulatedReceiver:
    """Bounded in-memory receiver; no filesystem writes or extraction."""
    def __init__(self, *, corrupt=False, wrong_ack=False):
        self.buffer = bytearray()
        self.response = bytearray()
        self.expected = None
        self.closed = False
        self.now = 0.0
        self.corrupt, self.wrong_ack = corrupt, wrong_ack

    def write(self, data):
        self.now += 0.001
        data = data[:97]  # Exercise real partial-write loop.
        self.buffer.extend(data)
        if self.expected is None and b"\n" in self.buffer:
            header, rest = bytes(self.buffer).split(b"\n", 1)
            fields = header.split(b" ")
            if len(fields) != 3 or fields[0] != b"TRSIM1":
                raise OSError("Invalid simulation framing")
            size = int(fields[1])
            if not 0 < size <= LIMIT or len(fields[2]) != 64:
                raise OSError("Invalid simulation size/hash")
            self.expected = (size, fields[2])
            self.buffer = bytearray(rest)
        if len(self.buffer) > LIMIT + 128:
            raise OSError("Receiver bound exceeded")
        if self.expected and len(self.buffer) >= self.expected[0]:
            size, expected_hash = self.expected
            payload = bytes(self.buffer)
            if self.corrupt:
                payload = payload[:-1] + bytes([payload[-1] ^ 1])
            if len(payload) != size or digest(payload).encode() != expected_hash:
                self.response.extend(b"ERROR\n")
            else:
                verify(payload)
                self.response.extend(b"WRONG\n" if self.wrong_ack else
                                     b"VERIFIED " + str(size).encode() + b" " +
                                     digest(payload).encode() + b"\n")
        return len(data)

    def read(self, size):
        self.now += 0.01
        data = bytes(self.response[:size])
        del self.response[:size]
        return data

    def close(self):
        self.closed = True


class SimulatedTransfer:
    def __init__(self, receiver: SimulatedReceiver):
        if type(receiver) is not SimulatedReceiver:
            raise PermissionError("Only the in-memory simulation receiver is enabled")
        self.receiver = receiver
        self.state = TransferState.PREPARED
        self.evidence = "SIMULATED — NOT A TOON TRANSFER"

    def send(self, data: bytes, *, timeout=60.0):
        if self.state != TransferState.PREPARED:
            raise TransportError("Transfer cannot be retried after start")
        finite_timeout(timeout)
        verify(data)  # No receiver communication after failed package validation.
        deadline = self.receiver.now + timeout
        self.state = TransferState.STARTED
        try:
            with SerialTransport(self.receiver, transmit=True,
                                 clock=lambda: self.receiver.now) as port:
                header = f"TRSIM1 {len(data)} {digest(data)}\n".encode("ascii")
                for chunk in (header, *(data[i:i + 4096] for i in range(0, len(data), 4096))):
                    remaining = deadline - self.receiver.now
                    if remaining <= 0:
                        raise TransportError("Transfer deadline exceeded")
                    port.write(chunk, timeout=remaining)
                self.state = TransferState.COMPLETED
                response = bytearray()
                while len(response) < 128 and not response.endswith(b"\n"):
                    response.extend(port.read(1, deadline))
                expected = f"VERIFIED {len(data)} {digest(data)}\n".encode()
                if bytes(response) != expected:
                    raise TransportError("Receiver length/hash acknowledgement mismatch")
                self.state = TransferState.INTEGRITY_VERIFIED
        except BaseException:
            self.state = TransferState.FAILED
            raise
