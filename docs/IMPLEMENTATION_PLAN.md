# Authoritative implementation plan
Goal: reliable Toon1 rooting while preserving independent heating; Python >=3.12.
Tasks are complete only with evidence and their acceptance criteria met.

- [x] M0-01 Establish baseline and trace tracked execution/config/payload paths.
  Acceptance: documented sequence and initial risk inventory.
- [ ] M0-02 Deep binary/init script provenance, upstream forks/PR/history comparison.
  Acceptance: source/build mapping or explicit unsupported asset gate.
- [x] M1-01 Package, safe CLI, local configuration and key lifecycle.
  Acceptance: host-only doctor and keys work; no legacy imports or hardware access.
- [x] M1-02 Initial key regression and CLI tests plus Ruff.
  Acceptance: absent/valid/partial/invalid/mismatch/external keys and safe paths tested.
- [ ] M1-03 Python 3.12/3.13/3.14 CI, install/build matrix and permission/failure injection.
  Acceptance: wheels install and tests pass across declared versions.
- [x] M2-01 Bounded bytes-only serial transport and fake transcripts.
  Acceptance: partial responses, deadlines, disconnect, unexpected prompts covered.
- [ ] M2-02 Managed OpenOCD subprocess and U-Boot protocol.
  Acceptance: interruption/reaping/error paths; commands compared to baseline.
- [ ] M2-03 Payload packaging/transfer protocol.
  Acceptance: safe archive paths, checksums, aborts, exit status and cleanup tests.
- [ ] M3-01 Expanded doctor and conservative probe design, risk classification.
  Acceptance: doctor host-only, probe side effects precisely established.
- [ ] M3-02 Preflight, redacted logs, explicit persistent confirmation.
- [ ] M4-01 Official OS/Python/UART/GPIO research and reproducible installation.
- [ ] M4-02 Pi host tests without Toon; validate adapter availability and permissions.
- [ ] M5-01 Authorized wiring/identity and temporary bootloader HIL.
- [ ] M5-02 Feasible verified backups and recovery mechanism.
- [ ] M5-03 Approved installation, normal boot, SSH and autonomous heating verification.
- [ ] M6-01 Audit updater activation and firmware prerequisites before integration.
- [ ] M6-02 Local API/HA, cloud isolation and network-failure heating tests.

Dependencies: M2 before M3 root gates; M4 before M5; explicit connected-hardware
authorization for every M5 operation; M5 before M6. Unknown firmware/provenance,
GPIO compatibility, incomplete backup and unactivated state remain risks.
Test categories: default pure unit; simulated integration; explicitly opted-in
Pi-host (no Toon); explicitly opted-in HIL (only category allowed to contact Toon).
Do not add hardware tests to default collection that can perform I/O.

Next task: M2-02 remains partial: host-query OpenOCD management and U-Boot
printenv protocol implemented, but no target startup or bootloader sequencing.
Add reviewed operation plans and pinned nested-config/source provenance before
disruptive bootstrapping. M2-03 remains entirely pending. M1-03 CI matrix added,
not yet run remotely; permission/failure matrix remains pending.
M3-01 partial: doctor expanded, observe implemented, live JTAG explicitly refused.
No physical target identification/reset/transfer simulation is claimed: those target
executors do not exist yet. Preserve this gate rather than testing unrelated mocks.
