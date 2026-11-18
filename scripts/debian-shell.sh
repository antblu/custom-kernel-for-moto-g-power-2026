#!/system/bin/sh
set -eu

bb=/data/adb/magisk/busybox
root=/data/adb/debian-trixie

if [ "${1:-}" != --inside ]; then
    exec "$bb" unshare -m -p -f -i -u /system/bin/sh "$0" --inside "$@"
fi
shift

"$bb" mount --make-rprivate /
"$bb" mount -t proc -o nosuid,nodev,noexec proc "$root/proc"
"$bb" mount -t tmpfs -o nosuid,mode=755 tmpfs "$root/dev"
for device in null zero full random urandom tty; do
    : > "$root/dev/$device"
    "$bb" mount --bind "/dev/$device" "$root/dev/$device"
done
"$bb" mount -t tmpfs -o nosuid,nodev,mode=755 tmpfs "$root/run"

if [ "$#" -eq 0 ]; then
    set -- /bin/bash -l
fi
exec "$bb" chroot "$root" /usr/bin/env -i \
    HOME=/root TERM="${TERM:-xterm}" PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "$@"
