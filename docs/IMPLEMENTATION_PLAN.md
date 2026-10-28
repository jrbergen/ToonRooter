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

## Third-session acceptance update
- [x] M2-02a Reviewed legacy command/effect/deadline specification and explicit
  simulation boot states; fail-stop evidence validation and command construction.
- [x] M2-02b Asset identity manifest and static exact-config allowlist. Acceptance:
  host-only inspection rejects mutation/unsupported hardware; unknown provenance
  cannot authorize execution. Original assets preserved.
- [x] M2-03a Deterministic host packaging and independent canonical integrity verifier.
- [x] M2-03b Simulation-only framed transfer, receiver length/hash verification and
  failure tests using actual serial partial-write loop.
- [ ] M2-02c Pinned complete nested OpenOCD chain, bootloader architecture/provenance,
  real response contracts and authorized live executor. Parent M2-02 remains partial.
- [ ] M2-03c Real Toon receiver capability negotiation, bounded staging on confirmed
  mount, checksum/length acknowledgement, interruption cleanup and extraction review.
  Parent M2-03 remains partial; simulation protocol is not deployed to the Toon.

Next recommended task: M2-02c offline provenance/config-chain investigation and
M2-03c receiver capability specification from representative firmware shell data.
Do not wire simulated exchange contracts into live serial/OpenOCD paths.

## M2-02c reference review acceptance update
- [x] M2-02c-1 Complete reference Tcl chain (OpenOCD v0.12.0), optional exact installed
  target comparison, effective reset policy review.
- [x] M2-02c-2 Raw ARM vector/link analysis, provenance limits and existing-console route plan.
- [x] M2-02c-3 Real legacy-format comparison and offline gzip/base64 adapter tests.
- [ ] M2-02c-4 Actual per-command response contracts, controlled config variables,
  compiled-version/firmware compatibility and separately authorized executor.
Parent M2-02c remains partial: its acceptance includes live execution support which
source/mocks cannot establish. Historical provenance alone is not an absolute blocker.
Next: M2-03c legacy-compatible simulated shell transfer with separate acknowledgements,
bounded staging/status and optional checksum capability negotiation. No TRSIM1 or
sha256sum installation requirement. Parallel independent task: M4-01 candidate modern
Pi host/OpenOCD/backend installation validation plan, no Toon.

## Host pipeline/deployment readiness update
- [x] M2-02d End-to-end source-derived simulation spanning host preflight, optional JTAG
  fallback, U-Boot/Linux, real legacy wire bytes, install/reboot consent and verification.
  Acceptance: partial writes, phase failure/no-retry and cleanup tested; explicitly synthetic.
- [x] M2-03d Legacy receiver simulation reconstructs gzip/base64 archive; transfer status
  separated from target integrity, installation and SSH. No TRSIM1/new target utility.
- [x] M4-01a Select Lite64/Trixie Python3.13 and distro OpenOCD0.12 candidate, implement
  isolated installer, host-only readiness and reproducible deployment instructions.
- [ ] M4-01b Execute and record installer/doctor on actual Pi3 WITHOUT Toon.
- [ ] M2-03c remains partial: simulation directly models legacy extraction, not a
  proven staged receiver on actual firmware. Tool/echo/mount/canonical/interrupt behavior pending.
M2-02c-4 remains incomplete: real response contracts and live backend remain absent.
M1-03: CI workflow reviewed/updated and prepared for version control; remote matrix
not yet run. Host package validation is separate from hardware readiness.
Next task: authorized M4-01b Pi-only deployment/doctor with Toon disconnected; independently
finish M2-03c staged receiver/status simulation, validate actual utility fixture evidence.
Do not unblock live execution by passing synthetic response tests.
