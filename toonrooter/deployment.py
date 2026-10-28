"""Read-only host readiness checks; never opens UART/GPIO or starts target OpenOCD."""
import importlib.metadata
import os
import platform
import re
import sys
from pathlib import Path

from .assets import validate_inventory
from .hardware.config_review import review_chain
from .security.ssh_keys import public_key, read_regular


def openocd_profile(version: str, adapters: str, required: str) -> tuple[str, str]:
    if required not in {"bcm2835gpio", "linuxgpiod"}:
        return "FAIL", "Unsupported adapter selection"
    match = re.search(r"Open On-Chip Debugger (\d+\.\d+\.\d+)([^\s]*)", version)
    if not match or match[1] != "0.12.0" or "dev" in match[2]:
        return "FAIL", "Reference profile requires release 0.12.0; other builds need review"
    if not re.search(r"(?<![\w])" + required + r"(?![\w])", adapters):
        return "FAIL", f"Required compiled adapter {required} not reported"
    return "PASS", f"Release profile and compiled {required} present; hardware unvalidated"


def readiness(*, serial: Path, host: dict, repository=None, scripts=None,
              key=None, adapter="bcm2835gpio", filesystem=Path("/")) -> list[dict]:
    checks = []

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})

    def text(name):
        try:
            return (filesystem / name).read_text(errors="replace")[:65536]
        except OSError:
            return ""

    add("python", "PASS" if sys.version_info >= (3, 12) else "FAIL", platform.python_version())
    for name in ("toonrooter", "cryptography", "pyserial"):
        try:
            value = importlib.metadata.version(name)
            add(name, "PASS", value)
        except importlib.metadata.PackageNotFoundError:
            add(name, "FAIL", "Package metadata missing; install into the virtual environment")
    os_release = text("etc/os-release")
    add("os", "PASS" if 'VERSION_CODENAME=trixie' in os_release else "UNKNOWN",
        os_release.strip() or "OS release unavailable; target is Raspberry Pi OS Lite Trixie")
    model = text("proc/device-tree/model").rstrip("\x00")
    add("pi-model", "PASS" if "Raspberry Pi 3" in model else "UNKNOWN",
        model or "Not detected; normal on a development workstation")
    ocd = host.get("openocd", {})
    state, detail = openocd_profile(ocd.get("VERSION", ""), ocd.get("ADAPTERS", ""), adapter)
    add("openocd-profile", state, detail + "; " + ocd.get("error", ""))
    add("serial-access", "PASS" if serial.exists() and os.access(serial, os.R_OK | os.W_OK)
        else "FAIL", f"{serial} -> {serial.resolve()}; metadata/access only, never opened")
    names = {serial.name, serial.resolve().name, "serial0"}
    cmdline = text("proc/cmdline")
    conflict = any(token.startswith("console=") and
                   token.split("=", 1)[1].split(",")[0] in names for token in cmdline.split())
    add("uart-console", "FAIL" if conflict else "UNKNOWN" if not cmdline else "PASS",
        "UART login console conflict" if conflict else
        "No selected UART in kernel console arguments; userspace consumers still require review")
    config = text("boot/firmware/config.txt")
    add("uart-configuration", "UNKNOWN",
        "Review conditional sections/overlays and hciuart; enable_uart=1 seen"
        if "enable_uart=1" in config else
        "Review raspi-config and /boot/firmware/config.txt; UART enablement not established")
    devices = list((filesystem / "dev").glob("gpiochip*"))
    devices += [filesystem / "dev/gpiomem"]
    accessible = [str(p) for p in devices if p.exists() and os.access(p, os.R_OK | os.W_OK)]
    add("gpio-access", "PASS" if accessible else "UNKNOWN",
        ", ".join(accessible) or "No accessible GPIO metadata; no GPIO line requested")
    for label, argument, validate in (
        ("assets", repository, validate_inventory),
        ("openocd-script-chain", scripts, lambda p: review_chain(installed_scripts=p)),
        ("ssh-public-key", key, lambda p: public_key(read_regular(p))),
    ):
        if argument is None:
            add(label, "UNKNOWN", "Supply explicit path to check")
        else:
            try:
                validate(argument)
                add(label, "PASS", "Host validation passed; no target compatibility claim")
            except (OSError, ValueError):
                add(label, "FAIL", "Missing, inaccessible, incompatible or changed input")
    add("target-compatibility", "HARDWARE_REQUIRED",
        "Wiring/voltage/TAP/reset/boot image/heating behavior require separate authorization")
    return checks
