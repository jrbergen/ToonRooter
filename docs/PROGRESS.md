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
