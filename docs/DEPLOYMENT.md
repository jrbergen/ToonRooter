# Raspberry Pi 3 host deployment

Recommended candidate: Raspberry Pi OS Lite **64-bit, Debian 13 Trixie**, image
dated 6 October 2026. Lite avoids desktop RAM overhead on a Pi3; 64-bit matches its
CPU and modern Python binary wheels. 32-bit may be workable but is not validated.
The official download page lists Pi3 compatibility. Debian Trixie supplies Python
3.13 and OpenOCD 0.12.0. Verify actual Pi repository versions before proceeding:
this procedure has not been run on a physical Pi. Host-only validation is the next gate.

Sources (checked 2026-10-28):
- https://www.raspberrypi.com/software/operating-systems/
- https://packages.debian.org/trixie/python3
- https://packages.debian.org/trixie/openocd
- https://www.raspberrypi.com/documentation/computers/configuration.html

## Install with the Toon disconnected

Use Raspberry Pi Imager to select that Lite image and set hostname toon-jtag,
Wi-Fi country/SSID, a user account and SSH public-key authentication. Keep the
thermostat disconnected during all host setup. After logging into the Pi, run:

```sh
sudo apt update
sudo apt install python3 python3-venv python3-pip openocd git
python3 --version
apt-cache policy openocd python3
git clone https://github.com/jrbergen/ToonRooter.git
cd ToonRooter
./scripts/install-host.sh
.venv/bin/toonrooter --help
.venv/bin/toonrooter doctor --repository . --openocd-scripts /usr/share/openocd/scripts
```

Use a checkout containing these changes; no commit/push is performed automatically.
The installer creates an isolated venv, installs the local project via pip, refuses
root execution and never modifies GPIO/UART/system config. It may download Python
dependencies from the configured index. It does not download/compile OpenOCD.
There are no global pip modifications. Record installed versions with:

```sh
.venv/bin/python -m pip freeze
openocd --version
```

Project Python requirement: >=3.12; deployment target 3.13. CI is configured for 3.12/3.13/3.14, but do not assume the remote CI has run.
Local suites pass on 3.13.12 and 3.14.8; physical Pi installation remains untested.
To install development tools in the same isolated environment:

```sh
.venv/bin/python -m pip install '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

## UART and GPIO host configuration

These manual system changes belong to a separately authorized Pi setup session.
No repository script performs them. With the Toon disconnected, use raspi-config:
serial login shell OFF, serial hardware ON. Inspect /boot/firmware/config.txt and
/proc/cmdline. Keep the kernel command line on one line. It must not designate the
target UART as a console. Do not disable SSH/Wi-Fi connectivity.

For Pi3 PL011 UART use the documented current dtoverlay=disable-bt and enable_uart=1,
and disable hciuart before reboot (sudo systemctl disable hciuart). This disables
Bluetooth, not Wi-Fi. Read the official instructions before applying; do not append
options blindly inside conditional config sections. Do not use legacy pi3-disable-bt
instructions as the production recipe.

After reboot inspect readlink -f /dev/serial0 and ls -l /dev/serial0 /dev/gpiomem
/dev/gpiochip*. Use /dev/serial0 as the stable primary alias, never assume ttyAMA0.
Check id and getent group dialout gpio; grant only required groups if necessary,
then log in again. Do not run the entire application as root to bypass permissions.
Doctor reports access metadata; it does not open UART/GPIO, change pin modes,
inspect waveforms, or prove no userspace process owns the UART.

The initial adapter candidate is bcm2835gpio on Pi3, matching the historical
procedure. Verify the system binary actually lists it. linuxgpiod is an alternative
candidate, not an automatic replacement; no sysfs fallback is enabled.
Bundling the single reviewed target file is useful for source comparison, not proof
that a different binary's compiled reset/examination handlers are compatible.
The release profile check requires 0.12.0 and rejects development builds for review;
distro patch suffixes still need package provenance inspection. Source hashes can
differ due to harmless distro patches: review differences rather than bypass checks.
No target OpenOCD process can currently be launched by the CLI.

## Host-only operational rehearsal

```sh
.venv/bin/toonrooter keys --private-key ./id_rsa --encrypt
.venv/bin/toonrooter doctor --repository . --ssh-public-key ./id_rsa.pub
.venv/bin/toonrooter simulate-root --repository . --ssh-public-key ./id_rsa.pub \
  --authorize-simulated-install --authorize-simulated-reboot
```

This uses only an in-memory serial/JTAG rig. It neither opens a device nor invokes
target shell scripts or SSH. Its receipt checks are synthetic tar/status observations,
not target checksums or hardware success. A failing doctor may be expected on ordinary
Linux development machines. PASS concerns the named host check only; UNKNOWN and
HARDWARE_REQUIRED remain separate. A matching source/release never authorizes rooting.
