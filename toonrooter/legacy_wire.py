"""Offline preparation for the actual historical receiver; no transfer executor."""
import base64
import gzip
import io
import tarfile
from dataclasses import dataclass

from .payload import LIMIT, _encode, digest, verify


@dataclass(frozen=True)
class LegacyWirePlan:
    receiver_command: bytes
    encoded: bytes
    archive_sha256: str
    compressed_bytes: int
    receiver_integrity_verified: bool = False
    live_permitted: bool = False


def prepare_legacy_wire(archive: bytes) -> LegacyWirePlan:
    """Adapt host USTAR bundle to gzip/base64 format used by rooter.py:147-165.

    Remove host-only manifest from the target archive. No new target utilities.
    SHA256 here is host-side only; the old pipeline supplies no verified receipt.
    """
    verify(archive)
    contents = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for member in tar:
            if member.name != "manifest.json":
                contents[member.name] = tar.extractfile(member).read()
    compressed = gzip.compress(_encode(contents), mtime=0)
    encoded = base64.encodebytes(compressed)  # legacy base64.encode: 76-column lines
    if len(encoded) > LIMIT:
        raise ValueError("Wire payload exceeds bound")
    return LegacyWirePlan(
        b"timeout -t 60 base64 -d | tar zxf -\n", encoded,
        digest(compressed), len(compressed),
    )
