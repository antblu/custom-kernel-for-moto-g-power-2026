#!/system/bin/sh
set -eu
bb=/data/adb/magisk/busybox
until [ "$(getprop sys.boot_completed)" = 1 ]; do sleep 2; done
exec "$bb" flock -n /data/adb/debian-trixie.start.lock \
    /system/bin/sh /data/adb/debian-shell --boot
