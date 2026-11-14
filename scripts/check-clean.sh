#!/usr/bin/env bash
# Confirm that nothing is left running and no guest memory file is left behind.
# Process names are matched, not whole command lines, so this script does not
# match itself.
WORK="${LUX_WORK_DIR:-$HOME/lux-work}"
status=0
if pgrep -a qemu-system; then echo "LEFTOVER: a virtual machine is still running"; status=1; else echo "virtual machines running: none"; fi
if pgrep -a -x swtpm; then echo "LEFTOVER: a software TPM is still running"; status=1; else echo "software TPMs running: none"; fi
if [ -d "$WORK" ] && find "$WORK" -name mem.bin | grep -q .; then echo "LEFTOVER: a guest memory file exists"; status=1; else echo "guest memory files: none"; fi
exit $status
