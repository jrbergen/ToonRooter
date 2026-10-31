# Raspberry Pi 3 installation advice

## Recommended image

Install **Raspberry Pi OS Lite (64-bit), Debian 13 Trixie** on the existing microSD.
This replaces Stretch completely. No Python 2 compatibility is needed.

The [official downloads](https://www.raspberrypi.com/software/operating-systems/)
list 64-bit support for Pi 3. Lite avoids desktop RAM overhead on the 1 GB machine.
Trixie's default Python is [3.13](https://packages.debian.org/trixie/python3), meeting
this project's >=3.12 requirement; its packaged [OpenOCD is 0.12.0](https://packages.debian.org/trixie/openocd).
Record actual installed versions, since package revisions can differ.

The Pi host is ARM64; the raw ARM bootloader and `qb2` IPKs run on the **Toon**, not
as Pi programs. Their presence does not require a 32-bit Pi OS. Their target
compatibility and actual Pi GPIO/reset behavior remain unverified.

## 1. Flash from Manjaro and boot headlessly

1. Download the Linux x86_64 Raspberry Pi Imager from the
   [official software page](https://www.raspberrypi.com/software/). Run the supplied
   Linux application, following its instructions. Do not use Debian apt commands on Manjaro.
2. Select Raspberry Pi 3 and **Raspberry Pi OS Lite (64-bit), Trixie**, not Legacy
   or a desktop edition. Insert the existing microSD and select it as storage.
   Check the selected device carefully: writing erases it.
3. In Imager customisation, set hostname `toon-jtag`, username `<pi-user>`, your
   chosen login credentials, Wi-Fi SSID `<wifi-ssid>`, Wi-Fi password, and country
   **Netherlands / NL**. Use a Pi3-compatible Wi-Fi network, preferably 2.4 GHz.
4. Enable SSH, preferably using your Manjaro user's public SSH key. Set credentials
   in Imager, not in project files. Leave networking on DHCP.
5. Write and verify, eject the card, insert it into the Pi and power the Pi from a
   suitable stable supply. **Keep the Toon disconnected.** Allow first boot to finish.
6. On Manjaro, connect (replace the username):

   ```sh
   ssh <pi-user>@toon-jtag.local
   ```

   If `.local` does not resolve, find its DHCP address in the router and use
   `ssh <pi-user>@<pi-dhcp-address>`; expect the `192.168.2.0/24` network.
   A reflash changes the SSH host key. If warned, verify the new host/address, then
   remove only that old known-host entry with `ssh-keygen -R toon-jtag.local`
   (or the exact IP used), and reconnect.
7. On the Pi, check:

   ```sh
   cat /etc/os-release
   uname -m
   dpkg --print-architecture
   python3 --version
   hostname
   ip -4 address show wlan0
   ip route
   ```

   Expect Trixie, `aarch64`, `arm64`, Python 3.13.x, `toon-jtag`, a DHCP address
   in the intended subnet and a default route. Correct a wrong image now.

## 2. Install the host tools

All remaining commands run on the Pi, as the normal user unless prefixed with sudo.

```sh
sudo apt update
sudo apt install python3 python3-venv python3-pip openocd git
apt-cache policy python3 openocd
openocd --version
git clone https://github.com/jrbergen/ToonRooter.git
cd ToonRooter
git log -1 --oneline
./scripts/install-host.sh
.venv/bin/python -m pip check
.venv/bin/toonrooter --help
```

The checkout must contain `d2d2b4e` or a later reviewed version. If the fork has not
been pushed, transfer the current development checkout from Manjaro instead; do not
mistake an older remote checkout for this application. For example, from Manjaro:

```sh
rsync -av --exclude=.venv --exclude=.idea --exclude=build --exclude=dist \
  /home/jrb/pycharmprojects/ToonRooter/ <pi-user>@toon-jtag.local:~/ToonRooter/
```

Then run the installer in that directory on the Pi. It checks Python >=3.12, creates
`.venv`, and installs the local package and dependencies (`cryptography`, `pyserial`).
It refuses root execution and does not change UART/GPIO or system settings. It uses
pip's configured index; no system-wide pip install or OpenOCD compilation is involved.
After later source changes, rerun the installer: a normal installation is not editable.

**Start with the distro OpenOCD package.** Building from source is not currently
justified. The CLI checks a release-0.12.0 profile and compiled adapter presence;
if these fail, collect results for review rather than installing a random development
build. The small bundled target configuration is for source comparison, not an
instruction to launch the legacy board configuration.

## 3. Prepare UART and check GPIO

Do this with no Toon wiring attached. The current
[official UART configuration instructions](https://www.raspberrypi.com/documentation/computers/configuration.html#configure-uarts)
use `/boot/firmware/config.txt` and the `disable-bt` overlay.

1. Run `sudo raspi-config`. Under Interface Options / Serial Port, disable the serial
   login shell and enable serial hardware. Reboot when the following edits are complete.
2. Edit `sudo nano /boot/firmware/config.txt`. In an applicable section (for example
   `[all]`), ensure these settings are present once:

   ```ini
   enable_uart=1
   dtoverlay=disable-bt
   ```

3. Run `sudo systemctl disable hciuart`, then `sudo reboot`. This frees the PL011
   UART from Bluetooth; Wi-Fi remains usable. If hciuart is absent, record that and
   inspect the installed Bluetooth setup rather than creating a service.
4. Reconnect and check the alias and consumers:

   ```sh
   readlink -f /dev/serial0
   ls -l /dev/serial0
   cat /proc/cmdline
   systemctl is-active hciuart
   systemctl list-units --all 'serial-getty@*'
   id
   ls -l /dev/gpiomem /dev/gpiochip*
   ```

   Do not assume `ttyAMA0`: use the resolved device to inspect any serial-getty
   instance. It must not be active on that UART; the kernel command line must not
   use that UART or `serial0` as a console. If necessary disable the **identified**
   instance, e.g. `sudo systemctl disable --now serial-getty@ttyAMA0.service` only
   when the alias actually resolves there. Do not remove unrelated console settings.
5. If permissions require it, check `getent group dialout` and `getent group gpio`,
   then add your user to existing required groups:
   `sudo usermod -aG dialout,gpio "$USER"`. Log out and back in. If a group/device is
   absent, inspect ownership/udev rules instead of using chmod 777 or running as root.

The historical Pi3 adapter uses OpenOCD `bcm2835gpio`, not Python GPIO libraries.
It maps GPIO registers; device access depends on the installed driver/build.
`linuxgpiod` is an alternative under review, not a validated replacement.
[OpenOCD's adapter documentation](https://openocd.org/doc-release/html/Debug-Adapter-Configuration.html)
describes the distinction. Listing GPIO files does not test their signals.

## 4. Verify and troubleshoot

Continue with Phase C in [TODO_MANUALLY.md](TODO_MANUALLY.md). No application code
changes are required before host-only testing; physical Pi validation is still pending.

| Problem | Action |
|---|---|
| No Wi-Fi/SSH | Recheck Imager Wi-Fi country/credentials, router DHCP lease and SSH settings; try IP instead of `.local` |
| No `/dev/serial0`, wrong mapping | Recheck raspi-config, applicable config section, overlay and reboot; do not substitute a guessed tty |
| Missing OpenOCD driver/version mismatch | Save version and adapter-list output; blocks JTAG progression, not packaging/simulation; do not compile blindly |
| Permission denied | Check device owner/group and new login membership; do not run ToonRooter with sudo |
| Python import/install failure | Check `.venv/bin/python --version` and pip check; rerun installer; retain full error output |
| Wrong architecture | `uname -m` and dpkg architecture should be aarch64/arm64 for this recommendation |
| Slow install/out-of-memory | Use Lite, close unnecessary processes; inspect `free -h`, `df -h`, and kernel OOM messages; avoid parallel source builds |
| Unstable Pi | Check power/cable and `vcgencmd get_throttled`; nonzero flags can record current or past throttling/undervoltage. Resolve before target tests |

No installation command here opens a target debug session or roots the Toon.
