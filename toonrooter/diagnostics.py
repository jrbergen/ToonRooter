"""Level 0 host inspection and Level 1 bounded observation."""
import platform
from datetime import UTC, datetime
from pathlib import Path

from .boot.uboot import version
from .hardware.openocd import OpenOCD, OpenOCDError, Query
from .hardware.serial import SerialTransport


def host_details():
    details = {"os": f"{platform.system()} {platform.release()}", "architecture": platform.machine(),
               "python": platform.python_version(), "pi_model": None,
               "gpio_devices": [str(p) for p in Path("/dev").glob("gpiochip*")],
               "serial_ports": [], "openocd": {}, "adapter_compatibility": "UNVALIDATED",
               "pi3_bcm_jtag": {"tck": 11, "tms": 25, "tdi": 10, "tdo": 9}}
    model = Path("/proc/device-tree/model")
    if model.is_file():
        details["pi_model"] = model.read_text().rstrip("\x00")
    try:
        from serial.tools.list_ports import comports
        details["serial_ports"] = [p.device for p in comports()]
    except ImportError:
        details["serial_ports"] = ["pySerial unavailable"]
    try:
        client = OpenOCD()
        for query in Query:
            details["openocd"][query.name] = client.query(query).decode("utf-8", "replace")
    except (OpenOCDError, OSError) as exc:
        details["openocd"]["error"] = str(exc)
    return details


def observe(path, *, timeout, limit):
    print("Passive UART observation: no software transmission; adapter control-line "
          "glitches remain possible. No JTAG.")
    with SerialTransport.open(path) as transport:
        def display(chunk):
            # repr escapes terminal control sequences and bounds output to the input limit.
            print(f"{datetime.now(UTC).isoformat()} RX {chunk!r}")
        data, reason = transport.collect(timeout=timeout, limit=limit, on_chunk=display)
    print(f"Capture ended: {reason}; bytes={len(data)}; U-Boot={version(data) or 'unknown'}")
    return 0
