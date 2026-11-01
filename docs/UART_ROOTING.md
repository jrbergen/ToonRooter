# Native UART temporary root

The manual R8 procedure is [physically verified](TOON1_R8_UART_VALIDATION.md).
The Python CLI is tested with in-memory UART devices; it has not yet been run on the
Pi/Toon. R6 and base 2010.09 passwords are historical, not validated on our hardware.
No physical operation is authorized by these instructions alone.

With a separately authorized, confirmed 3.3 V UART connection and the Toon initially
off, start the command on the Pi, then wait for **UART open ... ready for Toon power-on**
before powering the Toon using the agreed power procedure:

```sh
.venv/bin/toonrooter root --method auto --serial /dev/serial0 \
  --authorize-uart --authorize-boot-arguments --authorize-shell-boot
```

`auto` detects the actual banner and selects the known password method. It waits for
the password challenge, sends password plus CR, requires U-Boot prompt, reads actual
printenv and checks the verified R8 profile. Unrelated environment variables may
vary; all recorded profile fields must match. Original addmisc arguments, including
lpj, are preserved. The command verifies echoed setenv and the complete environment
readback, boots boot_nand, requires a Linux prompt and `id` with uid=0(root), and mounts
proc only if /proc/self/stat is unavailable. No saveenv or installer is sent.

Successful JSON reports temporary_root/proc_available true, permanent_root,
installation_performed and ssh_verified false. The UART closes on completion; the
Toon remains in the temporary shell. Normal heating services are bypassed. There is
no automatic reboot, reset, rollback, persistent installation or interactive terminal.
A later authorized serial terminal can attach after this process closes the port.

For R6/base versions or a different environment, supply a **privately reviewed full
printenv snapshot** with `--reviewed-environment PATH`. Plain name=value lines or a
complete printenv response are accepted; variable order/CRLF/prompt spacing are ignored.
Review boot_nand and every recursively invoked macro and parameter first. The complete
actual environment must match that snapshot before modification. Dynamic run targets,
unknown commands, cycles and persistent commands are rejected; a snapshot does not
bypass the temporary-boot command restrictions. No R6 firmware values are inferred
from the R8 profile. A mismatch leaves addmisc untouched. A readback failure after
setenv leaves a possible volatile change, but never executes the boot macro.

Each read/write has a bounded deadline and capture limit. --timeout (default 90s)
controls waiting for the initial banner and Linux shell; authentication is capped at
15s, individual U-Boot/root/proc checks at 10s. Bad credentials, incomplete output,
unknown prompts or boot errors stop with nonzero exit and close UART. No retries or
automatic switch to JTAG occur, even when JTAG flags were supplied.

JTAG is retained via the existing fixed Pi3 backend:

```sh
.venv/bin/toonrooter root --method jtag --serial /dev/serial0 --repository . \
  --reviewed-environment /private/reviewed-ram-uboot-environment.txt \
  --authorize-uart --authorize-boot-arguments --authorize-shell-boot \
  --authorize-jtag-reset --authorize-image-execution
```

This requires the supported Pi3 Model B Rev1.2 host and explicit separate reset/RAM
and historical-image execution approvals. It is not an identification-only probe.
The loaded image's actual environment needs its own review; the native R8 environment
must not be assumed for that image. JTAG electrical/reset/image execution remains
unvalidated. With auto and an unknown version, the supported Pi3/repository combination
only offers this option; a new explicit invocation and authorization are necessary.
`probe --jtag` remains disabled. Existing JTAG library entry points are preserved.

`--install` and `--authorize-install` are reserved and refused before device opening.
Live payload staging, installation/postconditions, partial-install recovery, reboot
and real SSH/heating verification remain unfinished. Host packaging and RootSimulation
remain available independently. BootConsole exposes the shared bounded console for a
future installer; simulator-only transfer contracts are never used on live devices.
