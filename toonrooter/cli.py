"""Host-only CLI; never imports the legacy Rooter."""
import argparse
import getpass
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

from .config import Config


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Toon 1 preparation tools (hardware disabled)")
    commands = result.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Inspect host only; never opens serial or GPIO")
    doctor.add_argument("--serial-port", type=Path, default=Path("/dev/serial0"))
    keys = commands.add_parser("keys", help="Prepare local RSA keys; never contacts the Toon")
    keys.add_argument("--private-key", type=Path, default=Path("id_rsa"))
    keys.add_argument("--ssh-public-key", type=Path)
    keys.add_argument("--encrypt", action="store_true", help="Prompt privately for key passphrase")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
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
            print(json.dumps({"checks": checks, "hardware_readiness": "UNVALIDATED",
                              "gpio_adapter": "NOT CHECKED; no GPIO opened"}, indent=2))
            return 0 if all(checks.values()) else 1
        from .security.ssh_keys import prepare_key

        password = None
        if args.encrypt:
            password = getpass.getpass("Key passphrase: ").encode()
            if not password:
                raise ValueError("Passphrase must not be empty")
        prepare_key(args.private_key, args.ssh_public_key, password)
        print("RSA public key validated; local key preparation complete.")
        return 0
    except (OSError, ValueError, TypeError):
        print("Preparation failed: check paths, permissions, RSA format, passphrase and key "
              "consistency. Existing keys were not overwritten.", file=sys.stderr)
        return 2
