from pathlib import Path

import pytest

from toonrooter.deployment import openocd_profile, readiness

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("version,adapters,result", [
    ("Open On-Chip Debugger 0.12.0", "bcm2835gpio {jtag swd}", "PASS"),
    ("Open On-Chip Debugger 0.12.0+dev", "bcm2835gpio", "UNKNOWN"),
    ("Open On-Chip Debugger 0.11.0", "bcm2835gpio", "FAIL"),
    ("Open On-Chip Debugger 0.12.0", "not_bcm2835gpio", "FAIL"),
    ("unknown", "bcm2835gpio", "UNKNOWN"),
])
def test_openocd_release_adapter_profile(version, adapters, result):
    assert openocd_profile(version, adapters, "bcm2835gpio")[0] == result


def test_readonly_deployment_conflict(tmp_path, monkeypatch):
    (tmp_path / "proc").mkdir()
    (tmp_path / "proc/cmdline").write_text("console=serial0,115200 root=/dev/mmcblk0")
    monkeypatch.setattr("toonrooter.deployment.os.open",
                        lambda *a, **kw: pytest.fail("device opened"))
    checks = readiness(serial=Path("/dev/serial0"), filesystem=tmp_path, host={})
    by_name = {c["name"]: c for c in checks}
    assert by_name["uart-console"]["status"] == "FAIL"
    assert by_name["target-compatibility"]["status"] == "HARDWARE_REQUIRED"


def test_simulation_cli(tmp_path, capsys):
    from toonrooter.cli import main
    from toonrooter.security.ssh_keys import prepare_key
    prepare_key(tmp_path / "key")
    args = ["simulate-root", "--repository", str(ROOT),
            "--ssh-public-key", str(tmp_path / "key.pub")]
    assert main(args) == 2
    assert main([*args, "--authorize-simulated-install", "--authorize-simulated-reboot"]) == 0
    output = capsys.readouterr().out
    assert "SIMULATED" in output and "PRIVATE KEY" not in output
