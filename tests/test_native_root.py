"""In-memory byte devices only; no Pi, Toon or OpenOCD target interaction."""
from collections import deque
from pathlib import Path

import pytest

from toonrooter.boot.live import BootAuthorization, environment_values, validate_boot_environment
from toonrooter.boot.native import JtagAvailable, select_method, temporary_root
from toonrooter.boot.profiles import R8_ENVIRONMENT
from toonrooter.boot.uboot import PASSWORDS
from toonrooter.cli import main
from toonrooter.hardware.serial import DeadlineExceeded, SerialTransport, TransportError

AUTH = BootAuthorization(uart_commands=True, boot_linux_shell=True, change_boot_arguments=True)
COMMAND = (b"setenv addmisc setenv bootargs \\$\\{bootargs\\} "
           b"mem=\\$\\{mem\\} lpj=999424 init=/bin/sh\n")


def snapshot(env):
    return b"\n".join(k + b"=" + v for k, v in env.items())


class ToonUART:
    def __init__(self, version="2010.09-R8", *, fail=None, env=None, expected_setenv=COMMAND):
        self.expected_setenv = expected_setenv
        self.version = version
        self.fail = fail
        self.env = dict(R8_ENVIRONMENT if env is None else env)
        self.rx = deque(b"Boot ROM\r\nU-Boot " + version.encode() + b" (Feb 15 2017)\r\n"
                        + (b"Enter password - autoboot in 2 sec" if fail != "challenge" else b""))
        self.pending = bytearray()
        self.sent = bytearray()
        self.commands = []
        self.now = 0
        self.closed = False
        self.authenticated = False
        self.expected = {"2010.09-R8": b"3BHf2\r", "2010.09-R6": b"f4E9J\r",
                         "2010.09": b"toon\r"}.get(version)

    def read(self, size):
        self.now += .001
        if self.fail == "disconnect":
            raise OSError("UART disconnected")
        return bytes([self.rx.popleft()]) if self.rx else b""

    def write(self, data):
        assert not self.rx, "Must consume challenge/prompt before sending input"
        part = data[:2]
        self.sent.extend(part)
        self.pending.extend(part)
        if not self.authenticated:
            if self.pending == self.expected:
                self.authenticated = True
                self.pending.clear()
                self.rx.extend(b"Wrong password\r\n" if self.fail == "auth" else b"\r\nU-Boot> ")
        elif self.pending.endswith(b"\n"):
            command = bytes(self.pending)
            self.commands.append(command)
            self.pending.clear()
            echo = command.replace(b"\n", b"\r\n")
            if command == b"printenv\n":
                self.rx.extend(echo + snapshot(self.env).replace(b"\n", b"\r\n")
                               + b"\r\nEnvironment size: 1234/131068 bytes\r\nU-Boot> ")
            elif command.startswith(b"setenv addmisc "):
                assert command == self.expected_setenv  # Explicit expected wire bytes.
                if self.fail != "readback":
                    self.env[b"addmisc"] += b" init=/bin/sh"
                self.rx.extend(echo + b"U-Boot> ")
            elif command == b"run boot_nand\n":
                self.rx.extend(echo + (b"Kernel panic\r\n" if self.fail == "boot" else
                               b"# " if self.fail == "shell-prompt" else b"/bin/sh: can't access tty; job control turned off\r\n/ # "))
            elif command.startswith(b"id;"):
                uid = b"uid=1000(user)" if self.fail == "uid" else b"uid=0(root)"
                self.rx.extend(echo + uid + b" gid=0(root)\r\nTR:ID:0\r\n/ # ")
            elif b"mount -t proc proc /proc" in command:
                status = b"1" if self.fail == "proc" else b"0"
                self.rx.extend(echo + b"TR:PROC:" + status + b"\r\n/ # ")
            else:
                pytest.fail("Unexpected target command")
        return len(part)

    def close(self):
        self.closed = True


def run(monkeypatch, device, **kwargs):
    port = SerialTransport(device, transmit=True, clock=lambda: device.now)
    monkeypatch.setattr(SerialTransport, "open", lambda *a, **kw: port)
    return temporary_root("/fake", AUTH, timeout=1, **kwargs)


@pytest.mark.parametrize("method", ["auto", "uart"])
def test_r8_complete_hardware_sequence(monkeypatch, method):
    device = ToonUART()
    result = run(monkeypatch, device, method=method)
    assert result["method"] == "uart" and result["temporary_root"] and result["proc_available"]
    assert not result["permanent_root"] and not result["installation_performed"]
    assert not result["ssh_verified"]
    assert device.commands[:4] == [b"printenv\n", COMMAND, b"printenv\n", b"run boot_nand\n"]
    assert device.closed and b"saveenv" not in device.sent
    assert "3BHf2" not in str(result)


def test_historical_r6_requires_reviewed_environment(monkeypatch):
    # Synthetic R6 configuration deliberately differs from the R8 profile.
    env = {**R8_ENVIRONMENT, b"addmisc": b"setenv bootargs ${bootargs} mem=${mem}",
           b"mem": b"64M", b"loadaddr": b"0xA0000000"}
    expected = b"setenv addmisc setenv bootargs \\$\\{bootargs\\} mem=\\$\\{mem\\} init=/bin/sh\n"
    device = ToonUART("2010.09-R6", env=env, expected_setenv=expected)
    result = run(monkeypatch, device, reviewed_environment=snapshot(device.env))
    assert result["uboot_version"] == "2010.09-R6"
    assert "historically documented" in result["password_evidence"]
    assert device.sent.startswith(b"f4E9J\r") and device.closed
    device = ToonUART("2010.09-R6", env=env)
    with pytest.raises(TransportError, match="snapshot"):
        run(monkeypatch, device)
    assert b"setenv" not in device.sent


