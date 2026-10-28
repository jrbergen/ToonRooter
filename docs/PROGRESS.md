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
