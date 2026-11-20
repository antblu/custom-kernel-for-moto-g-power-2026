#!/usr/bin/env bash
set -euo pipefail

cache=${KERNEL_BUILD_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/moto-g-power-2026-kernel}
ack=9b2308ac0ad616788fb57ba688aa07f0ff221355
clang=5538393cf30cb39da6d53730a9b85f36958230da
source_dir="$cache/ack-$ack"
toolchain="$cache/clang-$clang/bin"
profile=experimental-namespaces-pids-vxlan-k3s-unified
if (( $# > 1 )) || [[ ${1:---k3s-unified} != --k3s-unified ]]; then
    printf 'Usage: bash scripts/build-stock.sh [--k3s-unified]\n' >&2
    exit 2
fi
fragments=(namespaces.config pids.config vxlan.config cfs-bandwidth.config
           bridge-netfilter.config k3s-netfilter.config cgroup-v2-only.config)
output=${KERNEL_BUILD_OUTPUT:-$cache/out/$profile}
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

if [[ $(uname -s)/$(uname -m) != Linux/x86_64 ]]; then
    printf 'The pinned toolchain requires x86_64 Linux.\n' >&2
    exit 1
fi
if [[ ! -f $source_dir/Makefile || ! -x $toolchain/clang ]]; then
    printf 'Run bash scripts/fetch-sources.sh first.\n' >&2
    exit 1
fi
for tool in make gcc flex bison bc pahole openssl flock; do
    if ! command -v "$tool" >/dev/null; then
        printf 'Missing build tool: %s\n' "$tool" >&2
        exit 1
    fi
done
compiler=$("$toolchain/clang" --version | sed -n '1p')
if [[ $compiler != *8508608* || $compiler != *'clang version 14.0.7'* ]]; then
    printf 'Unexpected Android Clang build.\n' >&2
    exit 1
fi

mkdir -p -- "$output"
output=$(cd -- "$output" && pwd -P)
exec 9>"$output/.build.lock"
flock -n 9 || { printf 'This build output is in use.\n' >&2; exit 1; }
jobs=${JOBS:-$(nproc)}
export PATH="$toolchain:$PATH"
kcflags=-D__ANDROID_COMMON_KERNEL__
command -v patch >/dev/null || { printf 'Missing build tool: patch\n' >&2; exit 1; }
patches=("$project/patches/pids-legacy-slot.patch"
         "$project/patches/bridge-legacy-skb-ext.patch"
         "$project/patches/cfs-separate-state.patch")
kcflags+=' -DMOTO_PIDS_LEGACY_SLOT -DMOTO_BRIDGE_LEGACY_SKB_EXT'
patch_hash=$(cat -- "${patches[@]}" | sha256sum)
patched_source="$cache/pids-source-${patch_hash%% *}"
(
    flock 8
    if [[ ! -d $patched_source ]]; then
        staging=$(mktemp -d "$cache/pids-source.XXXXXXXX")
        trap 'rm -rf -- "$staging"' EXIT
        cp -al -- "$source_dir/." "$staging"
        for patch_file in "${patches[@]}"; do
            patch --batch --fuzz=0 -d "$staging" -p1 < "$patch_file"
        done
        mv -T -- "$staging" "$patched_source"
    fi
) 8>"$patched_source.lock"
source_dir=$patched_source
build=(make -C "$source_dir" "O=$output" ARCH=arm64 LLVM=1 LLVM_IAS=1 "KCFLAGS=$kcflags")
configure() {
    "${build[@]}" gki_defconfig || return
    local fragment setting
    local paths=()
    for fragment in "${fragments[@]}"; do
        paths+=("$project/configs/fragments/$fragment")
    done
    "$source_dir/scripts/kconfig/merge_config.sh" -m -O "$output" "$output/.config" "${paths[@]}" || return
    "${build[@]}" olddefconfig || return
    for fragment in "${paths[@]}"; do
        while IFS= read -r setting; do
            [[ $setting == CONFIG_*=y || $setting == CONFIG_CMDLINE=* ||
                $setting == '# CONFIG_'*' is not set' ]] || continue
            if ! grep -Fxq -- "$setting" "$output/.config"; then
                printf 'Kconfig did not resolve %s\n' "$setting" >&2
                return 1
            fi
        done < "$fragment"
    done
}
printf 'Building %s in %s\n' "$profile" "$output"
rm -f -- "$output/build-manifest.txt"
{
    configure &&
    "${build[@]}" -j "$jobs" Image modules
} > "$output/build.log" 2>&1 || {
    tail -n 35 "$output/build.log" >&2
    exit 1
}
# These facilities come from gki_defconfig and must stay built in.
for symbol in EXT4_FS BLK_DEV_LOOP OVERLAY_FS WIREGUARD NETFILTER_XT_MATCH_QUOTA2; do
    if ! grep -Fxq "CONFIG_${symbol}=y" "$output/.config"; then
        printf 'Kconfig must build in %s\n' "$symbol" >&2
        exit 1
    fi
done
for artifact in arch/arm64/boot/Image System.map .config Module.symvers; do
    test -s "$output/$artifact"
done
(
    cd -- "$output"
    printf 'profile=%s\nack_revision=%s\nclang_revision=%s\ncompiler=%s\n' "$profile" "$ack" "$clang" "$compiler"
    printf 'ack_archive_sha256=%s\nclang_archive_sha256=%s\n' \
        "$(cat "$source_dir/.archive-sha256")" "$(cat "$toolchain/../.archive-sha256")"
    printf 'kernel_patch_sha256=%s\n' "${patch_hash%% *}"
    sha256sum arch/arm64/boot/Image System.map .config Module.symvers
) > "$output/build-manifest.txt"
printf 'Build complete. Manifest: %s/build-manifest.txt\n' "$output"