@pytest.mark.parametrize("failure,error", [
    ("challenge", DeadlineExceeded), ("auth", DeadlineExceeded),
    ("readback", TransportError), ("boot", DeadlineExceeded),
    ("shell-prompt", DeadlineExceeded),
    ("uid", TransportError), ("proc", TransportError), ("disconnect", TransportError),
])
def test_failure_cleanup_no_fallback(monkeypatch, failure, error):
    device = ToonUART(fail=failure)
    class NeverJtag:
        def start(self, *a, **kw):
            pytest.fail("Automatic JTAG fallback forbidden")
    with pytest.raises(error):
        run(monkeypatch, device, jtag_backend=NeverJtag())
    assert device.closed and b"saveenv" not in device.sent
    if failure in {"challenge", "auth", "readback"}:
        assert b"run boot_nand\n" not in device.sent
    if failure in {"boot", "uid"}:
        assert b"mount -t proc" not in device.sent


@pytest.mark.parametrize("key,value", [(b"addmisc", b"setenv bootargs changed"),
                                        (b"boot_nand", b"saveenv; reset"),
                                        (b"loadaddr", b"0x00000000"),
                                        (b"nandargs", b"setenv bootargs other-root")])
def test_profile_mismatch_never_changes_boot(monkeypatch, key, value):
    env = {**R8_ENVIRONMENT, key: value}
    device = ToonUART(env=env)
    with pytest.raises(TransportError, match="profile"):
        run(monkeypatch, device)
    assert device.commands == [b"printenv\n"]


@pytest.mark.parametrize("macro", [b"saveenv", b"nand erase 0 1", b"nand write a b c",
                                    b"run missing", b"run boot_nand", b"run ${unknown}",
                                    b"setenv bootargs foo && saveenv"])
def test_reviewed_snapshot_does_not_authorize_persistent_commands(macro):
    env = {**R8_ENVIRONMENT, b"boot_nand": b"run addmisc; " + macro}
    with pytest.raises(TransportError):
        validate_boot_environment(env)


def test_known_profile_recurses_named_nand_reads():
    validate_boot_environment(R8_ENVIRONMENT)
    assert environment_values(snapshot(R8_ENVIRONMENT)) == R8_ENVIRONMENT
    with pytest.raises(TransportError):
        environment_values(b"addmisc=x\naddmisc=y")


@pytest.mark.parametrize("version", ["2010.09-R6", "2010.09-R8", "2010.09"])
def test_selection_prefers_password_even_when_jtag_available(version):
    assert select_method("auto", version, jtag_supported=True) == "uart"


def test_selection_unknown_or_unavailable_password(monkeypatch):
    with pytest.raises(JtagAvailable):
        select_method("auto", "unknown", jtag_supported=True)
    with pytest.raises(TransportError):
        select_method("uart", "unknown", jtag_supported=True)
    monkeypatch.delitem(PASSWORDS,
                        "2010.09-R8")
    with pytest.raises(JtagAvailable):
        select_method("auto", "2010.09-R8", jtag_supported=True)


def test_auto_unknown_does_not_send_or_start_jtag(monkeypatch):
    device = ToonUART("2099.01")
    with pytest.raises(JtagAvailable):
        run(monkeypatch, device, repository=Path('/fake'),
            model="Raspberry Pi 3 Model B Rev 1.2")
    assert device.closed and not device.sent


def test_explicit_jtag_retained_and_gated(monkeypatch):
    device = ToonUART("2010.09-R8")
    port = SerialTransport(device, transmit=True, clock=lambda: device.now)
    opened = []
    def open_port(*a, **kw):
        opened.append(True)
        return port
    monkeypatch.setattr(SerialTransport, "open", open_port)
    class Jtag:
        def start(self, authorization, **kw):
            assert opened and authorization.execute_reviewed_image
    with pytest.raises(PermissionError):
        temporary_root("/fake", AUTH, method="jtag", repository=Path('/fake'),
                       model="Raspberry Pi 3 Model B Rev 1.2")
    assert not opened
    auth = BootAuthorization(True, True, True, True, True)
    with pytest.raises(TransportError, match="snapshot"):
        temporary_root("/fake", auth, method="jtag", repository=Path('/fake'),
                       model="Raspberry Pi 3 Model B Rev 1.2", jtag_backend=Jtag())
    assert not opened
    result = temporary_root("/fake", auth, method="jtag", repository=Path('/fake'),
                            model="Raspberry Pi 3 Model B Rev 1.2", jtag_backend=Jtag(),
                            reviewed_environment=snapshot(device.env))
    assert result['method'] == 'jtag' and device.closed


@pytest.mark.parametrize("extra", [[], ["--authorize-uart"], ["--install"],
                                    ["--install", "--authorize-install"], ["--authorize-install"],
                                    ["--authorize-uart", "--authorize-shell-boot"]])
def test_cli_refuses_before_open(monkeypatch, capsys, extra):
    monkeypatch.setattr(SerialTransport, "open", lambda *a, **kw: pytest.fail("opened hardware"))
    assert main(["root", "--serial", "/fake", *extra]) == 2
    assert capsys.readouterr().err


def test_cli_dispatch_and_no_secret_output(monkeypatch, capsys):
    device = ToonUART()
    port = SerialTransport(device, transmit=True, clock=lambda: device.now)
    monkeypatch.setattr(SerialTransport, "open", lambda *a, **kw: port)
    assert main(["root", "--serial", "/fake", "--method", "auto", "--authorize-uart",
                 "--authorize-boot-arguments", "--authorize-shell-boot"]) == 0
    output = capsys.readouterr()
    assert '"permanent_root": false' in output.out and '3BHf2' not in output.out + output.err
    assert "ready for Toon power-on" in output.err
