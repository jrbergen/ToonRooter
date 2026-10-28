# Architecture and evidence
Baseline: 4035537edf77e6b4fc2d89525fd7d0c08cd284bc, initially clean.
Reviewed all tracked text sources, adapter/board configurations, recent history,
binary sizes/hashes and IPK control/data inventories without executing target code.
Original entry point is retained in Git; rooter.py and sshkeys.py remain legacy evidence.
Commit 6da0b46 introduced an explicitly untested key overwrite check.

## Original execution
1. CLI autodetects Pi using a finite revision lookup, even if JTAG is not requested.
   Opens UART at 115200, default /dev/serial0; default serial timeout is unlimited.
2. Waits indefinitely for U-Boot version. Known passwords for 2010.09, R6, R8.
3. Otherwise starts openocd with /usr/share/openocd and relative adapter and board paths.
   Sleeps ten seconds, connects telnet localhost:4444; sends soft_reset_halt,
   reset halt, load_image assets/u-boot.bin 0xa1f00000, resume 0xa1f00000.
4. Board sources target/imx27.cfg. gdb-attach resets/init; reset-init invokes ed20_init.
   This resets, changes GPIO/clock/AIPS/SDRAM registers and CPU mode. It is not read-only.
   Pi3 bcm2835gpio base 0x3F000000, 500 kHz; BCM TCK/TMS/TDI/TDO 11/25/10/9,
   TRST 8, SRST 24 (physical 23/22/19/21, 24/18); reset_config none.
5. UART password then U-Boot> prompt. printenv extracts addmisc, setenv adds init=/bin/sh,
   escaping dollars and semicolons; run boot_nand starts Linux shell.
   No saveenv or explicit NAND write found in Python path. Environment change appears
   volatile, not a guarantee about all bootloader side effects.
6. At / # prompt, base64 streams gzip tar into timeout -t 60 base64 -d | tar zxf -.
   No checksums, exit status or verified completion. Temporary descriptor is leaked.
7. Runs payload/patch_toon.sh with weak random password, consumes prompts, optionally
   rm -r payload and /etc/init.d/reboot even following a caught exception.

## Persistent payload inventory
patch_toon.sh creates missing /dev/urandom; copies /etc/passwd.preroot and
/etc/default/iptables.conf.preroot once; replaces root password using DES crypt;
adds INPUT accept rules for TCP 22/80/10080; comments VPN entry in /etc/inittab;
installs bundled IPKs; appends authorized_keys repeatedly without permissions enforcement.
Dropbear IPK writes /etc/default/dropbear, /etc/init.d/dropbear,
/usr/sbin/dropbearmulti and related links/tools, /usr/bin/dbclient, /etc/dropbear.
Postinst changes ssh/scp alternatives and update-rc.d startup links. Removal scripts
stop service and delete host keys. Init script/runtime behavior needs deeper audit.
SFTP IPK writes /usr/libexec/sftp-server, requires glibc >=2.10.1; no postinst.
Payload erroneously calls dropbear.postinst for SFTP failure. Package failures other
than code 255 can be ignored. No transaction or complete rollback exists.

## Binary provenance
u-boot.bin: 166504 bytes, SHA256
5ff62c31c19265eff1160169c60594335ea727174002f667d9344ea9cb7882e0.
README credits community authors; reproducible source/build mapping unconfirmed.
Dropbear SHA256 e097a7db067f9fee3402238202e7b3d15a5f009fdb2235d60c85d7ac6eb5c0e0;
SFTP SHA256 b736f8d5214c515f6bf3b12d174c13c3a10aad85682b040b5f8b8db7dc2fdd33.
Package metadata lists OpenEmbedded sources, build unknown. Hashes identify assets,
not their trustworthiness. Machine-code behavior is not established by inspection.

## Modern boundary
CLI -> configuration / local diagnostics / RSA lifecycle only. No device is opened.
Future transport -> bounded byte protocol -> explicit operation orchestration.
probe, backup, root, verify, boot-console, configure-local and restore are deliberately
not exposed until implemented and tested. No simulated hardware success claims.

## External evidence and deployment direction (2026-10-28)
- https://github.com/martenjacobs/ToonRooter/issues/26 reports Pi3/Stretch rooting of
  an unactivated Toon1, then updater-assisted setup. This is one report, not proof for
  product 6500-1400-2001 or unknown firmware.
- https://github.com/ToonSoftwareCollective/update-rooted documents VPN firmware updates
  and -f fix-only mode. Activation without upgrade still requires source audit.
- https://www.raspberrypi.com/software/operating-systems/ lists Trixie/Debian13 Lite
  and Pi3-compatible 64-bit images. Proposed host: Lite 64-bit; hardware unvalidated.
- https://github.com/ToonSoftwareCollective/ToonRooter and
  https://github.com/ToonSoftwareCollective/Root-A-Toon remain comparison tasks.
Python declared >=3.12; exercised 3.14.8 only. Trixie Python package version and
3.12/3.13 dependency/install matrix remain to verify. Bookworm's older Python is
not the target. Modern GPIO driver selection, UART overlays (/boot/firmware),
console/Bluetooth conflicts and signal compatibility require official-doc research
and Pi-only validation before deployment instructions can be called tested.
Do not substitute a new GPIO driver based only on compilation.

## Activation and autonomy
Rooting grants access; it does not activate the thermostat. Updater script contents,
firmware prerequisites, local API endpoints and Home Assistant behavior remain unverified.
Later gates: preserve autonomous heating through network/HA failure; permit HA
192.168.2.25 and local DNS/NTP; test router outbound isolation after setup.
No cloud shutdown or firmware update is implemented.
