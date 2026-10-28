import base64
import gzip
import io
import shutil
import tarfile
from pathlib import Path

import pytest

from toonrooter.boot.compatibility import analyze_bootloader, plan_route
from toonrooter.hardware.config_review import review_chain
from toonrooter.legacy_wire import prepare_legacy_wire
from toonrooter.payload import package
from toonrooter.security.ssh_keys import prepare_key

ROOT = Path(__file__).resolve().parents[1]


def test_complete_reference_chain():
    report = review_chain()
    assert report["unresolved"] == []
    assert report["includes"]["target/imx27.cfg"] == []
    assert report["expected_taps"] == {"cpu": "0x07926121", "etb": "0x1b900f0f"}
    assert not report["live_permitted"]
    assert "after adapter" in report["reset_override"]


@pytest.mark.parametrize("change", [b"source evil.cfg", b"reset halt", b"# innocent change"])
def test_installed_chain_mismatch(tmp_path, change):
    target = tmp_path / "target"
    target.mkdir()
    source = ROOT / "toonrooter/data/openocd-0.12.0/target/imx27.cfg"
    (target / "imx27.cfg").write_bytes(source.read_bytes() + change)
    with pytest.raises(ValueError):
        review_chain(installed_scripts=tmp_path)


def test_matching_installed_reference(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    shutil.copy(ROOT / "toonrooter/data/openocd-0.12.0/target/imx27.cfg", target)
    assert review_chain(installed_scripts=tmp_path)["unresolved"] == []
    (target / "imx27.cfg").unlink()
    with pytest.raises(OSError):
        review_chain(installed_scripts=tmp_path)


def test_bootloader_analysis():
    info = analyze_bootloader(ROOT)
    assert info["linked_address"] == 0xa1f00000
    assert info["soc_evidence"] and info["version_evidence"]
    assert info["persistent_write_capability"] and not info["live_permitted"]


@pytest.mark.parametrize("version", ["2010.09", "2010.09-R6", "2010.09-R8"])
def test_existing_console_avoids_jtag(version):
    route = plan_route(version, console_access_verified=True)
    assert route.route == "existing-console"
    assert route.operations == ("printenv", "setenv addmisc", "run boot_nand")
    assert not route.live_permitted


def test_banner_not_authentication():
    assert plan_route("2010.09").route == "jtag-fallback"
    with pytest.raises(ValueError):
        plan_route("unknown", console_access_verified=True)


def test_legacy_format_roundtrip(tmp_path):
    archive = package(ROOT, prepare_key(tmp_path / "key"))
    plan = prepare_legacy_wire(archive)
    assert plan == prepare_legacy_wire(archive)
    assert not plan.receiver_integrity_verified and not plan.live_permitted
    assert all(len(line) <= 76 for line in plan.encoded.splitlines())
    compressed = base64.decodebytes(plan.encoded)
    assert len(compressed) == plan.compressed_bytes
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(compressed))) as tar:
        names = tar.getnames()
        assert "manifest.json" not in names
        assert len(names) == 4
        assert tar.extractfile("payload/patch_toon.sh").read() == (
            ROOT / "payload/patch_toon.sh").read_bytes()
    assert plan.receiver_command == b"timeout -t 60 base64 -d | tar zxf -\n"


def test_cli_reference_and_legacy_format(tmp_path, capsys):
    from toonrooter.cli import main
    scripts = ROOT / "toonrooter/data/openocd-0.12.0"
    assert main(["asset-audit", "--repository", str(ROOT),
                 "--openocd-scripts", str(scripts)]) == 0
    assert '"installed_reference"' in capsys.readouterr().out
    prepare_key(tmp_path / "key")
    output = tmp_path / "wire.txt"
    assert main(["package-payload", "--repository", str(ROOT),
                 "--ssh-public-key", str(tmp_path / "key.pub"),
                 "--format", "legacy-base64", "--output", str(output)]) == 0
    assert gzip.decompress(base64.decodebytes(output.read_bytes())).startswith(b"payload/")


def test_wire_refuses_corruption(tmp_path):
    archive = package(ROOT, prepare_key(tmp_path / "key"))
    with pytest.raises(ValueError):
        prepare_legacy_wire(archive + b"bad")
