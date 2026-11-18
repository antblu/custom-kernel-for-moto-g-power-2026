# Debian 13 ARM64 on Android

Debian trixie-slim was installed as a root filesystem under `/data/adb/debian-trixie` on the Moto G Power 2026 running the namespace kernel. The source was the official Debian ARM64 OCI image from `docker.io/library/debian` at digest `sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2`. The exported filesystem was SHA-256 checked after transfer before extraction.

## Open a Debian shell

```sh
adb shell -t "su -c '/system/bin/sh /data/adb/debian-shell'"
```

The [launcher](../scripts/debian-shell.sh) uses Magisk BusyBox to create private mount, PID, IPC, and UTS namespaces before entering the Debian root filesystem. Debian shares Android's network namespace. Its resolver was configured from the phone's active network and may need updating when that network changes. The launcher runs on demand.

## Verified on the phone

- Debian reports version 13 and architecture arm64.
- The Debian test process ran as PID 1 with its own proc filesystem.
- DNS resolution and `apt-get update` succeeded over Android's network.

Docker, systemd as PID 1, and cgroup delegation remain untested.
