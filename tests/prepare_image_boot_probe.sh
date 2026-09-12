#!/bin/bash
# Isolated Linux builder only. Creates a disposable copy; never edits the release artifact.
set -euo pipefail
umask 077
[[ $EUID = 0 && $(hostname) = justverify-dev ]] || exit 1
artifact=${1:?}; output=${2:?}
[[ ${3:-} = "" || ${3:-} = --with-data ]] || exit 1
[[ ! -e "$output" && "$output" = /var/tmp/jv-virt-probe-*.img ]] || exit 1
case "$artifact" in
  *.img) cp --sparse=always "$artifact" "$output" ;;
  *.img.xz) xz -dc "$artifact" | dd of="$output" bs=4M conv=sparse status=none ;;
  *) echo "Expected pristine .img or .img.xz"; exit 1 ;;
esac
loop=$(losetup --find --show --partscan "$output")
# Kernel partition scanning and udev node creation are separate events.
udevadm settle --timeout=10
for attempt in $(seq 1 50); do
  [[ -b "${loop}p1" && -b "${loop}p2" ]] && break
  sleep 0.1
done
[[ -b "${loop}p1" && -b "${loop}p2" ]] || { losetup -d "$loop"; echo 'Partition device nodes did not appear'; exit 1; }
work=$(mktemp -d)
cleanup() { umount "$work/boot/firmware" 2>/dev/null || true; umount "$work" 2>/dev/null || true; losetup -d "$loop"; rmdir "$work"; }
trap cleanup EXIT
mount "${loop}p2" "$work";mount "${loop}p1" "$work/boot/firmware"
# External generic-VM kernel needs its matching modules (e.g. FAT, loop, virtio).
# This test-only addition is never made to the distributed Pi image.
cp -a "/usr/lib/modules/$(uname -r)" "$work/usr/lib/modules/"
install -d "$work/opt/jv-test-modules"
/opt/justverify-tests/bin/python -c 'import importlib.metadata as m; assert m.version("pyte")=="0.8.2" and m.version("wcwidth")=="0.8.3", "unverified terminal decoder versions"'
pyte_dir=$(/opt/justverify-tests/bin/python -c 'import pathlib,pyte; print(pathlib.Path(pyte.__file__).parent)')
wcwidth_dir=$(/opt/justverify-tests/bin/python -c 'import pathlib,wcwidth; print(pathlib.Path(wcwidth.__file__).parent)')
cp -a "$pyte_dir" "$wcwidth_dir" "$work/opt/jv-test-modules/"
install -m 0700 tests/image_boot_probe.py "$work/opt/jv-image-boot-probe.py"
install -m 0700 tests/onion_http.py "$work/opt/jv-onion-http.py"
if [[ ${3:-} = --with-data ]]; then install -m 0700 tests/image_data_probe.py "$work/opt/jv-image-data-probe.py"; chmod 0755 "$work/opt/jv-image-data-probe.py"; fi
cat > "$work/etc/systemd/system/jv-image-boot-probe.service" <<'UNIT'
[Unit]
Description=Disposable generic VM image boot probe
After=justverify-firstboot.service justverify-web.service justverify-manager.service
Wants=justverify-firstboot.service justverify-web.service justverify-manager.service
[Service]
Type=oneshot
ExecStartPre=/bin/sleep 5
ExecStart=/opt/justverify/venv/bin/python /opt/jv-image-boot-probe.py
StandardOutput=journal+console
StandardError=journal+console
TimeoutStartSec=300
[Install]
WantedBy=multi-user.target
UNIT
ln -s ../jv-image-boot-probe.service "$work/etc/systemd/system/multi-user.target.wants/jv-image-boot-probe.service"
sync
