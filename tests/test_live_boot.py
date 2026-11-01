from collections import deque
from pathlib import Path

import pytest

from toonrooter.boot.live import (
    BOOTSTRAP,
    BootAuthorization,
    BootConsole,
    Pi3JtagBoot,
    boot_to_console,
)
from toonrooter.deployment import openocd_profile
from toonrooter.hardware.openocd import OpenOCDError, Query, parse_adapters
from toonrooter.hardware.serial import DeadlineExceeded, SerialTransport, TransportError

ROOT = Path(__file__).resolve().parents[1]
PI = "Raspberry Pi 3 Model B Rev 1.2"
AUTH = BootAuthorization(True, True, True, True, True)
VERSION = "Open On-Chip Debugger 0.12.0+dev-snapshot (2026-02-16-16:07)"
ADAPTERS = "banner\nTOON_ADAPTERS_BEGIN\nbcm2835gpio sysfsgpio linuxgpiod\nTOON_ADAPTERS_END\nshutdown command invoked"
ENV = (b"printenv\r\naddmisc=setenv bootargs ${bootargs} mem=${mem}\r\n"
       b"boot_nand=run addmisc; nand read 0xa0000000 0 0x200000; bootm 0xa0000000\r\nU-Boot>")


@pytest.mark.parametrize("value,status", [
    (VERSION, "PASS"), (VERSION.replace("16:07", "16:08"), "UNKNOWN"),
    ("Open On-Chip Debugger 0.12.0+dev-123", "UNKNOWN"),
    ("Open On-Chip Debugger 0.12.0+dfsg-1", "PASS"),
    ("Open On-Chip Debugger 0.11.0", "FAIL"),
    ("Open On-Chip Debugger 0.13.0", "UNKNOWN"), ("garbage", "UNKNOWN"),
])
def test_versions(value, status):
    assert openocd_profile(value, " ".join(parse_adapters(ADAPTERS)), "bcm2835gpio")[0] == status


@pytest.mark.parametrize("output", ["shutdown command invoked", "", ADAPTERS + ADAPTERS,
                                       ADAPTERS.replace("bcm2835gpio sysfsgpio linuxgpiod", ""),
                                       ADAPTERS.replace("sysfsgpio", "Info : startup")])
def test_bad_adapters(output):
    with pytest.raises(OpenOCDError):
        parse_adapters(output)


def test_missing_adapter():
    assert openocd_profile(VERSION, "sysfsgpio linuxgpiod", "bcm2835gpio")[0] == "FAIL"


class Client:
    def __init__(self, output=None, failure=None):
        self.calls = []
        self.output = output if output is not None else (
            b"TOON_BOOT:identified\nTOON_BOOT:initialized\nTOON_BOOT:verified\nTOON_BOOT:resumed\n")
        self.failure = failure

    def query(self, query):
        return (ADAPTERS if query is Query.ADAPTERS else VERSION).encode()

    def _run(self, args, **kwargs):
        self.calls.append((args, kwargs))
        root = Path(kwargs["cwd"])
        assert (root / "boot.bin").read_bytes() == (ROOT / "assets/u-boot.bin").read_bytes()
        assert (root / "boot.cfg").read_text() == BOOTSTRAP
        assert (root / "target/imx27.cfg").exists()
        if self.failure:
            raise self.failure
        return self.output


def test_bootstrap_sequence_and_cleanup():
    client = Client()
    assert Pi3JtagBoot(ROOT, client=client).start(AUTH, model=PI)[-1] == "resumed"
    assert not Path(client.calls[0][1]["cwd"]).exists()
    sequence = ["init\n", "jtag cget imx27.cpu", "jtag cget imx27.etb", "soft_reset_halt",
                "reset init", "load_image", "verify_image", "resume 0xa1f00000"]
    assert [BOOTSTRAP.index(item) for item in sequence] == sorted(
        BOOTSTRAP.index(item) for item in sequence)
    for forbidden in ("saveenv", "nand write", "flash write", "program "):
        assert forbidden not in BOOTSTRAP


@pytest.mark.parametrize("output", [b"Wrong CPU TAP", b"Wrong ETB TAP", b"target not examined",
                                       b"TOON_BOOT:identified\nTOON_BOOT:failed\n",
                                       b"TOON_BOOT:resumed\n"])
def test_wrong_target_or_transfer_evidence(output):
    with pytest.raises(OpenOCDError):
        Pi3JtagBoot(ROOT, client=Client(output)).start(AUTH, model=PI)


@pytest.mark.parametrize("failure", [OpenOCDError("startup failed"),
                                     OpenOCDError("load failed"), KeyboardInterrupt()])
def test_jtag_abort_cleanup(failure):
    client = Client(failure=failure)
    with pytest.raises(type(failure)):
        Pi3JtagBoot(ROOT, client=client).start(AUTH, model=PI)
    assert not Path(client.calls[0][1]["cwd"]).exists()


