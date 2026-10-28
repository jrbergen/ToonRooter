"""Deterministic host archive. Never extract or execute payload contents."""
import hashlib
import io
import json
import tarfile

from .assets import validate_inventory
from .security.ssh_keys import public_key

LIMIT = 1048576
KEY_PATH = "payload/id_rsa.pub"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package(root, key: bytes) -> bytes:
    assets = validate_inventory(root, operation="package")
    contents = {name: data for name, data in assets.items() if name.startswith("payload/")}
    contents[KEY_PATH] = public_key(key) + b"\n"
    manifest = {name: {"sha256": digest(data), "size": len(data), "mode": 0o600}
                for name, data in contents.items()}
    contents["manifest.json"] = json.dumps(manifest, sort_keys=True,
                                           separators=(",", ":")).encode()
    result = _encode(contents)
    verify(result)
    return result


def _encode(contents):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(contents.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o600, 0
            archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


def verify(data: bytes) -> dict:
    try:
        return _verify(data)
    except (tarfile.TarError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Invalid payload archive") from exc


def _verify(data: bytes) -> dict:
    from .assets import MANIFEST
    if not 0 < len(data) <= LIMIT:
        raise ValueError("Invalid archive size")
    expected = {e["path"]: e for e in MANIFEST["assets"] if e["type"] == "payload"}
    expected_names = set(expected) | {KEY_PATH, "manifest.json"}
    contents = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        for member in archive:
            if (member.name not in expected_names or member.name in contents
                    or not member.isfile() or member.mode != 0o600
                    or not 0 <= member.size <= LIMIT or member.uid or member.gid
                    or member.mtime or member.pax_headers):
                raise ValueError("Unexpected archive member or metadata")
            contents[member.name] = archive.extractfile(member).read()
    if set(contents) != expected_names:
        raise ValueError("Incomplete archive")
    if _encode(contents) != data:
        raise ValueError("Noncanonical archive or trailing data")
    manifest = json.loads(contents.pop("manifest.json"))
    actual = {name: {"sha256": digest(value), "size": len(value), "mode": 0o600}
              for name, value in contents.items()}
    if manifest != actual:
        raise ValueError("Archive manifest mismatch")
    for name, entry in expected.items():
        if digest(contents[name]) != entry["sha256"]:
            raise ValueError("Unexpected executable or package content")
    public_key(contents[KEY_PATH])
    return actual
