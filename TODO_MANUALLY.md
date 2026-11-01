# Manual tests and remaining work

**Immediate objective: prepare receive-only UART validation; Pi host tests completed.**
The current app is ready for that. It is not yet a live rooting utility.
Commands below assume the Pi checkout at `~/ToonRooter` unless stated otherwise.

## Phase A — Current project readiness

- Complete: Python packaging/CLI and keys (M1-01/02), bounded serial transport
  (M2-01), reviewed boot simulation/assets (M2-02a/b and c-1/2/3), archive/wire
  preparation (M2-03a/b/d), integrated simulation (M2-02d), host deployment candidate
  (M4-01a).
- Incomplete: live boot/JTAG backend and response contracts (M2-02c-4), actual
  receiver/staging (M2-03c), complete safety/verification and physical deployment
  (M3/M4), hardware rooting/backups (M5), activation/local integration (M6).
- **No additional code is required for Pi host-only installation/testing.** Live
  rooting does require more code and physical validation. Do not wait for those to
  complete before running Phases B/C.
- Historical README rooting commands are not the current procedure. Use these guides.

## Phase B — Install and configure the Pi

1. Follow [RPI_INSTALL.md](RPI_INSTALL.md): overwrite the existing microSD with
   **Raspberry Pi OS Lite 64-bit, Trixie**. Set NL Wi-Fi country, `toon-jtag`, your
   user and SSH authentication in Imager. Keep the Toon disconnected.
2. Connect from Manjaro: `ssh <pi-user>@toon-jtag.local` or use its router DHCP IP.
3. Verify `cat /etc/os-release`, `uname -m`, `dpkg --print-architecture`,
   `python3 --version`, `ip -4 address show wlan0`: expect Trixie, aarch64/arm64,
   Python3.13.x and the intended DHCP network. A mismatch blocks the recommended setup.
4. Install system packages/project using the guide. `.venv/bin/toonrooter --help`
   must list seven subcommands. `.venv/bin/python -m pip check` must report no broken
   requirements. A failure blocks application testing, not a reason to connect Toon.
5. Configure UART/disable Bluetooth and serial login as described there. After reboot,
   `readlink -f /dev/serial0` must resolve; `cat /proc/cmdline` must not designate
   that UART as a console. Confirm the corresponding getty is inactive.

## Phase C — Test without the Toon connected

Run all steps as the ordinary Pi user. Do not run `observe` in this phase: its
resource-open behavior belongs to later electrical/UART testing.

### 1. Host and OpenOCD baseline

```sh
cd ~/ToonRooter
git log -1 --oneline
python3 --version
uname -m
openocd --version
openocd -c 'noinit; echo [adapter list]; shutdown'
readlink -f /dev/serial0
cat /proc/cmdline
id
```

Expect Python3.13.x, aarch64, release OpenOCD0.12.0 and `bcm2835gpio` in compiled
adapters. The OpenOCD command does not select an adapter or load a target configuration.
A missing driver/version mismatch blocks JTAG progression, **not** the remaining
host tests. A missing UART/conflicting console blocks later observation/debugging.
Do not launch OpenOCD with the legacy adapter/board `-f` files.

### 2. Assets and local test keys

```sh
.venv/bin/toonrooter asset-audit --repository .
.venv/bin/toonrooter asset-audit --repository . --openocd-scripts /usr/share/openocd/scripts
TEST_DIR=$(mktemp -d "$HOME/toonrooter-test.XXXXXX")
.venv/bin/toonrooter keys --private-key "$TEST_DIR/id_rsa" --encrypt
.venv/bin/toonrooter keys --ssh-public-key "$TEST_DIR/id_rsa.pub"
```

Use the same shell for subsequent `$TEST_DIR` commands. Expected: audits exit 0,
with `live_permitted: false`; key creation prompts for a passphrase, then public
validation succeeds. Keep the private key/passphrase private. The first audit may
report the installed chain unresolved because no installed path was supplied; the
second compares it exactly. If `/usr/share/openocd/scripts` is absent, locate it with
`dpkg -L openocd` and use the directory containing `target/imx27.cfg`.

Asset corruption/missing files block packaging and target use. An installed-script
mismatch blocks that OpenOCD profile pending a diff review; it does not prevent the
in-memory simulation. Do not replace packaged scripts simply to force a match.

### 3. Application diagnostics

