# Run Debian 13 ARM64 at Android startup

Use a phone running the [namespace kernel](building.md), working Magisk root and BusyBox, USB debugging, Python 3.11 or newer, Docker, and ADB. Debian stays under `/data/adb/debian-trixie`.

## Install

From the repository root:

```sh
python3 scripts/install-debian.py
adb reboot
```

Use `--adb <path-to-adb>` if ADB is outside PATH. On WSL, a working Windows Platform-Tools executable is also usable via its mounted path. Add `--reuse` to preserve an existing trixie filesystem while updating its launcher, resolver, and startup hook.

The installer downloads and exports the digest-pinned official ARM64 Debian image, verifies the archive after transferring it, installs Debian's `tini` package, and registers a Magisk startup service. After Android finishes booting, the service launches `tini` as PID 1 inside Debian's PID namespace. Android retains its own init. The Debian instance has separate PID, mount, IPC, and UTS namespaces and shares Android's network. DNS is copied from Android's active network during setup. Run the installer with `--reuse` to refresh it after a network change.

## Enter and test

```sh
adb shell -t "su -c '/system/bin/sh /data/adb/debian-shell --enter'"
python3 tests/test-debian-phone.py
```

The shell joins the Debian instance started during boot. To disable automatic startup, move `/data/adb/service.d/90-debian-trixie.sh` outside Magisk's service directory as root, then reboot Android.

## Test results

On the test phone, a fresh Android reboot started Debian automatically. The test suite verified Debian 13 ARM64, `tini` as PID 1, the namespace boundaries, Bash, child exit status, signals, file permissions and hard links, device nodes, private pseudoterminals, the writable shared memory directory, DNS, APT index updates, and the installed init package.

This is a usable Debian command-line environment. Debian uses the Android kernel, shares the phone's network, and uses `tini` for startup. Full systemd service management, Docker, cgroup delegation, and hardware access from Debian have not been validated.
