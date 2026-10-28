# Architecture and evidence
Baseline: 4035537edf77e6b4fc2d89525fd7d0c08cd284bc, initially clean.
Reviewed all tracked text sources, adapter/board configurations, recent history,
binary sizes/hashes and IPK control/data inventories without executing target code.
Original entry point is retained in Git; rooter.py and sshkeys.py remain legacy evidence.
Commit 6da0b46 introduced an explicitly untested key overwrite check.

## Original execution
1. CLI autodetects Pi using a finite revision lookup, even if JTAG is not requested.
   Opens UART at 115200, default /dev/serial0; default serial timeout is unlimited.
2. Waits indefinitely for U-Boot version. Known passwords for 2010.09, R6, R8.
3. Otherwise starts openocd with /usr/share/openocd and relative adapter and board paths.
   Sleeps ten seconds, connects telnet localhost:4444; sends soft_reset_halt,
   reset halt, load_image assets/u-boot.bin 0xa1f00000, resume 0xa1f00000.
4. Board sources target/imx27.cfg. gdb-attach resets/init; reset-init invokes ed20_init.
   This resets, changes GPIO/clock/AIPS/SDRAM registers and CPU mode. It is not read-only.
   Pi3 bcm2835gpio base 0x3F000000, 500 kHz; BCM TCK/TMS/TDI/TDO 11/25/10/9,
   TRST 8, SRST 24 (physical 23/22/19/21, 24/18); reset_config none.
5. UART password then U-Boot> prompt. printenv extracts addmisc, setenv adds init=/bin/sh,
   escaping dollars and semicolons; run boot_nand starts Linux shell.
   No saveenv or explicit NAND write found in Python path. Environment change appears
   volatile, not a guarantee about all bootloader side effects.
6. At / # prompt, base64 streams gzip tar into timeout -t 60 base64 -d | tar zxf -.
   No checksums, exit status or verified completion. Temporary descriptor is leaked.
7. Runs payload/patch_toon.sh with weak random password, consumes prompts, optionally
   rm -r payload and /etc/init.d/reboot even following a caught exception.

## Persistent payload inventory
patch_toon.sh creates missing /dev/urandom; copies /etc/passwd.preroot and
/etc/default/iptables.conf.preroot once; replaces root password using DES crypt;
adds INPUT accept rules for TCP 22/80/10080; comments VPN entry in /etc/inittab;
installs bundled IPKs; appends authorized_keys repeatedly without permissions enforcement.
Dropbear IPK writes /etc/default/dropbear, /etc/init.d/dropbear,
/usr/sbin/dropbearmulti and related links/tools, /usr/bin/dbclient, /etc/dropbear.
Postinst changes ssh/scp alternatives and update-rc.d startup links. Removal scripts
stop service and delete host keys. Init script/runtime behavior needs deeper audit.
SFTP IPK writes /usr/libexec/sftp-server, requires glibc >=2.10.1; no postinst.
Payload erroneously calls dropbear.postinst for SFTP failure. Package failures other
than code 255 can be ignored. No transaction or complete rollback exists.

## Binary provenance
u-boot.bin: 166504 bytes, SHA256
5ff62c31c19265eff1160169c60594335ea727174002f667d9344ea9cb7882e0.
README credits community authors; reproducible source/build mapping unconfirmed.
Dropbear SHA256 e097a7db067f9fee3402238202e7b3d15a5f009fdb2235d60c85d7ac6eb5c0e0;
SFTP SHA256 b736f8d5214c515f6bf3b12d174c13c3a10aad85682b040b5f8b8db7dc2fdd33.
Package metadata lists OpenEmbedded sources, build unknown. Hashes identify assets,
not their trustworthiness. Machine-code behavior is not established by inspection.

## Modern boundary
CLI -> configuration / local diagnostics / RSA lifecycle only. No device is opened.
Future transport -> bounded byte protocol -> explicit operation orchestration.
probe, backup, root, verify, boot-console, configure-local and restore are deliberately
not exposed until implemented and tested. No simulated hardware success claims.

## External evidence and deployment direction (2026-10-28)
- https://github.com/martenjacobs/ToonRooter/issues/26 reports Pi3/Stretch rooting of
  an unactivated Toon1, then updater-assisted setup. This is one report, not proof for
  product 6500-1400-2001 or unknown firmware.