```sh
.venv/bin/toonrooter doctor --repository . --serial-port /dev/serial0 --openocd-scripts /usr/share/openocd/scripts --ssh-public-key "$TEST_DIR/id_rsa.pub" > "$TEST_DIR/doctor.json"
printf 'doctor exit: %s\n' "$?"
cat "$TEST_DIR/doctor.json"
.venv/bin/toonrooter probe
.venv/bin/toonrooter probe --jtag
```

Expect JSON with named PASS/FAIL/UNKNOWN/HARDWARE_REQUIRED checks and hardware
readiness `UNVALIDATED`. Doctor exit 1 means failed host checks; inspect individual
items. Exit 0 does not resolve UNKNOWN/HARDWARE_REQUIRED. UART configuration is
currently always UNKNOWN because the app does not interpret all overlay/service
conditions. Target compatibility must remain HARDWARE_REQUIRED.

Default probe exits 0 with a capability message. `probe --jtag` is an intentional
refusal (exit 2), not an installation defect; it starts no target session. Fix genuine
host failures before hardware work, but continue simulation after recording them.

### 4. Payload preparation and complete simulation

```sh
.venv/bin/toonrooter package-payload --repository . --ssh-public-key "$TEST_DIR/id_rsa.pub" --output "$TEST_DIR/payload.tar"
.venv/bin/toonrooter package-payload --repository . --ssh-public-key "$TEST_DIR/id_rsa.pub" --format legacy-base64 --output "$TEST_DIR/payload.b64"
.venv/bin/toonrooter simulate-root --repository . --ssh-public-key "$TEST_DIR/id_rsa.pub" --authorize-simulated-install --authorize-simulated-reboot
```

Expect both local files, exit 0, and a simulation JSON result containing
`SIMULATED ONLY; not hardware validation`, final phase `boot-and-ssh-checked`, and
`ssh_verified: true`. That boolean describes the fixture, not any network login.
Transfer integrity must read `legacy tar exit status only; no target checksum`.
No payload is executed or extracted to the Pi filesystem. Existing output files are refused:
use a fresh test directory on repeats. Any unexpected failure blocks accepting the
host implementation until diagnosed; save the error and commit ID.

### 5. Automated tests and resource cleanup

```sh
.venv/bin/python -m pip install '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/python -m compileall -q toonrooter tests
pgrep -a -x openocd
vcgencmd get_throttled
free -h
df -h /
```

At `d2d2b4e`, expect **135 passing tests**, including the local pseudo-terminal test;
no physical hardware is used. No Ruff/compile errors. A skipped pySerial test means
serial-backend coverage is incomplete; check venv dependencies. Tests failing under
Pi ARM64 need diagnosis before target work. `pgrep` should find no OpenOCD process
(exit 1 means none). Investigate an unexpected process; do not kill unrelated work
blindly. Resolve power/throttling/storage problems before hardware testing.

### Results to share

Copy this checklist and add outputs/errors. Share no private key, passphrase, Wi-Fi
credentials or unnecessary network details. Review logs before sharing.

```text
Date / git revision:
OS / uname -m / dpkg architecture:
Python / OpenOCD versions:
Compiled bcm2835gpio present?:
serial0 resolved path / device group / user groups:
Kernel UART console absent? / matching getty inactive? / hciuart inactive?:
Asset audit / installed-script comparison:
Doctor exit code / FAIL or UNKNOWN items:
Keys / both package formats:
Simulation final phase / evidence string:
pytest result (including skips) / Ruff / compileall:
OpenOCD processes after tests:
get_throttled / free RAM / free storage:
Errors needing review:
```

**Stop here and share results before wiring the Toon.**

## Phase D — Requirements before target operations

| Missing or unverified item | Why it matters | Offline work possible? | Physical testing / blocks |
|---|---|---|---|
| Live backend, M2-02c-4 | CLI cannot start target JTAG/boot sequence | Implement reviewed commands, per-phase consent and response/failure tests | Pi/Toon response validation; blocks live JTAG/rooting, not host tests |
| Pi OpenOCD/GPIO/reset profile | Driver presence does not prove correct electrical timing/reset behavior | Review binary/scripts/driver syntax | Pi host then target tests; blocks JTAG |
| Identification/image compatibility | Expected i.MX27 TAPs and raw image are not device-revision proof | Analyze source/image and match checks | Confirm product/board/TAPs; blocks RAM image execution |
| Actual UART/boot behavior | Prompt timing, password access and terminal modes vary | Improve fixture/protocol coverage | Receive-only capture first; blocks active console workflow |
| Receiver and installer, M2-03c/M3 | Tar success does not check content; original script ignores some errors | Implement practical staging/status, installer fixes and postcondition tests | Check actual tools/mounts/services; blocks persistent install |
| Backup/recovery, M5-02 | No backup CLI, complete flash backup or tested universal rollback | Define accessible files/environment and limited restoration methods | Capture/check actual data before install; no claim of guaranteed recovery |
| Verification, M5-03 | Simulation cannot prove SSH login or independent heating | Implement checks and failure reporting | Normal boot/SSH/touchscreen/heating tests required |

