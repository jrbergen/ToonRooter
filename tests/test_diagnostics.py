import pytest
from test_protocols import transport

from toonrooter.cli import main
from toonrooter.hardware.serial import SerialTransport


def test_probe_never_starts_process(monkeypatch, capsys):
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("process started"))
    assert main(["probe"]) == 0
    assert main(["probe", "--jtag"]) == 2
    assert "disabled" in capsys.readouterr().err


def test_observe_receive_only(monkeypatch, capsys):
    port, device = transport([b"U-Boot 2010.09\r\n"])
    monkeypatch.setattr(SerialTransport, "open", lambda path: port)
    assert main(["observe", "--serial", "/fake", "--timeout", "1"]) == 0
    assert device.closed and not device.sent
    assert "2010.09" in capsys.readouterr().out


def test_observe_disconnect(monkeypatch):
    port, device = transport([OSError("disconnect")])
    monkeypatch.setattr(SerialTransport, "open", lambda path: port)
    assert main(["observe", "--serial", "/fake", "--timeout", "1"]) == 2
    assert device.closed


@pytest.mark.parametrize("value", ["nan", "inf", "-1"])
def test_observe_invalid_before_open(monkeypatch, value):
    monkeypatch.setattr(SerialTransport, "open", lambda *a: pytest.fail("opened"))
    assert main(["observe", "--serial", "/fake", "--timeout", value]) == 2
