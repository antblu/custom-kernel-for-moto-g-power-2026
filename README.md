# Moto G Power 2026 unified K3s worker

For an already unlocked Moto G Power 2026 (vegas26) running Android 16 and the stock 5.15.180-android13-8 kernel, with working Magisk 31.1 root. A phone already unlocked with Val Protocol can start here. On the tested XT2617V firmware W1WEOS36.48-22-3-3-4-2, Motorola Fastboot rejected temporary boot and modified init_boot. Confirm recovery on your specific firmware before writing either partition. Firmware with a different boot layout, vendor ABI, or Android policy needs its own validation. [Reference unlock and recovery observations](https://github.com/parsimo2010/moto-g-power-2026-straight-talk-wifi-root-guide)

Use x86-64 Ubuntu 24.04 or WSL2 with sources on the Linux filesystem, Python 3.12, Docker for the Debian rootfs, Google Platform-Tools, and a USB data connection usable in both Android and bootloader Fastboot. Keep your original factory init_boot and a private backup of device data. This workflow uses the kernel-only boot partition and the existing Magisk init_boot ramdisk. It captures vendor_boot for the early-module audit and recovery. [Android boot partition layout](https://source.android.com/docs/core/architecture/partitions/generic-boot)

## 1. Capture and build

Run capture and build from the repository root.

```bash
REPO=$PWD
umask 077
mkdir -p "$REPO/private"
WORK="$REPO/private/phone"
export KERNEL_BUILD_OUTPUT="$REPO/out/unified"

# Optionally set ADB_SERIAL and FASTBOOT_SERIAL for USB target selection.
# Set ADB or FASTBOOT if the executables are outside PATH.
android() { "${ADB:-adb}" ${ADB_SERIAL:+-s "$ADB_SERIAL"} "$@"; }
bootloader() { "${FASTBOOT:-fastboot}" ${FASTBOOT_SERIAL:+-s "$FASTBOOT_SERIAL"} "$@"; }

python3 scripts/deploy-vegas26.py "$WORK" capture
bash scripts/setup-build-env.sh
bash scripts/fetch-sources.sh
bash scripts/build-stock.sh
```

Capture records the active slot and firmware, verifies full readbacks of boot, init_boot and vendor_boot, and saves Android policy and vendor_dlkm modules. The init_boot backup contains your existing Magisk root. Store the entire capture privately and retain it until rollback has been verified.

Set `AOSP_DIR` to an AOSP checkout synced with `repo init -u https://android.googlesource.com/platform/manifest -b android16-release` and `repo sync`. Pin system/core and apply the patches in order in that disposable checkout.

```bash
(
    cd "$AOSP_DIR"
    git -C system/core checkout --detach 68be0c2c0006a0740d0b1809abe4717308f90d15
    for patch in process-domain-attributes threaded-group-cleanup \
        threaded-group-placement process-group-attachment isolated-process-attach-retry; do
        git -C system/core apply "$REPO/patches/android16-$patch.patch"
    done
    printf '\nPRODUCT_CGROUP_V2_SYS_APP_ISOLATION_ENABLED := true\n' \
        >> build/make/target/product/aosp_arm64.mk
    source build/envsetup.sh
    lunch aosp_arm64-aosp_current-userdebug
    m libprocessgroup host_init_verifier
    printf '%s\n' "$ANDROID_PRODUCT_OUT/system/lib64/libprocessgroup.so" > "$REPO/private/library-path"
)
LIBPROCESSGROUP=$(cat "$REPO/private/library-path")
```

With the Android SDK and the pinned Magisk ONDK available, build the ARM64 initializer. Supply a Linux-native Magisk 31.1 magiskboot executable via `MAGISKBOOT` and use AOSP's avbtool.py for the AVB footer. The ARM64 Android magiskboot binary from the APK requires an Android execution environment. [Magisk build prerequisites](https://github.com/topjohnwu/Magisk/blob/v31.1/docs/build.md)

```bash
git clone --recurse-submodules --branch v31.1 https://github.com/topjohnwu/Magisk.git \
    "$REPO/private/magisk"
(
    cd "$REPO/private/magisk"
    test "$(git rev-parse HEAD)" = 0972f67d97f9b6302b67c5171283330c74114b4a || exit 1
    git apply "$REPO/patches/magisk31.1-vegas26-early-library.patch" || exit 1
    printf 'version=31.1\nversionCode=31100\nabiList=arm64-v8a\n' > config.prop
    ./build.py ndk && ./build.py native magiskinit
)
MAGISKINIT="$REPO/private/magisk/native/out/arm64-v8a/magiskinit"
AVBTOOL="$AOSP_DIR/external/avb/avbtool.py"

python3 scripts/deploy-vegas26.py "$WORK" prepare \
    --build "$KERNEL_BUILD_OUTPUT" --library "$LIBPROCESSGROUP" \
    --magiskinit "$MAGISKINIT" --magiskboot "$MAGISKBOOT" --avbtool "$AVBTOOL"
```

Preparation audits both sets of vendor modules against the candidate, checks the target library ABI, transforms the phone's cgroups.json and task_profiles.json, and verifies the repacked Magisk ramdisk. Generated images and policy stay under the private work directory. The Android library keeps the process resource domain when threaded CPU placement fails and falls back to stock paths when unified scheduling is absent.

## 2. Test and deploy

```bash
android reboot bootloader
python3 scripts/deploy-vegas26.py "$WORK" test
```

The temporary test writes no partitions. Fastboot can load only the kernel image in this step. The on-disk init_boot remains active, so acceptance of the image cannot establish that the full pair boots. If it fails to boot, return to the bootloader with the hardware keys and reboot the existing images.

When the bootloader supports both image writes and the recovery path has been verified, return to the bootloader and explicitly flash the pair.

```bash
python3 scripts/deploy-vegas26.py "$WORK" flash --confirm-recovery &&
    bootloader reboot
```

For the reference Val-unlocked bootloader, first verify that you can restore your matching factory boot and factory init_boot before ADB starts. If you choose to proceed without a temporary test, return to working Magisk-rooted Android. Stage init_boot through the existing root, reboot directly to bootloader Fastboot, and flash boot. Proceed to each line only after the previous one succeeds. Complete both writes before starting Android.

```bash
python3 scripts/deploy-vegas26.py "$WORK" stage-init --confirm-recovery --skip-temporary-test &&
    android reboot bootloader
# Wait for bootloader Fastboot.
python3 scripts/deploy-vegas26.py "$WORK" flash --staged-init --confirm-recovery --skip-temporary-test &&
    bootloader reboot
```

After Android has finished booting, verify the installed image hashes, root, early overlay, absence of v1 mounts and delegation of all five controllers. Check Android UI, audio, camera and WebView before adding the worker.

```bash
python3 scripts/deploy-vegas26.py "$WORK" verify
```

## 3. Install the worker

Use a reachable, TLS-valid K3s API endpoint and the same K3s release as the control plane. Set K3S_VERSION, K3S_URL, K3S_NODE_NAME, and K3S_AGENT_TOKEN_FILE locally. Set POD_CIDR and SERVICE_CIDR to the cluster networks and NODE_POD_CIDR to the phone node's assigned PodCIDR. If the control plane assigns the node CIDR after registration, leave NODE_POD_CIDR unset on the first boot. Then read it with `kubectl get node "$K3S_NODE_NAME" -o jsonpath='{.spec.podCIDR}'`, upload network.conf, and reboot. The phone shares Android networking. Keep the agent and its credentials in a trusted cluster. [K3s agent options](https://docs.k3s.io/cli/agent)

```bash
python3 scripts/install-debian.py
R=/data/adb/debian-trixie
C=/etc/rancher/k3s/vegas26
android shell "su -c 'umask 077; mkdir -p $R$C $R/usr/local/bin'"

(
    cd "$REPO/private"
    base="https://github.com/k3s-io/k3s/releases/download/$K3S_VERSION"
    curl -fL "$base/k3s-arm64" -o k3s-arm64 &&
        curl -fL "$base/sha256sum-arm64.txt" -o sha256sum-arm64.txt &&
        awk '$2 == "k3s-arm64" || $2 == "*k3s-arm64"' sha256sum-arm64.txt | sha256sum --check
) || exit 1
upload() { android exec-in "su -c 'umask 077; cat > $R$1'"; }
upload /usr/local/bin/k3s < "$REPO/private/k3s-arm64"
upload "$C/token" < "$K3S_AGENT_TOKEN_FILE"
upload "$C/config.yaml" <<EOF
server: "$K3S_URL"
token-file: "$C/token"
node-name: "$K3S_NODE_NAME"
snapshotter: overlayfs
prefer-bundled-bin: false
kubelet-arg:
  - "cgroup-driver=cgroupfs"
  - "cgroup-root=/k3s"
  - "oom-score-adj=-1000"
EOF
if [ -n "${NODE_POD_CIDR:-}" ]; then
    printf '%s %s %s\n' "$POD_CIDR" "$SERVICE_CIDR" "$NODE_POD_CIDR" | upload "$C/network.conf"
fi
android shell "su -c 'chmod 700 $R/usr/local/bin/k3s; touch $R$C/ext4-storage $R$C/keep-awake'"
python3 scripts/install-debian.py --reuse --k3s-service

# First install only. Pick a size that leaves sufficient Android free space.
android shell "su -c '/data/adb/debian-shell /bin/sh -ec \"umask 077; \
    test ! -e /var/lib/k3s-root.img; fallocate -l 8G /var/lib/k3s-root.img; \
    mkfs.ext4 -F -b 4096 /var/lib/k3s-root.img\"'"
android reboot
```

The Magisk service waits for Android and tini, uses SELinux Permissive, mounts the ext4 loop image for OverlayFS data, applies the netd routing rules, and maintains the k3s_node wake lock. Leave UID 65532 unassigned to Android packages and services. If the cluster uses UID 65532 for CoreDNS or pods, create allow-uid-65532 beside config.yaml so the watcher can apply the scoped netd exemption.

Optional WireGuard uses a private wireguard.conf in wg syntax and wireguard-network.conf with the interface IPv4 address/prefix and MTU on one line. Set the K3s node IP and Flannel interface to the corresponding address and wg-k3s. The reference path used WireGuard MTU 1120 and Flannel MTU 1070. For a custom Wi-Fi interface, put its name in wifi-interface. All files live beside config.yaml.

Verify that the node is Ready, containerd reports SystemdCgroup = false, and a non-root ARM64 pod can resolve DNS, reach services and peers, and read a PVC after replacement. Repeat after reboot. Read the supervisor log at /data/adb/vegas26-k3s.log.

## Roll back

Disable the Android boot hooks while root is available. The early Magisk overlay is removed by restoring init_boot. Keep the private Debian data and ext4 image.

```bash
android shell 'su -c "rm -f /data/adb/service.d/95-vegas26-k3s.sh /data/adb/service.d/90-debian-trixie.sh"'
android reboot bootloader
python3 scripts/deploy-vegas26.py "$WORK" restore &&
    bootloader reboot
```

Restore uses the captured active slot and checks the backup hashes. Use restore --vendor-boot if vendor_boot was independently altered and its matching backup needs restoration. If Fastboot rejects the saved Magisk init_boot, stay in the bootloader and check that boot was restored. Set FACTORY_INIT_BOOT to the matching factory image from your original root backup and verify its recorded hash before running the following commands.

```bash
slot=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["slot"])' "$WORK/capture.json")
bootloader flash "init_boot_$slot" "$FACTORY_INIT_BOOT" &&
    bootloader reboot
```

This restores factory Android boot. Reapply Magisk through the recovery procedure you verified for the phone.