Electrical inspection and later passive UART observation can be prepared before the
live rooting backend is complete. They still require their own reviewed connection
and authorization. Do not make perfect historical provenance an indefinite blocker;
resolve the specific startup/compatibility uncertainties before running the binary.

## Phase E — Prepare the physical Toon connection, later

Target is Toon 1 product `6500-1400-2001`; its exact PCB/firmware is not confirmed.
This is preparation, not an instruction to connect it now.

1. At an authorized session, power down both Pi and Toon before opening or wiring.
   Do not open the boiler or boiler-interface module; this procedure uses the display's
   debug connector. Identify revision-specific screws/latches before opening: the
   repository has no verified teardown guide for this exact product. Do not force it.
2. Locate the 14-position debug header and its pin-1 marking. Confirm PCB revision,
   connector orientation and numbering against a clear board view. Do not infer
   orientation from a photograph of a different revision or from the display position.
3. Validate the following **historical Toon 1** assignments before using them. They
   match the [upstream wiring table](https://github.com/martenjacobs/ToonRooter#how-to-use-it)
   and actual GPIO directives in `assets/adapters/rpi3.cfg`. Pi numbers are physical
   header positions, with BCM numbers supplied to avoid confusion.

| Toon pin | Signal | Pi physical pin | BCM / purpose |
|---|---|---|---|
| 1 | RTCK | Not connected | — |
| 2 | TRST | 24 | GPIO8 |
| 3 | GND | 25 | Ground |
| 4 | TCK | 23 | GPIO11 |
| 5 | GND | 20 | Ground |
| 6 | TMS | 22 | GPIO25 |
| 7 | SRST | 18 | GPIO24 |
| 8 | TDI | 19 | GPIO10 |
| 9 | VT | Not connected | Target voltage reference, not a Pi supply connection |
| 10 | TDO | 21 | GPIO9 |
| 11 | Toon RX | 8 | GPIO14 / Pi TX |
| 12 | Unspecified | Not connected | — |
| 13 | Toon TX | 10 | GPIO15 / Pi RX |
| 14 | GND | 9 | Ground |

The adapter comment naming TRST physical pin 26 conflicts with its GPIO8 directive;
GPIO8 is physical **24**, consistent with upstream. Confirm the header before wiring.

4. Establish compatible 3.3 V logic, common ground and correct signal directions.
   Pi GPIO is not a 5 V or RS-232 interface. Do not connect Pi 5 V/3.3 V supply pins
   to VT, the Toon's supply or boiler-interface wiring. Use separately appropriate
   supplies; confirm power/ground arrangements and avoid back-powering through signals.
5. Inspect continuity/shorts with power off and keep wires short. Recheck before
   powering either device. No simultaneous power-on order is verified here: avoid
   driving an unpowered device, and agree a power/connection plan before proceeding.
   Initial passive observation should use only the confirmed RX/ground path needed.

## Phase F — Controlled rooting sequence, not yet executable

No live root command exists. Do not translate this outline into ad-hoc console commands.

| Step | Current status / evidence required |
|---|---|
| Observe UART and establish debug access | `observe` implemented; electrical/UART behavior awaits validation. Live JTAG disabled |
| Identify hardware/U-Boot | Parsers/reference TAP IDs exist; real product/firmware responses untested |
| Load temporary bootloader only if needed | Image/link checks and simulation exist; live load/reset disabled |
| Obtain Linux shell | Supported U-Boot environment/boot sequence simulated; actual behavior untested |
| Back up relevant state | No CLI; capture boot environment before changes and accessible config/storage with declared coverage |
| Transfer payload | Offline gzip/base64 and simulation work; real receiver/staging still missing |
| Install persistent root access | Requires reviewed installer, prerequisites and explicit per-operation consent; live execution disabled |
| Reboot | Simulation only; never automatically reboot following a failed install |
| Verify | Real SSH authentication, normal touchscreen and autonomous boiler regulation still required |

Prefer an existing supported U-Boot console over loading another image. JTAG reset/
halt and `init=/bin/sh` boot interrupt ordinary thermostat control, even without flash
writes. A RAM bootloader can contain persistent-write code; its behavior must be checked.

## Phase G — Activation and local Home Assistant integration

After confirmed rooting, investigate the
[update-rooted project](https://github.com/ToonSoftwareCollective/update-rooted).
Activation is separate from root access. Audit its current behavior and supported
firmware before use; there is no activation command in this application. Decide
whether activation-only repair or a firmware update is needed, rather than assuming
an update is mandatory.

Then verify touchscreen/heating, establish the supported local API, and configure
Home Assistant at `192.168.2.25`. API endpoints/integration compatibility remain to
be established. Temporary Eneco/Quby/update-server access is allowed during setup.
Afterward disable unnecessary cloud clients and block outbound internet at the router,
while permitting local HA and needed local DNS/NTP. Test internet loss **and** Home
Assistant shutdown: the Toon must continue regulating the boiler autonomously.

## Phase H — Remaining milestones in order

1. **Pi only:** M4-01b/M4-02, run Phases B/C and record host evidence.
2. **Codex/offline:** M1-03 remaining CI/version/failure coverage; M2-02c-4 live
   protocol/backend preparation; M2-03c receiver and installer tests; M3 preflight,
   consent/logging and verification. Use Pi findings to avoid guessing drivers/tools.
3. **Toon hardware, separately authorized:** M5-01 electrical/identity/volatile boot,
   then M5-02 feasible verified backups, then M5-03 approved installation/reboot/heating.
4. **After successful rooting:** M6 activation/update audit and M6 local API/HA/cloud
   isolation, including autonomous-operation tests.

**Next action: flash the existing microSD using RPI_INSTALL.md, then complete Phase C
with the Toon disconnected and share the results checklist.**

## Current next action — 2026-11-01 (supersedes Phases B/C and old next-action text)

**Pi host validation is complete at 718ae8f**; see
[PI3_HOST_VALIDATION](docs/PI3_HOST_VALIDATION.md). Do not reinstall or repeat the
completed host checklist. After installing this development revision, rerun doctor
only to confirm the changed adapter/version diagnostics on the Pi. No target attached.

First physical test, in a separately authorized session:

1. Power off before opening/identifying the display PCB. Confirm product
   6500-1400-2001, PCB revision, header pin 1/orientation and continuity of ground.
   The historical table in Phase E is a reference, not revision-specific confirmation.
2. With an appropriate meter/scope and agreed safe power arrangement, confirm Toon
   TX (historical pin 13) idles near 3.3 V relative to GND (historical pin 14).
   A meter can establish idle DC, not pulse overshoot; inspect signal levels with a
   scope if uncertain. Stop for 5 V, negative/RS-232 levels, uncertain ground or
   connector numbering. Pi inputs are not 5 V tolerant. Never connect VT/supply rails.
3. After the power/connection plan excludes back-powering, use only confirmed Toon
   pin 13 TX -> Pi physical 10 / BCM15 RX, and Toon pin 14 GND -> Pi physical 9 GND.
   Pi TX (physical 8), Toon RX, all JTAG/reset and supply pins stay disconnected.
   Recheck shorts and signal direction. No reset or deliberate power cycle is part
   of this first capture; silence on an already running Toon is inconclusive.
4. Run the supported command:
   `.venv/bin/toonrooter observe --serial /dev/serial0 --timeout 30 --max-bytes 65536`
   Expect timestamped escaped UART bytes at 115200 8N1; possible Linux/U-Boot banner,
   or silence. It makes no software writes and never sends a password or BREAK.
   Opening pySerial sets DTR/RTS inactive, but driver glitches remain possible;
   those lines must not be wired. RX-only wiring avoids a Pi TX path to the Toon.
5. Stop for unexpected reset, display/heating disturbance, power instability,
   abnormal voltage/heat or sustained framing garbage. Retain capture privately;
   boot/environment output may expose identifiers or credentials. Do not infer an
   alternate baud rate, login, reset or JTAG permission from silence.

Next stages need separate authorization: inspect the captured firmware/banner;
prefer supported existing U-Boot console access; review actual environment/macros
before shell boot. If JTAG is needed, review revision-specific wiring/reset levels,
then implement/use an identification-only fixed profile (not yet exposed). The new
Pi3JtagBoot backend combines identification with disruptive initialization; it must
NOT be used as an identification-only probe. Check both TAP IDs before RAM loading.
Then approve the exact historical image's startup risks, run volatile boot validation,
and capture UART. No persistent installation before backups and receiver/tool/mount
inspection. The library has no live install, reboot or SSH verification operation.
