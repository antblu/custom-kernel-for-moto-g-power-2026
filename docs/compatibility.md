# Device findings and build prerequisites

The ADB report came from one Moto G Power 2026 running W1WEOS36.48-22-3-3-4-2. The phone was on slot A and reported an unlocked bootloader and orange Verified Boot state.

| Area | Read-only observation |
| --- | --- |
| Namespaces | PID and user namespaces explicitly disabled. Network, UTS, and time namespaces configured. Mount namespace link present. IPC configuration unknown. |
| Cgroups | cgroup v1 and v2 mounted. The pids controller was explicitly disabled in the kernel configuration. Controller delegation and runtime behavior remain untested. |
| Filesystem and networking | OverlayFS, veth, TUN, bridges, and NAT configured as built-ins. |
| Runtime security | Seccomp filtering and the BPF syscall configured as built-ins. |
| Vendor modules | CONFIG_MODVERSIONS enabled. Existing root access confirmed 197 vendor module dependency records, of which 118 list prerequisites. |
| Partitions | Read-only size probes confirmed boot_a and vendor_boot_a at 64 MiB each, init_boot_a, dtbo_a, and vbmeta_a at 8 MiB each, and super at 11,475,615,744 bytes. |
| Hardware and software | ADB worked on the existing Android installation. Docker, chroots, and the hardware regression checklist have yet to be tested. |

## Boot layout

The active slot's headers were read into memory and reduced to the fields below. Header decoding follows the [AOSP boot image format](https://source.android.com/docs/core/architecture/bootloader/boot-image-header).

| Partition | Observed layout |
| --- | --- |
| boot_a | v4, gzip-compressed kernel of 21,525,939 bytes, zero-byte ramdisk, boot signature size field zero |
| init_boot_a | v4, no kernel, generic ramdisk of 2,631,657 bytes |
| vendor_boot_a | v4, 4,096-byte pages, one legacy-LZ4 ramdisk fragment totaling 30,447,358 bytes, DTB of 183,530 bytes |

AVB footer and descriptor validation, temporary boot support, and recovery procedures remain unverified.

Inspect a local v3 or v4 image with `python scripts/inspect-boot-image.py <private-image-path>`. It reads the header and kernel prefix and reports only layout fields. Keep firmware images in private storage.

## Source and baseline

The running kernel's abbreviated hash resolves to [Android Common Kernel commit 9b2308ac0ad616788fb57ba688aa07f0ff221355](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355). Its build configuration specifies KMI generation 8 on android13-5.15 and Clang r450784e. The running kernel reports Android Clang build 8508608 (14.0.7) and LLD 14.0.7. The upstream GKI build configuration includes Motorola and MediaTek KMI symbol lists.

The Motorola kernel-mtk and kernel-common remote ref checks found no W1WEOS release ref. The [exact-firmware corresponding source request](https://github.com/lenovo/gplcc/issues/25) is a separate lead. The exact ACK commit is a candidate for an experimental unmodified GKI build. The corresponding Motorola vendor sources, vendor module symbol requirements, and firmware-specific boot image inputs remain unverified.

The [build procedure](building.md) pins the ACK and compiler archives and uses direct Kbuild for an offline reference. See the [baseline comparison](baseline-compatibility.md) for config and KMI findings.