- https://github.com/ToonSoftwareCollective/update-rooted documents VPN firmware updates
  and -f fix-only mode. Activation without upgrade still requires source audit.
- https://www.raspberrypi.com/software/operating-systems/ lists Trixie/Debian13 Lite
  and Pi3-compatible 64-bit images. Proposed host: Lite 64-bit; hardware unvalidated.
- https://github.com/ToonSoftwareCollective/ToonRooter and
  https://github.com/ToonSoftwareCollective/Root-A-Toon remain comparison tasks.
Python declared >=3.12; exercised 3.14.8 only. Trixie Python package version and
3.12/3.13 dependency/install matrix remain to verify. Bookworm's older Python is
not the target. Modern GPIO driver selection, UART overlays (/boot/firmware),
console/Bluetooth conflicts and signal compatibility require official-doc research
and Pi-only validation before deployment instructions can be called tested.
Do not substitute a new GPIO driver based only on compilation.

## Activation and autonomy
Rooting grants access; it does not activate the thermostat. Updater script contents,
firmware prerequisites, local API endpoints and Home Assistant behavior remain unverified.
Later gates: preserve autonomous heating through network/HA failure; permit HA
192.168.2.25 and local DNS/NTP; test router outbound isolation after setup.
No cloud shutdown or firmware update is implemented.

## Second implementation session: diagnostic levels and protocol boundary
Level 0 doctor now enumerates serial metadata, GPIO device names, model, OS/architecture
and runs only fixed OpenOCD --version / noinit; adapter list; shutdown queries.
The latter reports compiled drivers, not functional adapter compatibility. It never
selects an adapter, loads config, or requests init. Default probe reports readiness only.
Level 1 observe requires an explicit absolute device; opens closed pySerial with
DTR/RTS inactive before open, all flow control disabled, no BREAK or write call.
UART fixed at documented 115200 8N1; no dynamic changes. Software receive-only is
not physical isolation: use a validated RX/GND-only connection if appropriate.
Drivers may glitch lines on open; no electrical noninterference claim.
See https://pyserial.readthedocs.io/en/latest/pyserial_api.html (open/RTS/DTR caveats).
Capture capped at 1 MiB and 3600 seconds, default 64 KiB/30 seconds. Output escapes
terminal controls; captured bytes may contain device secrets, so do not publish blindly.
No capture file option yet. Timestamps are per received chunk.
Level 2 JTAG remains disabled: every legacy adapter uses bcm2835gpio with reset pins;
ed20.cfg:20 sources external target/imx27.cfg not included/pinned in this repository.
ed20.cfg:21-22 reset-init/gdb-attach hooks and :34-117 initialization writes preclude
using this board configuration for conservative identification. Nested script audit
cannot be completed against an unspecified system OpenOCD installation.
Level 3 remains disabled even with confirmation/compatibility flags in safety policy.
No new bootloader transfer, memory write or payload executor exists.

SerialTransport has injectable byte device and monotonic clock, partial writes,
bounded reads/writes, context cleanup and receive-only rejection.
UBootSession supports prompt synchronization and explicit interactive printenv only;
no generic commands. Standalone U-Boot> plus idle read is a synchronization heuristic,
not proof against deliberately crafted/delayed output. environment requires command
echo and addmisc evidence; unsupported prompts time out. Hardware firmware command
behavior remains unverified. Transcript stores bounded timestamp/direction/size metadata
only, never response content. Returned environment bytes remain sensitive.
OpenOCD runner merges stdout/stderr, uses selectors and a bounded buffer, finite
deadline, new process session and kill/reap in finally. No arbitrary Tcl/config paths.
See https://openocd.org/doc/html/Debug-Adapter-Configuration.html for adapter list;
built-in driver presence is distinct from real GPIO/target validation.

