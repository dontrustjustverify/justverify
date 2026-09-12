#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
set --
if [ -f .state/vm/provision-test.qcow2 ]; then
  set -- -drive file=.state/vm/provision-test.qcow2,if=none,id=jv_provision,format=qcow2 -device virtio-blk-pci,drive=jv_provision,serial=JUSTVERIFY_TEST_DATA
fi
if [ -f .state/vm/provision-ui-test.qcow2 ]; then
  set -- "$@" -drive file=.state/vm/provision-ui-test.qcow2,if=none,id=jv_provision_ui,format=qcow2 -device virtio-blk-pci,drive=jv_provision_ui,serial=JUSTVERIFY_UI_TEST
fi
exec qemu-system-aarch64 -machine virt -accel hvf -cpu host -smp 4 -m 6144 \
  -bios /opt/homebrew/share/qemu/edk2-aarch64-code.fd \
  -drive file=.state/vm/disk.qcow2,if=virtio,format=qcow2 \
  -drive file=.state/vm/seed.iso,if=virtio,format=raw,readonly=on \
  -netdev user,id=net0,hostfwd=tcp:127.0.0.1:22222-:22 \
  -device virtio-net-pci,netdev=net0 -nographic "$@"
