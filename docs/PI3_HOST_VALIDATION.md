# Raspberry Pi 3 host validation

User-reported real execution, recorded 2026-11-01. Validated revision `718ae8f`
on `py3-modernize`; earlier integration milestone `d2d2b4e`. This validates this
installation only, not every Pi/Toon combination. No Toon was contacted.

- Pi 3 Model B Rev 1.2, `toon-jtag`, user `pi`, Ethernet DHCP `192.168.2.27`.
- Raspberry Pi OS Lite64 / Debian 13 Trixie 13.7, kernel
  `6.18.50+rpt-rpi-v8`, aarch64/arm64; Python 3.13.5.
- Checkout `/home/pi/ToonRooter`, environment `.venv`; Stretch overwritten.
- `/dev/serial0` -> `/dev/ttyAMA0`; kernel `console=tty1`, no active serial
  getty, hciuart inactive. User in dialout/gpio. Serial access passed.
  gpiomem and gpiochip0/1/2 plus gpiochip4 alias present.
- Distro OpenOCD package `0.12.0+rpt20250909.cd4873400-1`; runtime
  `Open On-Chip Debugger 0.12.0+dev-snapshot (2026-02-16-16:07)`.
  `openocd -c 'noinit; echo [adapter list]; shutdown'` succeeded and listed
  bcm2835gpio, sysfsgpio, linuxgpiod. No compilation or GPIO initialization.
- Both asset-audit forms passed, including `/usr/share/openocd/scripts`.
  Installed imx27.cfg matched the reviewed chain: ARM926EJS, CPU `0x07926121`,
  ETB `0x1b900f0f`. Reset handlers write registers/RAM; match is not execution approval.
- `scripts/install-host.sh` succeeded: ToonRooter 0.1.0, cryptography 50.0.2,
  pySerial 3.5, cffi 2.1.1. pip check reported no broken requirements.
- Passphrase-protected RSA creation/public validation and both local payload formats
  passed independent verification. No transfer, extraction or execution.
- simulate-root completed all eleven phases from host-validated to
  boot-and-ssh-checked, with both simulated authorizations. Output explicitly said
  `SIMULATED ONLY; not hardware validation`. ssh_verified was synthetic;
  transfer evidence was only legacy tar exit status, no target checksum.
- Initial ARM64 tests: 134 passed, one failed. test_doctor_never_opens_devices
  wrongly forbade subprocess opening /dev/null. Commit `718ae8f` permits that
  host descriptor while still rejecting unexpected opens. Final full suite:
  **135 passed in 134.05 seconds, no skips**; Ruff passed.
- `vcgencmd get_throttled`: `throttled=0x0`; no lingering OpenOCD process.

Doctor defects found: overly restrictive release-only profile; batch adapter query
omitted echo and showed banners rather than the returned list. Fixed in the next
local development milestone; those changes have not yet been rerun on the Pi.

UART traffic, GPIO signaling, JTAG/reset timing, exact Toon PCB/firmware, bootloader
startup and persistent side effects remain unvalidated. Historical image provenance
is incomplete. No real payload/SSH/heating test occurred. Next: electrical inspection
and separately authorized receive-only UART capture, not another OS installation.
