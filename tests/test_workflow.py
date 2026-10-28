from pathlib import Path

import pytest

from toonrooter.hardware.serial import TransportError
from toonrooter.security.ssh_keys import prepare_key
from toonrooter.testing.rooting import SimulatedRig
from toonrooter.workflow import RootSimulation

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def key(tmp_path):
    return prepare_key(tmp_path / "key")


@pytest.mark.parametrize("boot", ["unsupported", "2010.09", "2010.09-R8"])
def test_full_legacy_simulation(key, boot):
    rig = SimulatedRig(boot_version=boot)
    result = RootSimulation(rig).run(ROOT, key, authorize_install=True, authorize_reboot=True)
    assert result.ssh_verified and "SIMULATED" in result.evidence
    assert rig.install_attempted and rig.rebooted and rig.closed
    assert rig.openocd_started == (boot == "unsupported")
    assert rig.serial.transferred_files["payload/id_rsa.pub"].strip() == key
    for name in ("patch_toon.sh", "dropbear_2015.71-r0_qb2.ipk",
                 "openssh-sftp-server_7.3p1-r10.0_qb2.ipk"):
        assert rig.serial.transferred_files["payload/" + name] == (ROOT / "payload" / name).read_bytes()
    if rig.openocd_started:
        assert rig.jtag_commands == [
            b"soft_reset_halt", b"reset halt",
            b"load_image assets/u-boot.bin 0xa1f00000", b"resume 0xa1f00000"]
    assert rig.serial.commands.index(b"printenv\n") < rig.serial.commands.index(
        b"timeout -t 60 base64 -d | tar zxf -\n")


@pytest.mark.parametrize("failure", [
    "openocd", "identity", "load", "bootloader", "disconnect", "timeout",
    "transfer", "incomplete", "install", "verify", "reboot", "ssh", "interrupt",
])
def test_failure_cleanup_and_no_retry(key, failure):
    rig = SimulatedRig(fail=failure)
    workflow = RootSimulation(rig)
    with pytest.raises((TransportError, OSError, KeyboardInterrupt)):
        workflow.run(ROOT, key, authorize_install=True, authorize_reboot=True)
    assert rig.closed and rig.serial.closed
    with pytest.raises(TransportError):
        workflow.run(ROOT, key, authorize_install=True, authorize_reboot=True)
    if failure in {"openocd", "identity", "load", "bootloader", "disconnect", "timeout", "transfer", "incomplete"}:
        assert not rig.install_attempted
    if failure not in {"reboot", "ssh"}:
        assert not rig.rebooted


@pytest.mark.parametrize("kwargs", [{"hardware": "toon2"}, {"openocd_version": "0.11.0"}])
def test_preflight_stops_before_target(key, kwargs):
    rig = SimulatedRig(**kwargs)
    with pytest.raises(TransportError):
        RootSimulation(rig).run(ROOT, key)
    assert not rig.openocd_started and not rig.serial.writes and rig.closed


def test_scoped_simulation_authorizations(key):
    rig = SimulatedRig()
    with pytest.raises(PermissionError):
        RootSimulation(rig).run(ROOT, key)
    assert not rig.install_attempted
    rig = SimulatedRig()
    with pytest.raises(PermissionError):
        RootSimulation(rig).run(ROOT, key, authorize_install=True)
    assert rig.install_attempted and not rig.rebooted
    with pytest.raises(PermissionError):
        RootSimulation(object())


def test_corrupt_asset_stops_before_io(tmp_path, key):
    import shutil
    for folder in ("assets", "payload"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    (tmp_path / "assets/u-boot.bin").write_bytes(b"wrong")
    rig = SimulatedRig()
    with pytest.raises(ValueError):
        RootSimulation(rig).run(tmp_path, key)
    assert rig.closed and not rig.serial.writes and not rig.openocd_started


def test_simulation_cannot_start_real_processes_or_serial(key, monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("real process"))
    monkeypatch.setattr("toonrooter.hardware.serial.SerialTransport.open",
                        lambda *a, **k: pytest.fail("real serial open"))
    result = RootSimulation(SimulatedRig()).run(
        ROOT, key, authorize_install=True, authorize_reboot=True)
    assert result.ssh_verified


def test_install_password_not_in_transcript(key, monkeypatch):
    monkeypatch.setattr("toonrooter.workflow.secrets.token_hex", lambda n: "secretfixture")
    rig = SimulatedRig()
    result = RootSimulation(rig).run(
        ROOT, key, authorize_install=True, authorize_reboot=True)
    assert b"secretfixture" not in b"".join(rig.serial.commands)
    assert "secretfixture" not in repr(result)


def test_tar_success_is_not_host_hash_verification():
    import base64
    import gzip
    import io
    import tarfile

    from toonrooter.workflow import TRANSFER_STATUS
    # A valid tar with changed contents still exits successfully on the
    # historical decoder/tar pipeline; there is no SHA acknowledgement.
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as tar:
        info = tarfile.TarInfo("payload/changed.txt")
        info.size = 7
        tar.addfile(info, io.BytesIO(b"changed"))
    rig = SimulatedRig()
    serial = rig.serial
    serial.authenticated = True
    serial.output.clear()
    serial.command(b"timeout -t 60 base64 -d | tar zxf -\n")
    wire = base64.encodebytes(gzip.compress(output.getvalue())) + b"\x04\n"
    while wire:
        count = serial.write(wire)
        wire = wire[count:]
    serial.command(TRANSFER_STATUS)
    assert b"TR:TRANSFER:0" in serial.output
    assert serial.transferred_files == {"payload/changed.txt": b"changed"}
