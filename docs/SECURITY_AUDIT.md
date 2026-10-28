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
