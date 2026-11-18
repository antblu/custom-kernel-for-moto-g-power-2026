# Experimental baseline compatibility

| Input | Reference value |
| --- | --- |
| Target | Moto G Power 2026, vegas26, Android 16 W1WEOS36.48-22-3-3-4-2 |
| Observed kernel | 5.15.180-android13-8-00018-g9b2308ac0ad6-ab14563692 |
| Direct Kbuild release | 5.15.180 |
| ACK source | 9b2308ac0ad616788fb57ba688aa07f0ff221355 |
| Architecture and config | ARM64, upstream gki_defconfig |
| Compiler | Android Clang build 8508608, Clang and LLD 14.0.7 |

AOSP tagged the exact running source [android13-5.15-2025-05_r14](https://android.googlesource.com/kernel/common/+/refs/tags/android13-5.15-2025-05_r14) and associates it with build 14563692. The matching [kernel superproject revision](https://android.googlesource.com/kernel/superproject/+/a8ede6043543b5f6af5a01928a56fb63022673c5) pins the manifest at `1501b8a4a01d4d848c8ab6c00396faa0cd573b15`, kernel/build at `b05fb2e75ba86f934da7fbcb4435678a54645c5f`, and the Clang prebuilt repository at `9f759dee5cdc5f85d076c642a192f6a9232f7058`. The archive selected for the direct build has identical compiler and linker files and compiler headers. Its clang-tidy wrapper and Linux compiler runtime library subtree differ from the superproject pin.

The decompressed kernel payload from the phone's active boot partition matched the SHA-256 of the 47,512,064-byte ARM64 Image in [Google's certified r14 boot archive](https://dl.google.com/android/gki/gki-certified-boot-android13-5.15-2025-05_r14.zip). The phone payload was hashed on-device. This verifies the kernel payload; Motorola's vendor boot components and modules still require independent compatibility checks.

The live ADB report and generated config agree on 15 allowlisted settings. IPC namespace status was unknown in both. The agreement covers several container prerequisites and confirms the three observed gaps. It provides no evidence about the rest of the configuration.

The ACK source revision matches the running kernel's abbreviated revision. Firmware-specific Motorola sources remain unverified. The build uses direct Kbuild and leaves export trimming disabled. The source archive and direct build omit Android's release suffix, which must be checked separately when assessing module compatibility. Official Android KMI and ABI validation requires the Android build pipeline. The static CRC comparison covers symbol versions. Boot and driver behavior require separate tests.

## Local build and vendor CRCs

The Ubuntu 24.04 WSL build completed with the unchanged ARM64 GKI defconfig. The ARM64 Image, System.map, .config, and Module.symvers passed their manifest checksum checks. The local symbol table contains 15,406 entries.

The module files were held in restricted temporary storage and removed after inspection. The comparison includes the complete vendor_dlkm module set and the regular module files in the legacy-LZ4 vendor boot ramdisk.

| Module set | Files inspected | Imports matching local build CRCs | Imports matching companion CRCs | Unresolved or mismatched |
| --- | ---: | ---: | ---: | ---: |
| vendor_dlkm | 197 | 10,284 | 1,642 | 0 |
| Vendor boot ramdisk | 202 | 8,399 | 908 | 0 |

Before including the early-boot modules, the vendor_dlkm audit had 505 unresolved import records across 60 modules. Including the ramdisk resolved all of them. Neither module set contained conflicting companion export CRCs.

The checked-in AOSP ABI XML is a separate reference. All 8,481 of its CRC-bearing symbols are present in the local build, and 478 have a different CRC. Substituting the XML for the compiled symbol table would report 626 vendor_dlkm and 559 early-boot import CRC mismatches. The baseline retains the compiled symbol table for import comparison. Official ABI checks remain pending.

## PID controller candidate

The [pids controller fragment](../configs/fragments/cgroup-pids.config) enabled exactly one setting, CONFIG_CGROUP_PIDS. The ARM64 candidate built successfully and all four artifact checksums passed. Its symbol table added two exports, removed none, and changed 6,356 CRCs relative to the baseline.

| Module set | Import CRC mismatches | Files affected |
| --- | ---: | ---: |
| vendor_dlkm | 2,216 | 197 of 197 |
| Vendor boot ramdisk | 2,060 | 202 of 202 |

The candidate is **incompatible with the existing vendor modules** and must stay off the device. The pids controller adds an entry to the subsystem enum, increasing `CGROUP_SUBSYS_COUNT` from seven to eight. BTF from the two compiled builds confirms that `struct css_set` grew from 424 to 448 bytes and `struct cgroup` from 2,400 to 2,424 bytes. In `css_set`, the `e_cset_node` array moved from offset 152 to 160.

The `kernel/fork.symtypes` record traces `get_task_mm` through `task_struct` and its `cgroups` pointer to `css_set` and the subsystem count. The CRC changed from `0x5c9998cf` to `0xfa229ccf` even though `task_struct` stayed 4,608 bytes. A KMI-preserving design would need to preserve existing layouts and subsystem indices. CRC overrides would leave the layout differences in place. [Android kernel ABI monitoring](https://source.android.com/docs/core/architecture/kernel/abi-monitor)

Baseline compatibility status is **Experimental**. The [Android hardware and Linux runtime checks](hardware-tests.md) require separate device testing. Recovery and temporary boot support are unverified.

## Container host candidate

The [container-host profile](building.md#build-the-container-host-profile) built an ARM64 Image with all 59 requested settings built in. The Image, System.map, .config, and Module.symvers passed checksum verification. The candidate added 502 exports, removed none, and changed 10,148 shared CRCs relative to the unmodified baseline.

| Module set | Import CRC mismatches | Files affected |
| --- | ---: | ---: |
| vendor_dlkm | 4,365 | 197 of 197 |
| Vendor boot ramdisk | 4,197 | 202 of 202 |

This candidate is unsuitable for installation with the current vendor modules. The profile is a buildable record of the requested feature set. To isolate work that could preserve the vendor ABI, test individual options or small dependency groups against the unmodified baseline.

## Namespace-only candidate

The [namespace-only build](building.md#build-the-namespace-only-profile) enabled PID, user, and IPC namespaces with POSIX message queues. The build and manifest checks passed. It added 12 exports and preserved all 15,406 baseline export CRCs. All versioned imports in the 197 `vendor_dlkm` and 202 early-boot vendor module files resolved with matching CRCs.

An ARM64 QEMU guest ran an init program that created a child with mount, UTS, IPC, user, PID, and network namespaces. The child observed itself as PID 1 and successfully unshared its time namespace for children. The unmodified baseline failed the same test. Android's SELinux policy, device hardware, and a container runtime still require on-device verification.

The phone returned to stock Android after the [temporary stock boot probes](recovery.md). Both verified stock image formats returned to Fastboot when loaded temporarily. The candidate remained off-device pending a verified installation and recovery path.
