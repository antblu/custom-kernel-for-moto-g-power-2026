# Build the experimental GKI baseline

Use x86_64 Ubuntu 24.04 or WSL2 with Ubuntu 24.04. The default cache and outputs live on the Linux filesystem, including when the project checkout is on a Windows drive.

```bash
bash scripts/setup-build-env.sh
bash scripts/fetch-sources.sh
JOBS=8 bash scripts/build-stock.sh
```

The setup script installs host dependencies. The fetch script downloads source and Android Clang archives from immutable AOSP revisions and checks their SHA-256 digests before extraction. The digests were recorded from the initial HTTPS downloads. The build script uses the upstream ARM64 GKI defconfig and checks the Android compiler build number. Set KERNEL_BUILD_CACHE or KERNEL_BUILD_OUTPUT to an absolute path to change where files go. Build logs and the manifest stay in the output directory.

The baseline uses direct Kbuild. Its artifacts are an unmodified ACK reference for offline comparisons. Official Android build orchestration, KMI symbol trimming and ABI checks, and Motorola packaging still need separate validation. The manifest records archive and artifact hashes. Host dependencies come from Ubuntu's package repositories, so the manifest by itself provides no claim of bit-for-bit reproducibility.

## Check vendor module CRCs

With legally obtained vendor modules kept in private storage, run the static import check against the baseline:

```bash
python3 scripts/verify-kmi.py --symvers <build-output>/Module.symvers <private-directory>/<module>.ko
```

Repeat --symvers to include companion symbol tables. Pass --include-module-exports with the complete vendor module set to include exports read directly from those modules. The tool stops on conflicting export CRCs. Matching CRCs cover the supplied versioned imports only. Module load policy, Android ABI checks, and runtime driver behavior require separate validation.

## Validate the pids controller configuration

Set ACK_SOURCE, CLANG_BIN, and BASELINE_CONFIG to the absolute paths of the fetched ACK directory, the pinned Clang bin directory, and the completed baseline's .config. Run these commands from the repository root.

```bash
candidate=$(mktemp -d)
export PATH="$CLANG_BIN:$PATH"
"$ACK_SOURCE/scripts/kconfig/merge_config.sh" -m -O "$candidate" \
    "$BASELINE_CONFIG" "$PWD/configs/fragments/cgroup-pids.config"
make -C "$ACK_SOURCE" O="$candidate" ARCH=arm64 LLVM=1 LLVM_IAS=1 olddefconfig
"$ACK_SOURCE/scripts/diffconfig" "$BASELINE_CONFIG" "$candidate/.config"
```

The expected diff is `CGROUP_PIDS n -> y`. This check produces a configuration for a future candidate build.

To compile the candidate, run `JOBS=8 bash scripts/build-stock.sh --cgroup-pids`. It verifies the same one-option diff before compilation and writes to the separate `out/experimental-cgroup-pids` directory under the Linux build cache by default. Use the candidate's `Module.symvers` to repeat the full vendor CRC comparison.

## Build the container host profile

```bash
JOBS=8 bash scripts/build-stock.sh --container-host
```

The [container-host fragment](../configs/fragments/container-host.config) requires all requested namespace, cgroup, filesystem, network, security, and VPN options to resolve as built-ins. The script checks the result after `olddefconfig`. It also checks that the two KMI-gated options, `CONFIG_CGROUP_PIDS` and `CONFIG_CFS_BANDWIDTH`, remain disabled. Outputs default to `out/experimental-container-host` in the Linux build cache.

Use the profile for offline builds and vendor CRC checks. Runtime Docker, VPN, and filesystem behavior requires separate tests. In particular, `NF_TABLES` enables the core, and individual nftables families and expressions have their own Kconfig options.

## Build the namespace-only profile

```bash
JOBS=8 bash scripts/build-stock.sh --namespaces
```

The [namespace fragment](../configs/fragments/namespaces.config) adds PID, user, and IPC namespaces to the stock GKI configuration. POSIX message queues satisfy the IPC namespace dependency. System V IPC changed CRCs in all four sampled kernel objects, so it is disabled in this profile. Network, UTS, and time namespaces are already built in on this baseline. Outputs default to `out/experimental-namespaces` in the Linux build cache.

Run the vendor CRC check on the complete module sets before booting a candidate. A namespace-enabled config still requires on-device tests for namespace creation and the intended container runtime.

On Ubuntu, install `qemu-system-arm` to run the offline ARM64 namespace smoke test. Use the candidate's uncompressed kernel Image.

```bash
bash tests/test-namespaces-vm.sh <candidate-Image>
```

The isolated guest reports `NAMESPACE_SMOKE_PASS` when a nested PID 1 and the requested namespace operations work.

An isolated `CFS_BANDWIDTH` Kconfig experiment enabled only that setting. The scheduler core and fair-scheduler objects changed 64 export CRCs. Comparing just those changes with the phone's modules identified 97 mismatched imports in 36 `vendor_dlkm` files and 38 mismatches in 23 early-boot module files. The profile leaves this option disabled.
