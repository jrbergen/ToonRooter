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
