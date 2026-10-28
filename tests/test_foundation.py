import os
from pathlib import Path

import pytest

from toonrooter.cli import main
from toonrooter.config import Config
from toonrooter.security.ssh_keys import prepare_key, write_new


def test_create_reuse_and_recover(tmp_path):
    path = tmp_path / "key"
    public = prepare_key(path, password=b"secret")
    original = path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600
    assert prepare_key(path, password=b"secret") == public
    path.with_suffix(".pub").unlink()
    assert prepare_key(path, password=b"secret") == public
    assert path.read_bytes() == original
    with pytest.raises(ValueError):
        prepare_key(path, password=b"wrong")
    assert path.read_bytes() == original


@pytest.mark.parametrize("data", [b"", b"invalid", b"ssh-rsa nonsense"])
def test_invalid_public_never_overwrites(tmp_path, data):
    path = tmp_path / "key"
    prepare_key(path)
    original = path.read_bytes()
    Path(str(path) + ".pub").write_bytes(data)
    with pytest.raises(ValueError):
        prepare_key(path)
    assert path.read_bytes() == original


def test_mismatch_and_external(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    prepare_key(first)
    pub = prepare_key(second)
    Path(str(first) + ".pub").write_bytes(pub)
    with pytest.raises(ValueError):
        prepare_key(first)
    assert prepare_key(first, Path(str(second) + ".pub")) == pub


def test_public_only(tmp_path):
    path = tmp_path / "key"
    Path(str(path) + ".pub").write_bytes(b"existing")
    with pytest.raises(ValueError):
        prepare_key(path)
    assert not path.exists()


def test_unsafe_paths(tmp_path):
    path = tmp_path / "key"
    target = tmp_path / "target"
    target.write_bytes(b"unchanged")
    path.symlink_to(target)
    with pytest.raises(OSError):
        prepare_key(path)
    with pytest.raises(FileExistsError):
        write_new(path, b"replacement")
    assert target.read_bytes() == b"unchanged"
    with pytest.raises((OSError, ValueError)):
        prepare_key(tmp_path)
    with pytest.raises(OSError):
        prepare_key(path, tmp_path / "missing")


def test_doctor_never_opens_devices(monkeypatch, capsys):
    monkeypatch.setattr(os, "open", lambda *a, **k: pytest.fail("device opened"))
    assert main(["doctor", "--serial-port", "/nonexistent-toon-port"]) == 1
    assert "UNVALIDATED" in capsys.readouterr().out


def test_cli_and_config(tmp_path, capsys):
    assert main(["keys", "--private-key", str(tmp_path / "key")]) == 0
    assert "PRIVATE KEY" not in capsys.readouterr().out
    assert main(["doctor", "--serial-port", "relative"]) == 2
    with pytest.raises(SystemExit):
        main(["root"])
    with pytest.raises(ValueError):
        Config(Path("relative"))
