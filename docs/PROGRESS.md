# Progress — 2026-10-28
Current milestone: M1 foundation implemented; full milestone remains open.
Baseline 4035537, no pre-existing local changes. No commits or pushes.
Implemented packaging, safe entry points, configuration, host-only diagnostic report,
RSA3072 creation, encrypted-key prompt, reuse/match validation, missing-public recovery,
external key validation and exclusive no-follow 0600 writes. Existing files never overwritten.
Partial pair on interrupted creation intentionally retains private key for recovery.
Legacy rooter/sshkeys and target payload remain unported and unreachable from CLI.
Tests: 9 pytest cases passed on Python 3.14.8; Ruff passed. No Pi/Toon contacted.
Files: pyproject.toml, __main__.py, toonrooter/, tests/, AGENTS.md and docs/*;
README gains modern entry instructions with historical instructions retained.
Research: issue26 confirms a reported unactivated-device success; not hardware validation.
Inspected IPK controls/data listings without execution. Deeper init/binary audit unfinished.
Decision: expose only doctor/keys; unimplemented workflows fail argument parsing.
Limitations: no serial/OpenOCD/payload port yet; doctor presence/access checks cannot
prove adapter support, device identity or readiness; no complete backups or restore.
No tested Pi installation instructions yet. Supported declaration >=3.12 needs matrix tests.
Next: M2-01; see authoritative checklist. Permission injection/concurrent creation and
failure durability tests remain useful; hardware milestones require explicit authorization.

Final checks: Ruff and 9 tests passed again; compileall passed for modern package/tests;
source distribution and wheel built successfully with build --no-isolation.

## Second session — 2026-10-28
Preserved existing code and untracked .idea/; baseline nine tests passed.
Implemented M2-01: bounded serial with explicit RX/interactive modes, partial writes,
disconnect handling, finite deadlines, caps and deterministic fake sessions.
Added real pySerial PTY test using a local pseudo-terminal only (no physical device).
M2-02 partial: fixed OpenOCD host queries with selector-drained bounded merged output,
timeout, exit-code failure and process-group cleanup; U-Boot prompt/version parsing,
interactive printenv response validation and bounded metadata transcripts.
M3-01 partial: observe CLI, safe host-only default probe, refused --jtag;
doctor OS/model/GPIO metadata, serial enumeration and compiled-adapter inspection.
Level3 authorization policy refuses all execution even with confirmation/compatibility.
Added GitHub Actions Python 3.12/3.13/3.14 workflow (not executed here).
No legacy orchestration imports, target scripts, bootloader transfer or payload execution.
Unknown TAP/reset/adapter target transcripts are not implemented because no target
executor is enabled; they remain future target-orchestration acceptance requirements.
M2-02 and M3-01 deliberately remain unchecked pending their full acceptance gates.

Files added: hardware/{serial,openocd}.py, boot/uboot.py, diagnostics.py, safety.py,
three new test modules and .github/workflows/tests.yml. Updated CLI, README,
AGENTS.md, architecture/audit, plan/progress. Legacy assets/source unchanged.
Environment: Python 3.14.8 only. Temporary venv includes pySerial3.5/Ruff0.17.3.
Safety limitations: UART modem-line glitches cannot be excluded; prompt idle heuristic
cannot authenticate device identity; compiled adapter presence is not hardware validation.
Next task: complete M2-02 reviewed boot operation planning and provenance gate before
any state-changing executor; implement M2-03 verified payload packaging/abort tests.

Final verification: 42 tests passed (all original nine retained), Ruff passed,
modern package/tests compileall passed, sdist/wheel build --no-isolation passed,
git diff --check passed. OpenOCD tests run disposable Python child processes,
not OpenOCD against hardware; pySerial test runs only a local PTY.
No real Pi/Toon accessed, no commits or pushes.

## Third session — 2026-10-28
Inspected authoritative docs/source/assets/history/tests. Current branch master,
baseline a7271f9 (user commits preserved), untracked .github/ and .idea/ retained.
Baseline result here: 41 passed / 1 skipped (pySerial missing, PTY skipped).
Implemented M2-02a/b and M2-03a/b; parents remain partial.
Added asset manifest/validation, exact legacy config audit, fail-stop boot simulation
with evidence parsing and constrained addmisc command construction, deterministic
USTAR packaging/verification and in-memory framed receiver exercising actual serial
writes with partial progress. No receiver or executor deployed on Toon.
New CLI: asset-audit --repository PATH; package-payload --repository PATH
--ssh-public-key PATH --output PATH (exclusive 0600 local creation).
Files: toonrooter/assets.py, data/assets.json, boot/sequence.py, payload.py,
transfer.py, safety.py, cli.py, pyproject.toml, tests/test_boot_payload.py;
existing architecture/audit/roadmap/progress/AGENTS/README updated.
Unresolved: binary format/architecture/provenance, nested target/imx27.cfg and
modern Pi GPIO driver semantics, actual boot response contracts/authorization,
receiver utility/mount/canonical-mode negotiation and interrupted staging cleanup.
No physical Toon or Pi contacted, no commits/pushes. Other Python versions not tested.
Next: M2-02c offline provenance and nested config-chain investigation; M2-03c real
receiver specification. Never mistake simulated success for hardware validation.

Final validation: Python 3.14.8, 91 passed / 1 skipped (existing real-pySerial PTY
test skipped because dependency unavailable in this environment). Ruff passed,
compileall passed, sdist/wheel builds passed, git diff --check passed. Asset JSON
is included as package data. No claim of HIL, modern Pi OS or multi-Python validation.

## Fourth session — 2026-10-28: M2-02c architecture evaluation
Baseline master 5586bbc; untracked .github/ and .idea/ preserved. Baseline tests:
91 passed/1 skipped. Read docs/source and reviewed legacy execution/binary/history,
bundled Dropbear init/default. Retrieved inert OpenOCD v0.12.0 target/imx27.cfg,
pinned source/hash/license; no further includes. Target overrides adapter reset policy.
Implemented reference/installed config comparison, raw ARM vector/link analysis,
existing-console-first route planner (banner != authentication), offline gzip/base64
adapter matching legacy input. asset-audit optionally --openocd-scripts;
package-payload optionally --format legacy-base64. No live executor enabled.
Files: hardware/config_review.py, boot/compatibility.py, legacy_wire.py,
data/openocd-review.json, data/openocd-0.12.0/*, assets.py, cli.py, pyproject.toml,
tests/test_compatibility.py and persistent docs/README/AGENTS.
Completed M2-02c-1/2/3; parent partial for live response/compatibility/authorization.
Decision: retain established console/JTAG fallback, do not replace boot image/init.
Synthetic TRSIM1 excluded from real path. Host tar now has explicit legacy conversion.
Unknown: BBT startup effects, real firmware/reset timing, OpenOCD C behavior, modern
Pi drivers, receiver utilities/mount/echo handling. No real Pi/Toon accessed.
Next exact task M2-03c legacy-compatible shell transfer simulation with bounded
staging/status and optional available checksum; M4-01 modern host setup research.

Final validation: isolated environment Python 3.14.8 with pySerial3.5/Ruff0.17.3:
105 passed, zero skipped (PTY included). Ruff, compileall, sdist/wheel build and
git diff --check passed. Verified reference/manifest/license resources in wheel.
No other Python versions or real hardware validated; no commits/pushes.

## Fifth session — 2026-10-28: host integration/deployment
Baseline master b8217b4; reviewed commit contents/acceptance, retained .idea/.
Existing untracked .github/workflows/tests.yml is valid project CI, now updated with
wheel-install smoke check and prepared to be included in the next authorized commit.
No git staging/commit/push performed. Baseline system tests:104 pass/1 PTY skip.
Implemented workflow.py and testing/rooting.py: integrated source-derived boot/root
simulation with real transport, protocol parser, package and gzip/base64 bytes, separate
phase statuses/authorizations, fixed installation checks and synthetic reboot/SSH.
CLI simulate-root uses in-memory fixture only. Existing root/probe--jtag stay disabled.
deployment.py/doctor: structured release/adapter/OS/model/dependency/UART/GPIO/key/
asset/script checks without device open. Added scripts/install-host.sh and DEPLOYMENT.md.
Selected candidate Pi OS Lite64 Trixie, Python3.13, distro OpenOCD0.12; no real Pi tested.
Changes: CLI, new workflow/testing/deployment modules, new test modules, installer,
CI and persistent docs. Original assets/payload unchanged; no replacement target utility.
M2-02d/M2-03d/M4-01a complete; parent live/receiver/physical deployment tasks partial.
Source-derived pipeline status is NOT target integrity. IPK script error handling,
normal thermostat/heating, electrical, actual OpenOCD responses/firmware and
serial terminal semantics remain blockers. Only simulation backend exists.
Next exact action: separately authorized Pi-only install/doctor with Toon disconnected;
collect host release/adapter/config/UART results before any electrical/target work.

Final verification (continued): **135 passed, zero skipped** on Python 3.14.8 and
isolated Python 3.13.12 (selected deployment minor version). Both include PTY.
Ruff and compileall pass; sdist/wheel build passes; shell installer syntax and
git diff --check pass. Installed final wheel into /tmp Python3.13 venv and ran
simulate-root outside checkout successfully; packaged target reference present.
Python3.13 interpreter/dependencies installed only in task-specific /tmp locations.
Remote CI and physical Pi remain untested; Python3.12 matrix run remains pending.
Added explicit regression: tar status zero does not detect changed valid archive contents.
Fixture no longer invents receiver-side host-hash comparisons. Source protocol reads
version line then sends password immediately, without extra password-prompt wait.
No actual UART/GPIO/target OpenOCD/SSH or payload execution; no staging/commit/push.

## Documentation session — 2026-10-31
Inspected master d2d2b4e, implementation, installer, assets/configs and tests.
Initial worktree had only untracked .idea/; preserved. Created DOCS.md,
RPI_INSTALL.md and TODO_MANUALLY.md with exact current CLI, a fresh Lite64/Trixie
installation path (discarding Stretch), host-only testing/results checklist and
remaining hardware/development gates. Official Pi OS/Imager/UART docs, Debian
Python3.13/OpenOCD0.12 package pages and upstream wiring table checked.
No application changes needed for host-only Pi3 testing; no physical validation done.
Ran all seven subcommand helps, ten host CLI scenarios (local keys/audits/packages/
simulation/probe/refusal/doctor), Ruff0.14.11, compileall and installer bash syntax.
Full current suite on Python3.14.8:134 passed/1 skipped (pySerial absent, PTY test).
Prior isolated 135-test Python3.13.12/3.14.8 results remain historical evidence;
this session did not recreate those environments or test ARM64 hardware.
Documented CLI examples parse and local Markdown links resolve; git diff --check passed.
Only requested root guides and plan/progress updated. No commits/pushes or Pi/Toon access.
Next: follow RPI_INSTALL.md then TODO_MANUALLY.md Phase C; share host results before wiring.

User authorized committing this documentation work and encouraged descriptive local
commits after future implementation/documentation steps. AGENTS.md updated accordingly;
pushing still requires explicit instruction. Documentation diff check passed.

## Pi evidence and live boot implementation — 2026-11-01

Baseline `718ae8f`, branch py3-modernize; preserved earlier `d2d2b4e` milestone
and pre-existing untracked .idea/ and uv.lock (neither staged). Read repository guides,
architecture/audit, legacy Python/config/payload and relevant current modules/tests.
Created PI3_HOST_VALIDATION.md from user-supplied real Pi3 results: Lite64 Trixie,
Python3.13.5 ARM64, distro OpenOCD snapshot, UART/GPIO metadata, installed-script
comparison, packages/keys/payload preparation, eleven-phase synthetic rehearsal,
/dev/null regression fix and final 135 passing tests/Ruff. This session did not
reproduce those Pi results or access either physical device.

Fixed diagnostics: adapter list returned a Tcl value without printing; explicit echo
with delimiters now separates actual drivers from merged banners/shutdown messages.
Exact 0.12.0+dev-snapshot (2026-02-16-16:07) is host-validated; ordinary reviewed
0.12.0/dfsg releases supported, older profiles FAIL, unverified builds UNKNOWN.
Compiled driver availability remains separate from installed scripts and hardware.

Added boot/live.py: library-only fixed Pi3 bootstrap, exact inventory/private copies,
vendored target chain, actual TAP ID checks, explicit reset-init clocks/SDRAM handler,
halted-state check, load_image/verify_image then resume. Uses bounded process runner,
no listeners, no generic Tcl interface, fail-stop cleanup. Explicit separate approvals
for UART commands, reset/register/RAM, image execution and Linux shell boot. UART
opened before resume, no input discard. Supported-banner login, environment inspection,
exact separately reviewed full macro environment, setenv echo/readback, then boot_nand
and bounded Linux prompt. Existing supported console preferred, no automatic fallback.
No simulated endpoint connected to live transport; existing contracts remain isolated.

Important implementation limits: batch shutdown precedes buffered UART login, so
password-window latency still needs measurement. reset init deliberately differs from
legacy reset halt to invoke SDRAM setup; physical behavior is unvalidated. GPIO timing,
reset wiring, compiled OpenOCD semantics, RAM image startup/BBT and PCB/firmware remain
unverified. Current bootstrap is not an identification-only probe. No live root/JTAG CLI,
receiver/install/reboot/SSH executor, backup or recovery claim. Abort cannot undo target
state changes. Payload left unchanged during boot work; documented ignored package
failures, wrong SFTP postinst and partial-install/key/secret-handling defects remain
mandatory fixes before enabling install. No invented target checksum acknowledgement.

Updated plan, architecture/audit, AGENTS and user guides. TODO_MANUALLY now specifies
PCB/pin/voltage confirmation and first separately authorized RX/GND-only observe,
then existing console preference and staged JTAG/boot validation. Pi OS reinstallation
and repeated completed host tests are not needed; revised doctor needs Pi confirmation.

Verification on development host, Python3.13.5 x86_64: **167 passed in 6.96 seconds,
zero skips**; Ruff passed; compileall passed; uv pip check found all 13 installed
packages compatible. Source/wheel build passed; wheel installed under /tmp and imported
outside checkout, including pinned target resource/profile/authorization smoke checks.
Local Tcl stub harness exercised actual fixed script control flow for success, wrong
CPU/ETB IDs, load and verify failures (no resume after failure). This is not OpenOCD
interpreter/hardware validation. Regression tests also cover merged stdout/stderr,
unknown/missing adapters, version strings, abort/temp/process cleanup, wrong prompts,
UART timeout/disconnect, environment mismatch/readback failure and withheld approvals.
No Pi/Toon access, physical signaling, target code/payload execution or push performed.
Next: reviewed electrical inspection and receive-only UART capture; M2/M3/M5 parents
remain open pending actual acceptance, identification-only profile and installation work.
