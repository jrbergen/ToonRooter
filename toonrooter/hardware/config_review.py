"""Exact, version-specific source review. No Tcl evaluation or execution approval."""
import hashlib
import json
from importlib.resources import files
from pathlib import Path

from toonrooter.assets import read_asset

REVIEW = json.loads(files("toonrooter").joinpath("data/openocd-review.json").read_text())


def review_chain(*, installed_scripts: Path | None = None) -> dict:
    verified = []
    for name, expected in REVIEW["files"].items():
        if installed_scripts is None:
            data = files("toonrooter").joinpath("data/openocd-0.12.0", name).read_bytes()
        else:
            data = read_asset(installed_scripts, name)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("OpenOCD target script differs from reviewed 0.12.0 reference")
        verified.append(name)
    return {
        "reference_version": REVIEW["version"], "verified_files": verified,
        "includes": {"assets/boards/ed20.cfg": ["target/imx27.cfg"],
                     **REVIEW["includes"]},
        "unresolved": [], "live_permitted": False,
        "expected_taps": {"cpu": REVIEW["cpu_id"], "etb": REVIEW["etb_id"]},
        "target": REVIEW["cpu"],
        "reset_override": "target sets trst_and_srst srst_pulls_trst after adapter reset_config none",
        "effects": ["TAP/ARM926 target creation", "SRAM work area 0xffff4c00 size 0x8000",
                    "DCC downloads enabled", "ETM/ETB configuration",
                    "board gdb-attach reset init", "board reset-init register/RAM writes"],
        "scope": "Reviewed source chain only; OpenOCD compiled command behavior and hardware unverified",
    }
