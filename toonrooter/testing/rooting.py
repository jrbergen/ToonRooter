"""Synthetic observations, source-derived commands; never runs target shell scripts."""
import base64
import gzip
import io
import tarfile

from toonrooter.workflow import TRANSFER_STATUS, VERIFY


class SimulatedSerial:
    def __init__(self, rig):
        self.rig = rig
        self.now = 0.0
        self.output = bytearray(
            b"U-Boot " + rig.boot_version.encode() + b" (synthetic fixture)\r\n")
        self.input = bytearray()
        self.encoded = bytearray()
        self.receiving = False
        self.authenticated = False
        self.closed = False
        self.writes = []  # Sizes only, secrets excluded.
        self.commands = []
        self.transferred_files = {}

    def read(self, size):
        self.now += 0.01 if not self.output else 0.0001
        if self.rig.fail == "disconnect":
            raise OSError("Synthetic disconnect")
        if self.rig.fail == "timeout":
            return b""
        chunk = bytes(self.output[:min(size, 7)])
        del self.output[:len(chunk)]
        return chunk

    def emit(self, data):
        self.output.extend(data)

    def write(self, data):
        self.now += 0.0001
        data = data[:79]  # Real transport must finish partial writes.
        self.writes.append(len(data))
        if self.receiving:
            self.encoded.extend(data)
            if len(self.encoded) > 1048576:
                raise OSError("Receive bound exceeded")
            if b"\x04" in self.encoded:
                encoded, rest = self.encoded.split(b"\x04", 1)
                self.receiving = False
                try:
                    if self.rig.fail == "incomplete":
                        encoded = encoded[:len(encoded) // 2]
                    compressed = base64.b64decode(encoded, validate=False)
                    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(compressed))) as tar:
                        self.transferred_files = {m.name: tar.extractfile(m).read() for m in tar}
                    # A real tar exit status does not compare host hashes.
                    self.rig.transfer_ok = True
                except (ValueError, OSError, EOFError, tarfile.TarError, KeyError):
                    self.rig.transfer_ok = False
                self.input.clear()
                self.emit(b"\r\n/ # ")
            return len(data)
        self.input.extend(data)
        if not self.authenticated and bytes(self.input) in (b"toon", b"f4E9J", b"3BHf2"):
            self.input.clear()
            self.authenticated = True
            self.emit(b"\r\nU-Boot>")
        while b"\n" in self.input:
            line, rest = self.input.split(b"\n", 1)
            self.input = bytearray(rest)
            self.command(bytes(line) + b"\n")
        return len(data)

    def command(self, command):
        if command.startswith(b"sh payload/patch_toon.sh"):
            self.commands.append(b"INSTALL (redacted)")
            self.rig.install_attempted = True
            status = b"1" if self.rig.fail == "install" else b"0"
            self.emit(b"\r\nTR:INSTALL:" + status + b"\n/ # ")
            return
        self.commands.append(command)
        if command == b"printenv\n":
            self.emit(b"printenv\r\naddmisc=setenv bootargs ${bootargs} mem=${mem}\r\nU-Boot>")
        elif command.startswith(b"setenv addmisc "):
            self.emit(b"\r\nU-Boot>")
        elif command == b"run boot_nand\n":
            self.emit(b"\r\n/ # ")
        elif command == b"timeout -t 60 base64 -d | tar zxf -\n":
            self.receiving = True
        elif command == TRANSFER_STATUS:
            ok = self.rig.transfer_ok and self.rig.fail != "transfer"
            self.emit(b"\r\nTR:TRANSFER:" + (b"0" if ok else b"1") + b"\n/ # ")
        elif command == VERIFY:
            self.emit(b"\r\nTR:VERIFY:" +
                      (b"1" if self.rig.fail == "verify" else b"0") + b"\n/ # ")
        elif command == b"/etc/init.d/reboot\n":
            self.rig.rebooted = True
        elif command.strip():
            raise OSError("Unexpected synthetic command")

    def close(self):
        self.closed = True


class SimulatedRig:
    def __init__(self, *, hardware="toon1-imx27", openocd_version="0.12.0",
                 boot_version="unsupported", fail=None):
        self.hardware, self.openocd_version = hardware, openocd_version
        self.boot_version, self.fail = boot_version, fail
        self.serial = SimulatedSerial(self)
        self.transfer_ok = self.install_attempted = self.rebooted = self.closed = False
        self.jtag_commands = []
        self.openocd_started = False

    def start_openocd(self):
        self.openocd_started = True
        if self.fail == "openocd":
            raise OSError("Synthetic startup failure")
        return (0, 0) if self.fail == "identity" else (0x07926121, 0x1b900f0f)

    def jtag(self, command):
        self.jtag_commands.append(command)
        if self.fail == "interrupt":
            raise KeyboardInterrupt
        if command.startswith(b"load_image"):
            return b"failed" if self.fail == "load" else b"downloaded 166504 bytes"
        if command.startswith(b"resume"):
            observed = "unknown" if self.fail == "bootloader" else "2010.09"
            self.serial.emit(b"U-Boot " + observed.encode() + b" (synthetic)\n")
            return b""
        return b"target halted"

    def verify_boot_and_ssh(self, *, timeout):
        # Explicit synthetic evidence, no subprocess/network/real SSH.
        return self.rebooted and self.fail not in {"reboot", "ssh"}

    def close(self):
        self.serial.close()
        self.closed = True
