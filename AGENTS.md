# Session continuity and safety
Every session must read this file, docs/IMPLEMENTATION_PLAN.md and docs/PROGRESS.md,
inspect relevant implementation, continue the next unfinished task, run applicable tests,
and update both tracking documents before ending. Never mark complete before acceptance.
Do not commit or push without instruction.
Python >=3.12 only. Legacy rooter.py, sshkeys.py, assets and payload are evidence,
not validated modern implementation. New CLI must never import legacy orchestration.
No real hardware, remote Pi changes, payload execution, boot environment changes or HIL
tests without explicit authorization. Hardware tests must be opt-in, never default pytest.
Do not infer safe probing from an OpenOCD configuration: reset event handlers write registers.
Preserve existing private keys; never log key material or passwords.