## M2-02/M2-03 host implementation (third session)
Current baseline master a7271f9; prior user commits retained. New modules:
assets.py/data/assets.json, boot/sequence.py, payload.py, transfer.py.
asset-audit and package-payload are host-only CLI commands. Installation includes
the inventory JSON, but original assets must be supplied via --repository.
Hashes bind identity only; all assets remain unreproduced-legacy/inventory-only.
The only binary bootloader is raw u-boot.bin. file reports "data"; embedded string
is U-Boot 2010.09 (Feb 15 2017 - 18:17:02). Added in a25023f048f6d61e69e416f9e67ab247a21c97a9.
No ELF architecture metadata or reproducible source/build mapping identified.
imx27/ARM compatibility is source-derived from ed20.cfg and legacy address, not
binary-format proof. Execution requests are rejected even for matching hashes.
Config inventory pins every original adapter/board byte. Static audit reports the
known external include and effects; it does not evaluate Tcl or discover arbitrary
dynamic includes. Unknown hash/directive fails inventory validation. External
target/imx27.cfg remains unresolved; live config chain approval is impossible here.

### Reviewed legacy sequence and proposed finite simulation contracts
References: rooter.py:56-126,196-234; ed20.cfg:20-117.
Each transition requires the previous state; no retries; failed exchange -> FAILED,
closes endpoint, prohibits continuation. Successful history stores state/kind/size only.
All current boot transitions are SIMULATED, never hardware validation.
| Stage | Purpose/prerequisite | Evidence / proposed deadline | Effects / recovery |
|---|---|---|---|
| Host validation | pinned inventory before any exchange | all assets/paths/hash/size match | host-only; repair inputs and restart |
| Identify | Toon1 i.MX27 only | simulator explicit identity / 10s | real attach effects unknown; live disabled |
| JTAG init | legacy soft_reset_halt; reset halt | simulator halted / 10s | halt/reset/register init; heating interrupted; no automatic retry |
| RAM load | initialized SDRAM; load_image at 0xa1f00000 | simulator exact length/address / 10s | RAM write; provenance unknown; reboot recovery unverified |
| Resume/console | loaded image | supported U-Boot version and standalone prompt / 10s | target execution; legacy password step not executed by simulator |
| Environment inspection | known prompt | echoed printenv, unique nonempty addmisc and prompt / 10s | active UART command; no saveenv; output never logged |
| Shell boot | inspected addmisc | simulator exact Linux prompt / 10s | escaped setenv addmisc + init=/bin/sh, run boot_nand; heating services bypassed |
Timeouts above are proposed bounds passed to deterministic simulation exchanges,
not measured hardware timings. Simulator identity/load/halt acknowledgements are
explicit synthetic contracts, not OpenOCD output parsers. No live executor exists.
Command construction rejects unsupported addmisc syntax instead of guessing escaping.
The physical sequence still requires source/firmware/config and hardware review.

