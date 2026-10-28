"""Fail-closed RSA key preparation for the historical Dropbear payload."""
import os
import stat
from pathlib import Path

from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric import rsa


def public_key(data: bytes) -> bytes:
    """Validate exactly one RSA public key and return its canonical representation."""
    if len(data.strip().splitlines()) != 1:
        raise ValueError("Expected one RSA public key")
    key = ser.load_ssh_public_key(data.strip())
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 2048:
        raise ValueError("Expected RSA key of at least 2048 bits")
    return key.public_bytes(ser.Encoding.OpenSSH, ser.PublicFormat.OpenSSH)


def read_regular(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Key path must be a regular file")
        return stream.read()


def write_new(path: Path, data: bytes) -> None:
    """Exclusive creation prevents overwriting existing files, including symlinks."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def prepare_key(
    private_path: Path, external_public: Path | None = None, password: bytes | None = None
) -> bytes:
    """Reuse a validated pair, recover a missing public half, or exclusively create a pair.

    A public-only pair is rejected: ownership of a matching private key is unknown.
    Failure during public creation leaves the private key intact for recovery.
    """
    if external_public is not None:
        return public_key(read_regular(external_public))
    pub_path = Path(str(private_path) + ".pub")
    private_exists = os.path.lexists(private_path)
    public_exists = os.path.lexists(pub_path)
    if private_exists:
        key = ser.load_pem_private_key(read_regular(private_path), password=password)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise ValueError("Expected RSA private key of at least 2048 bits")
        expected = key.public_key().public_bytes(ser.Encoding.OpenSSH, ser.PublicFormat.OpenSSH)
        if public_exists:
            if public_key(read_regular(pub_path)) != expected:
                raise ValueError("Public and private keys do not match")
        else:
            write_new(pub_path, expected)
        return expected
    if public_exists:
        raise ValueError("Public key exists without private key; use an external public key explicitly")
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    encryption = ser.BestAvailableEncryption(password) if password else ser.NoEncryption()
    private = key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, encryption)
    expected = key.public_key().public_bytes(ser.Encoding.OpenSSH, ser.PublicFormat.OpenSSH)
    write_new(private_path, private)
    write_new(pub_path, expected)
    return expected
