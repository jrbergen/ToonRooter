"""Pinned inventory, not a trust assertion or execution authorization."""
import hashlib
import json
import os
import stat
from importlib.resources import files
from pathlib import Path, PurePosixPath

MANIFEST = json.loads(files("toonrooter").joinpath("data/assets.json").read_text())


def safe_path(name: str) -> None:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Invalid asset path")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or str(path) != name:
        raise ValueError("Noncanonical asset path")


def read_asset(root: Path, name: str) -> bytes:
    safe_path(name)
    path = root
    for component in PurePosixPath(name).parts:
        path = path / component
        if path.is_symlink():
            raise ValueError("Symlink in asset path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Asset must be a regular file")
        data = stream.read(1048577)
    if len(data) > 1048576:
        raise ValueError("Asset exceeds size bound")
    return data


def validate_inventory(root: Path, hardware="toon1-imx27", *, operation="inspect") -> dict:
    if hardware != "toon1-imx27" or operation not in ("inspect", "package", "simulate"):
        raise ValueError("Hardware or execution path is not supported")
    if MANIFEST.get("schema") != 1 or not isinstance(MANIFEST.get("assets"), list):
        raise ValueError("Invalid manifest")
    result = {}
    for entry in MANIFEST["assets"]:
        name = entry["path"]
        if name in result or entry["hardware"] != hardware:
            raise ValueError("Duplicate asset or inconsistent hardware")
        if operation not in entry["permitted_operations"]:
            raise ValueError("Operation not permitted")
        data = read_asset(root, name)
        if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("Asset integrity mismatch")
        result[name] = data
    actual = {p.relative_to(root).as_posix() for folder in ("assets", "payload")
              for p in (root / folder).rglob("*") if p.is_file() or p.is_symlink()}
    if actual != set(result):
        raise ValueError("Unexpected or missing asset")
    return result


def audit_configs(root: Path) -> dict:
    """Exact inventory allowlist, with known chain facts; never evaluates Tcl.

    Hash mismatch rejects even seemingly harmless new directives. The nested target
    script is unresolved, so no matching hash can grant live permission.
    """
    validate_inventory(root)
    from .hardware.config_review import review_chain
    reference = review_chain()
    return {
        "pinned_reference": reference,
        "review": "static-only", "live_permitted": False,
        "includes": {"assets/boards/ed20.cfg": ["target/imx27.cfg"]},
        "unresolved": ["target/imx27.cfg"],
        "effects": ["reset run", "reset halt", "gdb-attach: reset init",
                    "reset-init: ed20_init", "mww", "mwb", "reg"],
        "reason": "Pinned 0.12.0 reference reviewed; installed target chain unspecified; disruptive writes",
    }
