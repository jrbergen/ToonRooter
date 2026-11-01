"""User-captured, physical ED2.4 / qb2/uni/6.4.5-0 / R8 boot profile.

These values describe one verified installation; never apply them to another version
without comparing the actual environment. Unrelated environment variables may differ.
"""
R8_ENVIRONMENT = {
    b"bootcmd": b"run boot_nand",
    b"boot_nand": (b"run nandargs addmtd addtty addmisc; "
                   b"nand read ${loadaddr} kernel; bootm ${loadaddr}"),
    b"boot_nand_backup": (b"run nandargs addmtd addtty addmisc; "
                          b"nand read ${loadaddr} kernel-backup; bootm ${loadaddr}"),
    b"nandargs": b"setenv bootargs ubi.mtd=4 root=ubi0:rootfs rw rootfstype=ubifs",
    b"addmtd": b"setenv bootargs ${bootargs} ${mtdparts_kernel}",
    b"addtty": b"setenv bootargs ${bootargs} console=${console},${baudrate}",
    b"addmisc": b"setenv bootargs ${bootargs} mem=${mem} lpj=999424",
    b"mtdparts_kernel": (b"mtdparts=mxc_nand:512K@0x00100000(u-boot-env)ro,"
                         b"1536K(splash-image),3M(kernel),3M(kernel-backup),119M(rootfs)"),
    b"loadaddr": b"0xA1000000",
    b"mem": b"128M",
    b"console": b"ttymxc0",
    b"baudrate": b"115200",
    b"bootdelay": b"2",
}
