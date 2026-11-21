# Build the namespace kernel

Keep the source cache and build output on the Linux filesystem.

```bash
bash scripts/setup-build-env.sh
bash scripts/fetch-sources.sh
JOBS=8 bash scripts/build-stock.sh
JOBS=8 bash scripts/build-stock.sh --namespaces
```

The fetcher checks the pinned Android Common Kernel and Clang archives before extraction. The first build produces the unmodified GKI reference. The second enables PID, user, and IPC namespaces, using POSIX message queues for the IPC dependency. Network, UTS, and time namespaces are built into the baseline. Both builds record artifact checksums in build-manifest.txt.

The cache defaults to `${XDG_CACHE_HOME:-$HOME/.cache}/moto-g-power-2026-kernel`. The namespace Image is under `out/experimental-namespaces/arch/arm64/boot/Image`.

## Verify before installing

Use the Image and the complete vendor module sets from the same firmware. Include both vendor_dlkm and vendor boot ramdisk modules, stored privately.

```bash
python3 scripts/verify-kmi.py --symvers <namespace-build-output>/Module.symvers \
    --include-module-exports <private-vendor-module-paths>
bash tests/test-namespaces-vm.sh <namespace-Image>
```

The VM test requires Ubuntu's qemu-system-arm package. It creates an ARM64 guest and checks that a child starts as PID 1 in new namespaces. See the [verified results](baseline-compatibility.md) and [installation and recovery procedure](recovery.md).