### Payload packaging and simulated transfer
Host packaging validates exact original script/IPKs plus supplied RSA public key.
USTAR archive uses sorted regular files, uid/gid/mtime zero, mode 0600 (script invoked
with sh, not executable bit). Names remain payload/* including id_rsa.pub. Manifest
records length/mode/SHA256. No extraction or execution. Independent verification
checks pinned payload hashes and canonical archive bytes; no self-manifest-only trust.
Path checks reject traversal and symlinks; bounds are 1 MiB per asset/archive.
Local repository mutation during validation is not a supported adversarial trust boundary.

Transfer is a simulation-only binary framing experiment: TRSIM1 length SHA256,
bounded archive bytes, explicit VERIFIED length SHA256 response. This receiver does
not exist on Toon; no claim of legacy compatibility. It exercises SerialTransport's
actual partial-write loop, deadlines and disconnects against an in-memory receiver.
No shell interpolation, target filesystem writes, tar extraction or executable step.
States: PREPARED -> STARTED -> COMPLETED -> INTEGRITY_VERIFIED; errors -> FAILED.
Execution/installation states are defined but unreachable; successful transfer != root.
Legacy transfer uses base64/timeout/tar without checksum. A future real receiver
must establish available sha256/base64/timeout utilities, echo/canonical settings,
storage mount (RAM vs persistent), free space, cleanup and extraction behavior.
Toon shell requirements also include BusyBox ash extensions ([[ ]]), mknod, sed,
openssl DES crypt, opkg, update-rc.d. These are not assumed on unknown firmware.
Modern Pi differences remain unresolved: bcm2835gpio peripheral bases and old
adapter_khz syntax are historical, not a validated modern GPIO implementation.

## M2-02c reference review and decisions — 2026-10-28
This supersedes earlier statements that no nested reference could be resolved.
It does NOT establish the configuration of any installed OpenOCD or real device.

### Complete reference chain and binary evidence
Original adapter/rpi3.cfg -> boards/ed20.cfg -> target/imx27.cfg.
Retrieved unmodified OpenOCD v0.12.0 target/imx27.cfg to
toonrooter/data/openocd-0.12.0/target/imx27.cfg; GPL-2.0-or-later COPYING/NOTICE
included. Source/hash are in data/openocd-review.json. It has no further includes.
review_chain compares exact bytes, optionally against an installed scripts directory.
It never evaluates Tcl. Compiled OpenOCD C handlers/startup interpreter are not pinned.
CLI asset-audit --repository . --openocd-scripts /usr/share/openocd/scripts
uses the actual host directory, with no OpenOCD process or device access.

Critical ordering: target sets trst_and_srst srst_pulls_trst AFTER adapter reset_config
none. Assuming adapter reset policy remains effective was incorrect. Source review
establishes intent, not measured signaling. Defaults: little-endian ARM926EJ-S,
ETB TAP 0x1b900f0f, CPU TAP 0x07926121, IR length 4.
Conditional CHIPNAME/ENDIAN/ETBTAPID/CPUTAPID overrides must be controlled by a future
executor. Work area virtual/physical 0xffff4c00, size 0x8000, backup enabled;
DCC downloads and ETM/ETB debug setup. Work-area backup is not a target backup.
Board defines NAND/HWECC; definition is not an erase/program command. Board reset
hooks write GPIO/AIPS/clocks/SDRAM/CPU state. No explicit flash write in bootstrap
Python/OpenOCD source. Examination and compiled reset code still need validation.
Source: https://raw.githubusercontent.com/openocd-org/openocd/v0.12.0/tcl/target/imx27.cfg

Binary unchanged, 166504 bytes, hash recorded earlier. At 0x00: ea000012 then seven
e59ff014 words; at 0x40/0x44: a1f00000/a1f00000. These strongly indicate raw
little-endian ARM exception vectors/link address, not ELF metadata/full disassembly.
analyze_bootloader checks signatures/address plus pinned hash, i.MX27 CPU text and
2017 U-Boot version string. Bootcmd string runs boot_nand; boot_nand runs argument
macros then NAND read and bootm. NAND write/erase/BBT routines are present too.
Presence does not prove execution, but RAM loading cannot establish absence of
persistent side effects. Exact source/build, board revision and BBT startup behavior
remain unknown. No replacement binary is justified. Perfect provenance is not an
unconditional development blocker: examine actual runtime risks before authorized HIL.

### Behavioral and alternative decision record
| Concern | Historical behavior | Decision / current implementation | Evidence, assumptions and tests |
|---|---|---|---|
| Existing console | Password access before JTAG | Preserve preference; plan_route avoids resets/RAM image after supported access established | rooter.py:56-92; banner != authentication; route tests |
| Unsupported firmware | JTAG RAM U-Boot fallback | Retain design, live disabled | Issue26 reports successful comparable setup, not this device |
| Initialization | soft_reset_halt then reset halt | Preserve reference until measurements justify removing either | rooter.py:213-218, ed20_init; removing reset may break SDRAM setup |
| Shell boot | unsaved addmisc with init=/bin/sh, boot_nand | Preserve principle | Inspect real macros first; current synthetic batch simulator omits passwords/individual acknowledgements; not production protocol |
| GPIO | bcm2835gpio direct memory access, old adapter_khz syntax | Evaluate updated bcm2835gpio and linuxgpiod on Pi, defer replacement | Official OpenOCD supports both; no measured Toon superiority |
| USB adapter | Board comments report JLink use | Credible fallback, defer | Voltage/reset wiring/new adapter tests needed; new cost/setup |
| NFS recovery | Community ToonRecovery boots recovery environment | Defer as diagnostic alternative | More image/network dependencies; not verified rollback |
| Network exploit | Legacy Root-A-Toon services | Defer for supplied firmware | User observed no legacy-port fallback; no invented exploit |
| Persistent SSH | Bundled IPKs and edits | Retain reference, do not deploy blindly | Actual existing services/tools/space unknown; reuse sshd only if identified |
| Archive | gzip tar over base64 | Preserve host integrity checks, adapt wire format | Prior host tar alone incompatible with tar zxf; round-trip tests added |
| Receiver checks | Prompt only, no checksum/status | Improve optional capability negotiation next | No unsupported sha256sum requirement |
| TRSIM1 | No historical equivalent | Keep isolated synthetic test, excluded from live plan | No Toon receiver exists; not evidence of real transfer/extraction |

Recommendation: existing supported U-Boot console first; otherwise historical JTAG
RAM-U-Boot is the strongest supported hardware fallback. No evidence supports replacing
image/SoC initialization with a novel method. Improve acknowledgements/staging first.
Sources:
https://github.com/martenjacobs/ToonRooter/issues/26
https://github.com/ToonSoftwareCollective/ToonRecovery
https://openocd.org/doc-release/html/Debug-Adapter-Configuration.html
Official docs describe bcm2835gpio direct-register access, linuxgpiod character-device
bitbanging and deprecated sysfs GPIO. Prefer evaluating linuxgpiod over reviving sysfs,
but compilation or a newer interface proves neither electrical safety nor Toon timing.

### Payload and practical transfer findings
Inspected bundled Dropbear IPK init/default without execution. Init requires awk,
start-stop-daemon, dropbearkey and /proc/mounts; selects /var/lib/dropbear on read-only
root, /etc/dropbear otherwise, generates missing/empty RSA host keys, and skips
startup if /var/service/dropbear exists. Defaults can supply extra server arguments.
Postinst alternatives/update-rc.d and existing daemons may conflict. Removal scripts
delete host keys. Existing nonempty host keys are normally preserved by init.
patch_toon.sh duplicates authorized_keys, regenerates password, makes non-atomic sed
edits and calls the wrong postinst for SFTP failure. Copies cover two files only.
A replacement installer must first identify actual tools, sshd and opkg state.
Do not assume modern utilities, systemd, rename durability or package rollback.

legacy_wire.prepare_legacy_wire verifies host bundle, removes host-only manifest,
emits deterministic gzip USTAR plus 76-column base64.encodebytes matching legacy
base64.encode. It returns original receiver command as inert bytes only.
package-payload --format legacy-base64 writes this representation locally.
This proves host format equivalence, NOT target receipt. Historical fixed 60-second
timeout, UART echo/canonical handling, Ctrl-D semantics, root mount/free space and
BusyBox capabilities remain unverified. Direct extraction into / is not adopted.
Next receiver design should stage on a confirmed mount and capture explicit status,
negotiate available checksum/byte count, and stop before extraction/execution on failure.
Do not require installing a receiver or new SHA256 utility merely for design elegance.

### Separately authorized hardware-validation stages
No stage executed. Stop on unexpected identity/reset, wiring uncertainty, timeout,
checksum mismatch, heating failure or failure to restore normal boot.
| Stage | Expected observation / possible effects | Stop/recovery |
|---|---|---|
| 1 Pi host | OS/Python/OpenOCD/drivers and UART conflicts inspected | Fix host offline; no target attached |
| 2 Electrical/UART | Verified voltage/wiring, passive banner; open may glitch lines | Stop/disconnect powered-down if unsafe; no reset just to obtain banner |
| 3 JTAG identity | Reviewed adapter, expected TAPs; attach may change debug state | Stop unknown IDs/reset; no automatic init |
| 4 Initialization | Authorized halt/reset, exact OpenOCD results recorded | Heating suspended; reboot recovery remains unverified |
| 5 Volatile boot | Exact image length/address verified, supported UART banner | Stop mismatch; no flash writes; recovery still uncertain |
| 6 Linux console | Verified shell and boot macros | init=/bin/sh bypasses thermostat services |
| 7 Backups | Environment/files/mount map captured and checked | Report coverage; no universal restore |
| 8 Transfer | Tool/mount/free-space preflight, staged length/checksum/status | No execution after partial transfer; reviewed cleanup only |
| 9 Persistent install | Explicit plan confirmation and supported service/userspace | Stop first error; rollback not established |
| 10 Reboot/verify | Normal UI, autonomous heating and SSH | Stop integration/cloud changes if heating fails; no destructive retries |
