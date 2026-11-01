# Session continuity and safety
Every session must read this file, docs/IMPLEMENTATION_PLAN.md and docs/PROGRESS.md,
inspect relevant implementation, continue the next unfinished task, run applicable tests,
and update both tracking documents before ending. Never mark complete before acceptance.
Make sensible, descriptive local commits after completed implementation or documentation
steps unless the user requests otherwise. Do not push without explicit instruction.
Python >=3.12 only. Legacy rooter.py, sshkeys.py, assets and payload are evidence,
not validated modern implementation. New CLI must never import legacy orchestration.
No real hardware, remote Pi changes, payload execution, boot environment changes or HIL
tests without explicit authorization. Hardware tests must be opt-in, never default pytest.
Do not infer safe probing from an OpenOCD configuration: reset event handlers write registers.
Preserve existing private keys; never log key material or passwords.
Diagnostic levels: doctor/default probe host-only; observe is explicit receive-only UART
and still carries control-line opening risk. probe --jtag is deliberately disabled.
OpenOCD.query accepts only fixed host Query enums, never target configs or arbitrary Tcl.
The separate boot/live.py backend uses fixed target Tcl and explicit operation approvals.
UBootSession printenv is an explicit interactive library operation, never passive observe.
BootSequence and SimulatedTransfer accept only their concrete in-memory endpoints.
Do not connect simulator contracts to live devices. Asset hashes permit inspection/
packaging/simulation only, never execution. New payload archives must be independently
verified and never extracted/executed during host preparation.
OpenOCD v0.12.0 Tcl chain is vendored for static review only; target reset_config
overrides adapter reset_config none. Matching hashes never authorize execution.
Prefer established supported console access before disruptive JTAG fallback planning.
RootSimulation is the integrated source-derived rehearsal, concrete in-memory rig only.
Do not equate tar/printf status with target integrity or installation success.
Pi3 deployment candidate is Lite64/Trixie Python3.13; scripts/install-host.sh only
installs local host tools into venv. Pi3 host-only validation at 718ae8f is recorded in docs/PI3_HOST_VALIDATION.md.
ED2.4/R8 UART wiring and manual temporary root are physically verified; see
docs/TOON1_R8_UART_VALIDATION.md. JTAG/GPIO signaling remains unvalidated. boot/live.py is a separate,
explicitly authorized library backend; fixed bootstrap Tcl is isolated from host Query.
Its presence grants no hardware execution authorization. root --method auto|uart|jtag
requires explicit operation approvals; probe --jtag and persistent install remain disabled.
The new root CLI has simulated tests only; R6 is historical, not our hardware validation.
