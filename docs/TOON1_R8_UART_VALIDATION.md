# Toon 1 R8 temporary-root validation

User-reported real hardware execution, recorded 2026-11-01. This is a major physical
milestone beyond Pi host checks and simulated rooting. It validates this particular
Toon installation and manual UART procedure, not the new CLI implementation.

| Item | Observed |
|---|---|
| Product | Toon 1, PN 6500-1400-2001 |
| PCB | Prodrive ED2.4 Display, PN 6500-1400-2200 |
| CPU | Freescale i.MX27, ARM926EJ-S |
| Memory/storage | 128 MiB RAM, 128 MiB NAND |
| Firmware | qb2/uni/6.4.5-0 |
| Kernel | 2.6.36-R10-h28 |
| U-Boot | 2010.09-R8 |
| UART | 115200 8N1, 3.3 V, real boot logs captured |

Verified wiring: J503 pin 11 (Toon RX) to Pi GPIO14/TX (physical 8), J503 pin 13
(Toon TX) to Pi GPIO15/RX (physical 10), J503 pin 14 to Pi GND. These assignments
are confirmed for this PCB. They do not establish other PCB revisions or JTAG wiring.

UART was opened before power-on. After the version banner and `Enter password -
autoboot in 2 sec` challenge, the version-specific R8 password plus CR obtained
`U-Boot>`. The credential is retained in the protocol implementation; no diagnostic
or result should print it. R6 credentials are historical only, untested on our hardware.

The original environment, captured before modification:

```text
bootcmd=run boot_nand
boot_nand=run nandargs addmtd addtty addmisc; nand read ${loadaddr} kernel; bootm ${loadaddr}
boot_nand_backup=run nandargs addmtd addtty addmisc; nand read ${loadaddr} kernel-backup; bootm ${loadaddr}
nandargs=setenv bootargs ubi.mtd=4 root=ubi0:rootfs rw rootfstype=ubifs
addmtd=setenv bootargs ${bootargs} ${mtdparts_kernel}
addtty=setenv bootargs ${bootargs} console=${console},${baudrate}
addmisc=setenv bootargs ${bootargs} mem=${mem} lpj=999424
mtdparts_kernel=mtdparts=mxc_nand:512K@0x00100000(u-boot-env)ro,1536K(splash-image),3M(kernel),3M(kernel-backup),119M(rootfs)
loadaddr=0xA1000000
mem=128M
console=ttymxc0
baudrate=115200
bootdelay=2
```

The successful volatile modification was:

```text
setenv addmisc setenv bootargs \$\{bootargs\} mem=\$\{mem\} lpj=999424 init=/bin/sh
```

printenv confirmed original arguments plus `init=/bin/sh`; `run boot_nand` read the
existing NAND kernel and booted it. The runtime kernel command line was:

```text
ubi.mtd=4 root=ubi0:rootfs rw rootfstype=ubifs mtdparts=mxc_nand:512K@0x00100000(u-boot-env)ro,1536K(splash-image),3M(kernel),3M(kernel-backup),119M(rootfs) console=ttymxc0,115200 mem=128M lpj=999424 init=/bin/sh
```

The shell printed `/bin/sh: can't access tty; job control turned off` and `/ #`.
`id` returned `uid=0(root) gid=0(root)`. UBIFS was writable, about 40.1 MiB free.
`mount -t proc proc /proc` subsequently mounted proc successfully.

No saveenv, JTAG, explicit NAND erase/write, rooting payload or persistent SSH install
was performed. The unsaved boot argument change is lost on power loss; this was
**temporary root**, not permanent rooting. Booting a writable filesystem is not a
claim that the kernel makes no persistent changes. Normal heating/service operation,
SSH installation, recovery and autonomous thermostat acceptance remain separate.
