# Verified kernel results

The running stock kernel on Android 16 build W1WEOS36.48-22-3-3-4-2 matches the certified [Android GKI r14 kernel payload](https://android.googlesource.com/kernel/common/+/refs/tags/android13-5.15-2025-05_r14). The project builds the matching Android Common Kernel commit using Android Clang build 8508608.

The namespace build added 12 exports and preserved all 15,406 baseline export CRCs. All 197 vendor_dlkm and 202 early-boot vendor module files passed the versioned import check. The Image, System.map, .config, and Module.symvers passed their manifest checksums.

In ARM64 QEMU, a child ran as PID 1 with mount, UTS, IPC, user, PID, and network namespaces and successfully created a time namespace for its children.

The candidate booted on the phone. Android root remained available and SELinux stayed enforcing. PID, mount, network, IPC, and user namespace tests passed. A nested PID 1 mounted its own proc filesystem. The phone reported 360 loaded modules with zero module version and unresolved-symbol messages in the sampled kernel log.

See [Debian userspace tests](debian.md). Official Android ABI validation and the [full hardware regression checklist](hardware-tests.md) remain pending.
