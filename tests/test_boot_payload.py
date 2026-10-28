import io
import shutil
import tarfile
from pathlib import Path

import pytest

from toonrooter.assets import audit_configs, validate_inventory
from toonrooter.boot.sequence import BootSequence, SimulatedBootEndpoint, State
from toonrooter.hardware.serial import TransportError
from toonrooter.payload import package, verify
from toonrooter.security.ssh_keys import prepare_key
from toonrooter.transfer import SimulatedReceiver, SimulatedTransfer, TransferState

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def archive(tmp_path):
    return package(ROOT, prepare_key(tmp_path / "key"))


def test_archive_reproducibility_and_permissions(tmp_path, archive):
    key = (tmp_path / "key.pub").read_bytes()
    assert package(ROOT, key) == archive
    assert len(verify(archive)) == 4
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        assert all(m.mode == 0o600 and m.mtime == 0 for m in tar)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "payload/extra.sh",
                                 "payload/id_rsa.pub"])
def test_malicious_archive(archive, name):
    stream = io.BytesIO(archive)
    # Rebuild with extra member (duplicate key rejected too).
    output = io.BytesIO()
    with tarfile.open(fileobj=stream) as original, tarfile.open(fileobj=output, mode="w") as tar:
        for member in original:
            tar.addfile(member, original.extractfile(member))
        info = tarfile.TarInfo(name)
        info.size, info.mode = 1, 0o600
        tar.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(ValueError):
        verify(output.getvalue())


