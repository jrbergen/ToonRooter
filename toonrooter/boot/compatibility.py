"""Source-grounded boot route planning; never performs hardware operations."""
import hashlib
import struct
from dataclasses import dataclass

from toonrooter.assets import validate_inventory
from toonrooter.boot.uboot import PASSWORDS

SUPPORTED_VERSIONS = frozenset(PASSWORDS)


def analyze_bootloader(root) -> dict:
    data = validate_inventory(root)["assets/u-boot.bin"]
    words = struct.unpack_from("<8I", data)
    # ARM unconditional branch + seven PC-relative exception-vector loads.
    if words != (0xEA000012, *(0xE59FF014 for _ in range(7))):
        raise ValueError("Unexpected raw ARM vector layout")
    linked, entry = struct.unpack_from("<II", data, 0x40)
    if linked != 0xA1F00000 or entry != linked:
        raise ValueError("Unexpected linked/load address")
    return {
        "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
        "format": "raw binary; ARM little-endian vector signature",
        "architecture_confidence": "instruction/header inference; not full disassembly",
        "linked_address": linked, "entry_address": entry,
        "soc_evidence": b"CPU:   Freescale i.MX27" in data,
        "version_evidence": b"U-Boot 2010.09 (Feb 15 2017 - 18:17:02)" in data,
        "provenance": "unreproduced; added in a25023f",
        "persistent_write_capability": True,
        "live_permitted": False,
    }


@dataclass(frozen=True)
class BootRoute:
    route: str
    operations: tuple[str, ...]
    reason: str
    live_permitted: bool = False


def plan_route(uboot_version: str | None, *, console_access_verified=False) -> BootRoute:
    """Prefer an existing supported console, retain JTAG as a disruptive fallback.

    A version banner alone never proves password access. No password is returned/logged.
    """
    if console_access_verified:
        if uboot_version not in SUPPORTED_VERSIONS:
            raise ValueError("Unsupported existing console version")
        return BootRoute("existing-console", ("printenv", "setenv addmisc", "run boot_nand"),
                         "Avoid reset/RAM image when supported console access is established")
    return BootRoute(
        "jtag-fallback",
        ("initialize-adapter-and-target", "soft_reset_halt", "reset halt",
         "load_image assets/u-boot.bin 0xa1f00000", "resume 0xa1f00000",
         "authenticate-supported-uboot", "printenv", "setenv addmisc", "run boot_nand"),
        "Requires separate disruptive authorization and response/compatibility validation",
    )
