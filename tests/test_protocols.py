from collections import deque

import pytest

from toonrooter.boot.uboot import UBootSession, prompt, version
from toonrooter.hardware.serial import (
    CaptureLimit,
    DeadlineExceeded,
    SerialTransport,
    TransportError,
)


class FakeSerial:
    def __init__(self, chunks=(), **kwargs):
        self.chunks = deque(chunks)
        self.sent = []
        self.closed = False
        self.settings = kwargs
        self.now = 0
        self.opened = False

    def open(self):
        assert self.dtr is False and self.rts is False
        assert self.settings["port"] is None
        assert not any(self.settings[k] for k in ("xonxoff", "rtscts", "dsrdtr"))
        self.opened = True

    def read(self, size):
        self.now += 0.1
        chunk = self.chunks.popleft() if self.chunks else b""
        if isinstance(chunk, BaseException):
            raise chunk
        self.chunks.appendleft(chunk[size:]) if len(chunk) > size else None
        return chunk[:size]

    def write(self, data):
        self.sent.append(data[:2])
        return min(2, len(data))

    def close(self):
        self.closed = True


def transport(chunks=(), transmit=False):
    device = FakeSerial(chunks)
    return SerialTransport(device, transmit=transmit, clock=lambda: device.now), device


def test_open_passive_settings():
    device = FakeSerial()
    with SerialTransport.open("/fake", factory=lambda **kw: (
        device.settings.update(kw) or device
    )) as port, pytest.raises(PermissionError):
        port.write(b"\n")
    assert device.closed and device.opened and not device.sent


def test_open_failure_cleanup():
    device = FakeSerial()
    device.open = lambda: (_ for _ in ()).throw(OSError("unplugged"))
    with pytest.raises(OSError):
        SerialTransport.open("/fake", factory=lambda **kw: device)
    assert device.closed


@pytest.mark.parametrize("chunks", [[b"abc"], [b"a", b"", b"b", b"c"]])
def test_partial_capture(chunks):
    port, device = transport(chunks)
    data, reason = port.collect(timeout=1)
    assert data == b"abc" and reason == "timeout"
    assert not device.sent


def test_limit_and_unexpected_bytes():
    port, _ = transport([b"\xff\x00abcd"])
    assert port.collect(timeout=1, limit=3) == (b"\xff\x00a", "capture-limit")


def test_disconnect_cleanup():
    port, device = transport([OSError("gone")])
    with pytest.raises(TransportError), port:
        port.collect(timeout=1)
    assert device.closed


def test_write_partial_and_interrupted():
    port, device = transport(transmit=True)
    port.write(b"abcdef")
    assert b"".join(device.sent) == b"abcdef"
    device.write = lambda data: (_ for _ in ()).throw(OSError("transfer aborted"))
    with pytest.raises(TransportError):
        port.write(b"boot image")
    with pytest.raises(TypeError):
        port.write("text")


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), 3601])
def test_invalid_deadlines(value):
    port, _ = transport()
    with pytest.raises(ValueError):
        port.collect(timeout=value)


def test_boot_prompt_and_environment():
    port, device = transport([b"U-Boot 2010.09-R8 (date)\r\n", b"U-", b"Boot>"],
                             transmit=True)
    session = UBootSession(port)
    observed = session.wait_prompt(timeout=10)
    assert version(observed) == "2010.09-R8"
    device.chunks.extend([b"printenv\r\naddmisc=console=ttymxc0\r\nU-Boot>"])
    assert b"addmisc=" in session.environment(timeout=10)
    assert b"".join(device.sent) == b"printenv\n"
    assert session.transcript and all(isinstance(e.timestamp, float) for e in session.transcript)


@pytest.mark.parametrize("data", [b"output U-Boot>", b"U-Boot>garbage", b"=>", b"U-Boot"])
def test_not_prompt(data):
    assert not prompt(data)
    port, _ = transport([data])
    with pytest.raises(DeadlineExceeded):
        UBootSession(port).wait_prompt(timeout=1)


def test_prompt_is_not_success():
    port, device = transport([b"U-Boot>"], transmit=True)
    session = UBootSession(port)
    session.wait_prompt(timeout=2)
    device.chunks.extend([b"printenv\r\nUnknown command\r\nU-Boot>"])
    with pytest.raises(TransportError):
        session.environment(timeout=10)
    assert not session.ready
    with pytest.raises(TransportError):
        session.environment()


def test_prompt_limit():
    port, _ = transport([b"x" * 20])
    with pytest.raises(CaptureLimit):
        UBootSession(port, limit=10).wait_prompt(timeout=10)


def test_disruptive_authorization_stays_disabled():
    from toonrooter.safety import Level, authorize
    for confirmed in (False, True):
        for compatible in (False, True):
            with pytest.raises(PermissionError):
                authorize(Level.DISRUPTIVE, confirmed=confirmed, compatible=compatible)
    with pytest.raises(PermissionError):
        authorize(Level.JTAG_IDENTIFICATION)


def test_real_pyserial_pty():
    import os
    import pty
    pytest.importorskip("serial")
    master, slave = pty.openpty()
    try:
        with SerialTransport.open(os.ttyname(slave)) as port:
            os.write(master, b"binary\x00\xff")
            assert port.collect(timeout=0.1, limit=8) == (b"binary\x00\xff", "capture-limit")
            with pytest.raises(PermissionError):
                port.write(b"never")
            assert not port.device.dtr and not port.device.rts
    finally:
        os.close(master)
        os.close(slave)