@pytest.fixture
def inventory(tmp_path):
    for folder in ("assets", "payload"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    return tmp_path


@pytest.mark.parametrize("mutation", ["corrupt", "missing", "extra", "symlink", "tcl"])
def test_asset_rejection(inventory, mutation):
    path = inventory / "assets/u-boot.bin"
    if mutation == "missing":
        path.unlink()
    elif mutation == "extra":
        (inventory / "payload/extra").write_bytes(b"bad")
    elif mutation == "symlink":
        path.unlink()
        path.symlink_to(ROOT / "assets/u-boot.bin")
    elif mutation == "tcl":
        with (inventory / "assets/boards/ed20.cfg").open("a") as stream:
            stream.write("\nsource evil.cfg\n")
    else:
        path.write_bytes(b"corrupted")
    with pytest.raises((ValueError, OSError)):
        validate_inventory(inventory)


def test_inventory_policy():
    assert len(validate_inventory(ROOT)) == 9
    for kwargs in ({"hardware": "toon2"}, {"operation": "execute"}):
        with pytest.raises(ValueError):
            validate_inventory(ROOT, **kwargs)
    audit = audit_configs(ROOT)
    assert not audit["live_permitted"]
    assert audit["unresolved"] == ["target/imx27.cfg"]
    assert "mww" in audit["effects"]


RESPONSES = [b"SIM:toon1-imx27", b"SIM:halted",
             b"SIM:loaded:166504:0xa1f00000", b"U-Boot 2010.09 (date)\nU-Boot>",
             b"printenv\r\naddmisc=console\r\nU-Boot>", b"\r\n/ # "]


def test_boot_success():
    endpoint = SimulatedBootEndpoint(RESPONSES)
    sequence = BootSequence(endpoint)
    sequence.validate_host(ROOT)
    for _ in RESPONSES:
        sequence.advance()
    assert sequence.state == State.LINUX_CONSOLE_READY
    assert "SIMULATED" in sequence.evidence
    assert endpoint.closed and len(sequence.history) == 6
    with pytest.raises(TransportError):
        sequence.advance()


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("failure", [b"unexpected", TimeoutError(), KeyboardInterrupt()])
def test_boot_failure_stops_and_cleans(index, failure):
    responses = RESPONSES.copy()
    responses[index] = failure
    endpoint = SimulatedBootEndpoint(responses)
    sequence = BootSequence(endpoint)
    sequence.validate_host(ROOT)
    for _ in range(index):
        sequence.advance()
    with pytest.raises((TransportError, TimeoutError, KeyboardInterrupt)):
        sequence.advance()
    assert sequence.state == State.FAILED and endpoint.closed
    count = len(endpoint.commands)
    with pytest.raises(TransportError):
        sequence.advance()
    assert len(endpoint.commands) == count


def test_initial_state_and_provenance_gate(inventory):
    sequence = BootSequence(SimulatedBootEndpoint([]))
    with pytest.raises(TransportError):
        sequence.advance()
    (inventory / "assets/u-boot.bin").write_bytes(b"bad")
    with pytest.raises(ValueError):
        sequence.validate_host(inventory)
    assert not sequence.endpoint.commands
    with pytest.raises(PermissionError):
        BootSequence(object())


def test_transfer_success(archive):
    receiver = SimulatedReceiver()
    transfer = SimulatedTransfer(receiver)
    transfer.send(archive)
    assert bytes(receiver.buffer) == archive
    assert transfer.state == TransferState.INTEGRITY_VERIFIED
    assert receiver.closed and "SIMULATED" in transfer.evidence
    with pytest.raises(TransportError):
        transfer.send(archive)


@pytest.mark.parametrize("options", [{"corrupt": True}, {"wrong_ack": True}])
def test_receiver_integrity_and_ack_failure(archive, options):
    receiver = SimulatedReceiver(**options)
    transfer = SimulatedTransfer(receiver)
    with pytest.raises(TransportError):
        transfer.send(archive)
    assert transfer.state == TransferState.FAILED and receiver.closed


@pytest.mark.parametrize("error", [OSError("disconnect"), KeyboardInterrupt()])
def test_transfer_interrupted(archive, error):
    receiver = SimulatedReceiver()
    def failed(data):
        raise error
    receiver.write = failed
    transfer = SimulatedTransfer(receiver)
    with pytest.raises((TransportError, KeyboardInterrupt)):
        transfer.send(archive)
    assert receiver.closed and transfer.state == TransferState.FAILED


def test_transfer_deadline_and_prevalidation(archive):
    receiver = SimulatedReceiver()
    transfer = SimulatedTransfer(receiver)
    with pytest.raises(ValueError):
        transfer.send(b"bad")
    assert not receiver.buffer
    with pytest.raises(TransportError):
        transfer.send(archive, timeout=0.001)
    assert receiver.closed


@pytest.mark.parametrize("value", [b"x\nreset", b"`evil`", b"x|sh", b"x&&sh", b"", b"x" * 4097])
def test_boot_command_injection(value):
    from toonrooter.boot.sequence import shell_boot_commands
    with pytest.raises(ValueError):
        shell_boot_commands(value)


def test_boot_command_construction():
    from toonrooter.boot.sequence import shell_boot_commands
    result = shell_boot_commands(b"run foo; console=${console}")
    assert result == b"setenv addmisc run foo\\; console=\\${console} init=/bin/sh\nrun boot_nand\n"
    assert b"saveenv" not in result


def test_archive_trailing_data_rejected(archive):
    with pytest.raises(ValueError):
        verify(archive + b"unverified trailing bytes")


def test_packaging_cli_no_overwrite(tmp_path):
    from toonrooter.cli import main
    prepare_key(tmp_path / "key")
    args = ["package-payload", "--repository", str(ROOT), "--ssh-public-key",
            str(tmp_path / "key.pub"), "--output", str(tmp_path / "payload.tar")]
    assert main(args) == 0
    original = (tmp_path / "payload.tar").read_bytes()
    assert main(args) == 2
    assert (tmp_path / "payload.tar").read_bytes() == original
    assert main(["asset-audit", "--repository", str(ROOT)]) == 0


def test_invalid_manifest(monkeypatch):
    monkeypatch.setattr("toonrooter.assets.MANIFEST", {"schema": 999, "assets": []})
    with pytest.raises(ValueError):
        validate_inventory(ROOT)


def test_unknown_bootloader_version():
    responses = RESPONSES.copy()
    responses[3] = b"U-Boot 2099.01 (date)\nU-Boot>"
    endpoint = SimulatedBootEndpoint(responses)
    sequence = BootSequence(endpoint)
    sequence.validate_host(ROOT)
    for _ in range(3):
        sequence.advance()
    with pytest.raises(TransportError):
        sequence.advance()
    assert endpoint.closed and sequence.state == State.FAILED


def test_archive_symlink_rejected(archive):
    output = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(archive)) as original, tarfile.open(
        fileobj=output, mode="w"
    ) as tar:
        for member in original:
            if member.name == "payload/id_rsa.pub":
                member.type = tarfile.SYMTYPE
                member.linkname = "/etc/passwd"
                member.size = 0
                tar.addfile(member)
            else:
                tar.addfile(member, original.extractfile(member))
    with pytest.raises(ValueError):
        verify(output.getvalue())


def test_receiver_missing_ack_deadline(archive):
    receiver = SimulatedReceiver()
    receiver.read = lambda size: (setattr(receiver, "now", receiver.now + 1) or b"")
    transfer = SimulatedTransfer(receiver)
    with pytest.raises(TransportError):
        transfer.send(archive, timeout=10)
    assert receiver.closed and transfer.state == TransferState.FAILED
