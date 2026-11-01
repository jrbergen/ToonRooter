# Initial security audit
References to legacy entry point use baseline 4035537; other legacy files unchanged.

| ID | Severity | Reference | Evidence / impact | Mitigation / status / verification |
|---|---|---|---|---|
| S01 | High | legacy __main__.py:155-184 | Syntax errors, reads private as public, uninitialized public, overwrite logic | Replaced entry with safe CLI; isolated RSA lifecycle tested |
| S02 | High | rooter.py:56-126 | Unlimited reads, unchecked prompts, missing addmisc only returns | Disabled orchestration; bounded protocol tests pending |
| S03 | High | rooter.py:196-234 | Reset/halt, unchecked load results, communicate may hang, pipe deadlock, no wait | Disabled; managed subprocess and error checks pending |
| S04 | Critical | assets/boards/ed20.cfg:28 onward | Reset-init writes clocks/SDRAM/registers | No probe until side-effect-free config is demonstrated |
| S05 | High | rooter.py:129-194 | Unverified tar transfer, cleanup/reboot after failure | Disabled; checksum/exit-status/failure protocol pending |
| S06 | High | payload/patch_toon.sh:19-39 | DES password, secret stdout, firewall persistent changes | Not deployed; transactional redesign pending |
| S07 | High | payload/patch_toon.sh:41-73 | Ignores failures, wrong postinst, duplicate key append | Package audit and idempotency tests pending |
| S08 | High | assets/u-boot.bin; payload/*.ipk | Unknown reproducible provenance; old SSH binaries | Inventory recorded; provenance and compatibility gate pending |
| S09 | Medium | rooter.py:203 | Adapter string forms relative config path | New CLI exposes no adapter execution; allowlist pending |
| S10 | Medium | legacy __main__.py:password option | Password in process arguments | New CLI uses getpass; no secret CLI argument |

## Bricking and loss-of-heating risks
Incorrect wiring/voltage can physically damage both devices. Reset/halt suspends heating.
Incorrect boot image/SDRAM setup can crash runtime. Filesystem changes interrupted by
power loss, full flash or unsupported packages may prevent normal service startup.
Changing inittab, passwd, init links and firewall can impair access or operation.
No explicit bootloader flash/saveenv was found, but that does not prove safety.
Existing .preroot files cover only two files; not a full storage or environment backup.
No tested recovery or universal restore exists. No real hardware tests performed.
Acceptance gate: verified device identity, asset compatibility, bounded transport,
backup scope/checksums, explicit persistent-operation approval, normal-boot and
independent heating verification. Never promise recovery based on serial access alone.

## Updated evidence (second session)
- S02: modern transport/protocol has deadline/size/partial/disconnect tests; legacy
  code remains unreachable. Prompt recognition cannot prove command success.
- S03: fixed host-query process manager now bounds logs/time and kills/reaps groups.
  Target startup and bootloader orchestration remain disabled.
- S04: verified from source ed20.cfg:20-22,34-117: nested unpinned imx27 config,
  gdb-attach reset init and reset-init register writes. Physical attach effects and
  non-disruptive TAP IDCODE sequence are hardware-unverified. No live probe enabled.
- S11 (Medium): pySerial open may glitch RTS/DTR (official API open notes).
  Mitigation: closed construction, inactive lines, no flow control/write/BREAK;
  residual physical risk documented, fake initialization asserts exact settings.
- S12 (Medium): diagnostic output can include environment secrets / terminal escapes.
  Transcripts metadata-only, UART CLI uses escaped bytes; no automatic persistent log.
- S09: modern OpenOCD accepts enum queries only, no files/scripts/adapter input.
  This is a structural allowlist, not a forbidden-word scan.

## Power loss and recovery evidence
Source-derived inference: during JTAG/RAM boot stage, loss likely discards loaded
image and volatile environment. Original flash boot path is not explicitly written,
but bootloader behavior, power-loss flash behavior and reboot recovery are unverified.
During passwd/firewall/inittab/opkg writes, interruption may leave partial state;
payload is not idempotent (duplicate authorized_keys and credential regeneration).
No transaction or universal rollback. CPU halt/reset and init=/bin/sh boot interrupt
normal thermostat services. No verified recovery or autonomous heating test exists.
New implementation performs none of these state-changing actions.

## Third session findings and mitigations
| ID | Severity | Evidence/reference | Status and verification |
|---|---|---|---|
| S13 | High | u-boot.bin raw format, only version string; introduction a25023f | Hash/size inventory implemented; no architecture/provenance execution approval |
| S14 | High | rooter.py:129-165 recursively archives payload then extracts directly | New host packager accepts pinned regular files only, explicit paths/modes; verifier checks canonical archive, duplicate/traversal/symlink and content; no extraction |
| S15 | High | rooter.py:147-165 prompt substitutes for integrity/status | New simulation receiver verifies length/hash with explicit ack; real receiving tool absent, live transfer disabled |
| S16 | High | ed20.cfg:20 external target/imx27.cfg version-dependent | Exact config hashes allow static inspection only, unresolved nested chain reported; unknown directives/hash rejected |
| S17 | Medium | Boot transcript may contain credentials in addmisc/environment | State history holds sizes/status only; retained addmisc is never logged; live executor absent |

Power-loss claims remain inferences: RAM image and unsaved environment normally
disappear, but bundled binary behavior is not established. No complete backup,
verified recovery, package rollback, or autonomous heating evidence exists.
New simulated payload receiver stores only bounded host memory; it cannot demonstrate
safe target storage, interrupted extraction cleanup or idempotent installation.

## M2-02c findings
S04/S16: v0.12.0 Tcl reference chain resolved/pinned; installed script comparison
optional. Other versions/compiled handlers/examination/reset effects unverified.
S18 (High): target/imx27.cfg reset_config overrides adapter reset_config none.
Source ordering proves intent, not physical waveform. Exact reference tests added;
live probe disabled.
S13: ARM vectors/link address strengthen architecture inference, not provenance.
NAND/BBT/write routines present; RAM-loaded code may still alter persistent state.
S19 (Medium): prior host USTAR alone incompatible with legacy tar zxf gzip input.
New offline adapter round-trips gzip/base64 and original payload contents.
S15: TRSIM1 is synthetic, not a Toon receiver. No target SHA256 utility requirement.
Payload review: init generates host keys based on mount flags and depends on awk/
start-stop-daemon; skips service when /var/service/dropbear exists. Replacing it
without real userspace fixtures would introduce unsupported assumptions.
Architecture contains comparison decisions and staged hardware stops/recovery limits.

## Host integration milestone
S20 (High): a returned Linux prompt or tar pipeline status does not verify receipt
or successful rooting. Integrated simulation labels transfer status as weaker than
target checksum, blocks installation on nonzero/missing status, and stops before
reboot on failed installation/file checks. Real script may ignore IPK failures:
true SSH/daemon/key/heating postconditions remain hardware gates.
S21 (Medium): binary 0.12.0 version alone does not bind compiled handlers or package
patches. Doctor checks release profile/adapter and optional exact scripts but always
reports target compatibility HARDWARE_REQUIRED. No global unsafe bypass added.
Authorization is phase-specific in simulation; only concrete in-memory rig accepted.
No target shell operations, live JTAG or SSH execution backend is connected.
Timeout/disconnect/incomplete archive/error/interruption tests ensure no install after
failed transfer and no reboot after failed checks. No target rollback is claimed.
Installer changes venv only; manual apt/UART/Bluetooth changes are documented for a
separately authorized host setup. CI file is project-relevant, IDE files remain excluded.

## 2026-11-01 live-library boundary and remaining installation blockers

Pi host-only results at 718ae8f are now recorded; no target validation occurred.
boot/live.py adds fixed, separately authorized disruptive operations, outside the
host-only Query API. Existing simulated endpoints retain concrete-type restrictions.
Private temporary copies bind execution inputs to inspected bytes; execution approval
is separate from inventory hashes. No generic Tcl, command or persistent-write API.
Known image contains NAND write code: explicit image approval must account for startup
and BBT behavior; RAM placement alone is not a non-persistence guarantee.

Current complete bootstrap is unsuitable for identification-only testing. A dedicated
reviewed profile and staged hardware acceptance remain necessary. Killing OpenOCD or
closing UART does not restore thermostat control. Linux shell boot bypasses heating
services; do not infer success or recovery from a prompt.

Payload remains unchanged deliberately during boot-backend work. Concrete blockers
already found: SFTP error invokes dropbear.postinst; opkg statuses other than 255 can
be ignored; authorized_keys permissions/duplicates unchecked; partial sed/package
changes lack rollback; password printed by script. These must be fixed compatibly and
tested before enabling live installation. Actual firmware tool availability, terminal
modes, RAM staging/free-space and completion evidence are unknown. Retain gzip/base64
compatibility; tar exit zero is neither content verification nor install success.
Never automatically reboot a partially failed install. Postconditions must check files,
key permissions, package/service state, then real SSH and autonomous heating separately.

## Native temporary root update — 2026-11-01

Real R8 UART/password/temporary-root findings supersede earlier UART uncertainty for
this ED2.4 only; JTAG remains unvalidated. root is now a hardware-capable CLI command
with explicit UART, volatile argument and modified-boot approvals. JTAG additionally
requires reset/RAM and image execution approvals; auto never invokes it. Host-only
probe/doctor and receive-only observe retain their existing boundaries.

The verified profile boots writable UBIFS and init=/bin/sh, bypassing ordinary heating
services. Unsaved environment is temporary; this is not a claim of zero kernel/storage
side effects. No saveenv or persistent installer is sent. Exact readback blocks boot
after failed setenv, but cannot undo its possible volatile change. Abort closes UART
and does not restore heating. Root UID/proc evidence never certifies permanent SSH.
Snapshot matching never bypasses supported boot-command checks. Credentials and full
environment responses are not printed in CLI results. Known installer/backup/SSH and
heating-verification blockers above remain open.
