"""Host preparation and explicitly authorized boot operations; no legacy imports."""
import argparse
import getpass
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

from .config import Config
from .hardware.openocd import OpenOCDError, require_safe_jtag
from .hardware.serial import TransportError, finite_timeout


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Toon 1 preparation and authorized temporary-root tools")
    commands = result.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Inspect host only; never opens serial or GPIO")
    doctor.add_argument("--serial-port", type=Path, default=Path("/dev/serial0"))
    doctor.add_argument("--repository", type=Path)
    doctor.add_argument("--openocd-scripts", type=Path)
    doctor.add_argument("--ssh-public-key", type=Path)
    doctor.add_argument("--adapter", choices=["bcm2835gpio", "linuxgpiod"], default="bcm2835gpio")
    simulation = commands.add_parser("simulate-root", help="In-memory legacy workflow; no hardware")
    simulation.add_argument("--repository", type=Path, required=True)
    simulation.add_argument("--ssh-public-key", type=Path, required=True)
    simulation.add_argument("--authorize-simulated-install", action="store_true")
    simulation.add_argument("--authorize-simulated-reboot", action="store_true")
    root = commands.add_parser("root", help="Authorized temporary root shell; no persistent install")
    root.add_argument("--method", choices=["auto", "uart", "jtag"], default="auto")
    root.add_argument("--serial", required=True)
    root.add_argument("--reviewed-environment", type=Path,
                      help="Private reviewed printenv snapshot, including boot_nand and its macros")
    root.add_argument("--repository", type=Path, help="Required for the Pi3 JTAG backend")
    root.add_argument("--timeout", type=float, default=90.0)
    root.add_argument("--authorize-uart", action="store_true")
    root.add_argument("--authorize-boot-arguments", action="store_true")
    root.add_argument("--authorize-shell-boot", action="store_true")
    root.add_argument("--authorize-jtag-reset", action="store_true")
    root.add_argument("--authorize-image-execution", action="store_true")
    root.add_argument("--install", action="store_true", help="Reserved: live install is unavailable")
    root.add_argument("--authorize-install", action="store_true")
    keys = commands.add_parser("keys", help="Prepare local RSA keys; never contacts the Toon")
    keys.add_argument("--private-key", type=Path, default=Path("id_rsa"))
    keys.add_argument("--ssh-public-key", type=Path)
    keys.add_argument("--encrypt", action="store_true", help="Prompt privately for key passphrase")
    observe = commands.add_parser("observe", help="Level 1: receive-only UART capture")
    observe.add_argument("--serial", required=True)
    observe.add_argument("--timeout", type=float, default=30.0)
    observe.add_argument("--max-bytes", type=int, default=65536)
    probe = commands.add_parser("probe", help="Host readiness; live JTAG is disabled")
    probe.add_argument("--jtag", action="store_true")
    audit = commands.add_parser("asset-audit", help="Host-only pinned asset validation")
    audit.add_argument("--repository", type=Path, required=True)
    audit.add_argument("--openocd-scripts", type=Path)
    payload = commands.add_parser("package-payload", help="Host-only archive preparation")
    payload.add_argument("--repository", type=Path, required=True)
    payload.add_argument("--ssh-public-key", type=Path, required=True)
    payload.add_argument("--format", choices=["host-tar", "legacy-base64"], default="host-tar")
    payload.add_argument("--output", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "root":
            from .boot.live import BootAuthorization
            from .boot.native import temporary_root
            from .security.ssh_keys import read_regular
            if args.install or args.authorize_install:
                raise TransportError("Persistent installation is unavailable; no hardware opened")
            authorization = BootAuthorization(
                uart_commands=args.authorize_uart,
                reset_registers_ram=args.authorize_jtag_reset,
                execute_reviewed_image=args.authorize_image_execution,
                boot_linux_shell=args.authorize_shell_boot,
                change_boot_arguments=args.authorize_boot_arguments)
            if not (authorization.uart_commands and authorization.change_boot_arguments
                    and authorization.boot_linux_shell):
                raise TransportError("Require --authorize-uart, --authorize-boot-arguments "
                                     "and --authorize-shell-boot; no hardware opened")
            reviewed = (read_regular(args.reviewed_environment)
                        if args.reviewed_environment is not None else None)
            model_path = Path("/proc/device-tree/model")
            model = model_path.read_text().rstrip("\x00\n") if model_path.is_file() else ""
            result = temporary_root(
                args.serial, authorization, method=args.method, reviewed_environment=reviewed,
                repository=args.repository, model=model, timeout=args.timeout,
                on_open=lambda: print("UART open at 115200 8N1; ready for Toon power-on. "
                                      "No automatic power/reset action. Temporary root only.",
                                      file=sys.stderr, flush=True))
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "simulate-root":
            from dataclasses import asdict

            from .security.ssh_keys import read_regular
            from .testing.rooting import SimulatedRig
            from .workflow import RootSimulation
            result = RootSimulation(SimulatedRig()).run(
                args.repository, read_regular(args.ssh_public_key),
                authorize_install=args.authorize_simulated_install,
                authorize_reboot=args.authorize_simulated_reboot)
            print(json.dumps(asdict(result), indent=2))
            return 0
        if args.command in ("asset-audit", "package-payload"):
            from .assets import audit_configs
            report = audit_configs(args.repository)
            if args.command == "asset-audit":
                from .boot.compatibility import analyze_bootloader
                from .hardware.config_review import review_chain
                report["bootloader"] = analyze_bootloader(args.repository)
                if args.openocd_scripts is not None:
                    report["installed_reference"] = review_chain(
                        installed_scripts=args.openocd_scripts)
                    report["unresolved"] = []
                print(json.dumps(report, indent=2))
            else:
                from .payload import package
                from .security.ssh_keys import read_regular
                data = package(args.repository, read_regular(args.ssh_public_key))
                if args.format == "legacy-base64":
                    from .legacy_wire import prepare_legacy_wire
                    data = prepare_legacy_wire(data).encoded
                fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                print("Local archive verified. No transfer, extraction or execution performed.")
            return 0
        if args.command == "observe":
            from .diagnostics import observe
            finite_timeout(args.timeout)
            if not 0 < args.max_bytes <= 1048576:
                raise ValueError("Invalid capture size")
            return observe(args.serial, timeout=args.timeout, limit=args.max_bytes)
        if args.command == "probe":
            if args.jtag:
                require_safe_jtag()
            print("Level 0 readiness only. Passive UART: observe --serial PATH. "
                  "Live JTAG: disabled; legacy reset handlers modify target state. "
                  "No hardware contacted.")
            return 0
        if args.command == "doctor":
            config = Config(args.serial_port)
            checks = {
                "python_supported": sys.version_info >= (3, 12),
                "cryptography_available": importlib.util.find_spec("cryptography") is not None,
                "pyserial_available": importlib.util.find_spec("serial") is not None,
                "openocd_on_path": shutil.which("openocd") is not None,
                "serial_path_exists": config.serial_port.exists(),
                "serial_permissions": os.access(config.serial_port, os.R_OK | os.W_OK),
            }
            from .deployment import readiness
            from .diagnostics import host_details
            host = host_details()
            report = readiness(serial=config.serial_port, host=host, repository=args.repository,
                               scripts=args.openocd_scripts, key=args.ssh_public_key,
                               adapter=args.adapter)
            print(json.dumps({"host": host, "checks": checks, "deployment": report,
                              "hardware_readiness": "UNVALIDATED",
                              "gpio_adapter": "Metadata only; no GPIO opened"}, indent=2))
            return 0 if all(checks.values()) and not any(
                c["status"] == "FAIL" for c in report) else 1
        from .security.ssh_keys import prepare_key

        password = None
        if args.encrypt:
            password = getpass.getpass("Key passphrase: ").encode()
            if not password:
                raise ValueError("Passphrase must not be empty")
        prepare_key(args.private_key, args.ssh_public_key, password)
        print("RSA public key validated; local key preparation complete.")
        return 0
    except (TransportError, OpenOCDError, PermissionError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted; resources closed.", file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError):
        if args.command == "root":
            print("Temporary-root operation failed: check device/environment paths, permissions "
                  "and timeout. No permanent installation performed.", file=sys.stderr)
            return 2
        print("Preparation failed: check paths, permissions, RSA format, passphrase and key "
              "consistency. Existing keys were not overwritten.", file=sys.stderr)
        return 2