def test_gate_and_image_rejection(tmp_path):
    client = Client()
    with pytest.raises(PermissionError):
        Pi3JtagBoot(ROOT, client=client).start(BootAuthorization(), model=PI)
    with pytest.raises(ValueError):
        Pi3JtagBoot(ROOT, client=client).start(AUTH, model="Raspberry Pi 4")
    with pytest.raises((OSError, ValueError)):
        Pi3JtagBoot(tmp_path, client=client).start(AUTH, model=PI)
    assert not client.calls


class ConsoleDevice:
    def __init__(self, banner=b"U-Boot 2010.09 (Feb 15 2017)\r\n", failure=None):
        self.rx = deque(banner + b"Enter password - autoboot in 2 sec")
        self.sent = bytearray()
        self.pending = bytearray()
        self.now = 0
        self.closed = False
        self.env = ENV
        self.failure = failure
        self.prints = 0

    def read(self, size):
        self.now += .001
        if self.failure:
            raise self.failure
        return bytes([self.rx.popleft()]) if self.rx else b""

    def write(self, data):
        part = data[:2]
        self.sent.extend(part)
        self.pending.extend(part)
        if self.pending == b"toon\r":
            self.rx.extend(b"U-Boot>")
            self.pending.clear()
        elif self.pending.endswith(b"\n"):
            command = bytes(self.pending)
            self.pending.clear()
            if command == b"printenv\n":
                self.prints += 1
                self.rx.extend(self.env)
            elif command.startswith(b"setenv addmisc "):
                self.env = ENV.replace(b" mem=${mem}", b" mem=${mem} init=/bin/sh")
                self.rx.extend(command.replace(b"\n", b"\r\n") + b"U-Boot>")
            elif command == b"run boot_nand\n":
                self.rx.extend(b"Starting kernel ...\r\n/ # ")
            else:
                pytest.fail("Unexpected console command")
        return len(part)

    def close(self):
        self.closed = True


def console(device):
    port = SerialTransport(device, transmit=True, clock=lambda: device.now)
    return BootConsole(port)


def test_realistic_console_sequence():
    device = ConsoleDevice()
    session = console(device)
    assert session.login(AUTH) == "2010.09"
    session.linux_shell(AUTH, reviewed_environment=ENV)
    assert device.prints == 2
    assert device.sent.endswith(b"run boot_nand\n")
    assert b"saveenv" not in device.sent


@pytest.mark.parametrize("banner,error", [(b"U-Boot 2025.01 (test)\n", TransportError),
                                          (b"unexpected> ", DeadlineExceeded),
                                          (b"U-Boot 2010.09 (test)\nwrong>", DeadlineExceeded)])
def test_unexpected_console(banner, error):
    device = ConsoleDevice(banner)
    # Do not provide expected prompt after password.
    device.write = lambda data: len(data)
    with pytest.raises(error):
        console(device).login(AUTH, timeout=.1)


def test_uart_disconnect_and_environment_mismatch():
    device = ConsoleDevice(failure=OSError("disconnected"))
    with pytest.raises(TransportError):
        console(device).login(AUTH)
    device = ConsoleDevice()
    session = console(device)
    session.login(AUTH)
    with pytest.raises(TransportError, match="reviewed"):
        session.linux_shell(AUTH, reviewed_environment=ENV.replace(b"0x200000", b"0x100000"))
    assert b"setenv" not in device.sent


def test_wrapper_closes_uart_on_jtag_failure(monkeypatch):
    device = ConsoleDevice()
    port = SerialTransport(device, transmit=True, clock=lambda: device.now)
    monkeypatch.setattr(SerialTransport, "open", lambda *a, **kw: port)
    class Broken:
        def start(self, *args, **kwargs):
            raise OpenOCDError("failed")
    with pytest.raises(OpenOCDError):
        boot_to_console(ROOT, "/fake", AUTH, model=PI, jtag=True, jtag_backend=Broken())
    assert device.closed and not device.sent


def test_shell_boot_requires_approval_and_verified_update():
    device = ConsoleDevice()
    session = console(device)
    session.login(AUTH)
    with pytest.raises(PermissionError):
        session.linux_shell(BootAuthorization(uart_commands=True), reviewed_environment=ENV)
    assert b"printenv" not in device.sent
    original_write = device.write
    def fail_setenv(data):
        count = original_write(data)
        # Model a bootloader that echoes setenv but fails to change the variable.
        if device.sent.endswith(b"\\; nand read"):
            pytest.fail("No environment commands should be sent")
        if device.sent.endswith(b"init=/bin/sh\n"):
            device.env = ENV
        return count
    device.write = fail_setenv
    with pytest.raises(TransportError, match="update not verified"):
        session.linux_shell(AUTH, reviewed_environment=ENV)
    assert b"run boot_nand" not in device.sent


def test_failed_bootstrap_closes_uart_before_console(monkeypatch):
    device = ConsoleDevice()
    port = SerialTransport(device, transmit=True, clock=lambda: device.now)
    monkeypatch.setattr(SerialTransport, "open", lambda *a, **kw: port)
    class Aborted:
        def start(self, *args, **kwargs):
            raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        boot_to_console(ROOT, "/fake", AUTH, model=PI, jtag=True, jtag_backend=Aborted())
    assert device.closed
