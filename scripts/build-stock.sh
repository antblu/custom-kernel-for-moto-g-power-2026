#!/usr/bin/env bash
set -euo pipefail

cache=${KERNEL_BUILD_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/moto-g-power-2026-kernel}
ack=9b2308ac0ad616788fb57ba688aa07f0ff221355
clang=5538393cf30cb39da6d53730a9b85f36958230da
source_dir="$cache/ack-$ack"
toolchain="$cache/clang-$clang/bin"
profile=experimental-gki
if (( $# > 1 )); then
    printf 'Usage: bash scripts/build-stock.sh [--namespaces]\n' >&2
    exit 2
fi
fragment=
case ${1:-} in
    '') ;;
    --namespaces) profile=experimental-namespaces; fragment=namespaces.config ;;
    *) printf 'Unknown build profile: %s\n' "$1" >&2; exit 2 ;;
esac
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
if [[ -n $fragment && $output == "$(realpath -m "$cache/out/experimental-gki")" ]]; then
    printf 'Use a separate output directory for candidate builds.\n' >&2
    exit 1
fi
exec 9>"$output/.build.lock"
flock -n 9 || { printf 'This build output is in use.\n' >&2; exit 1; }
jobs=${JOBS:-$(nproc)}
export PATH="$toolchain:$PATH"
build=(make -C "$source_dir" "O=$output" ARCH=arm64 LLVM=1 LLVM_IAS=1 KCFLAGS=-D__ANDROID_COMMON_KERNEL__)
configure() {
    "${build[@]}" gki_defconfig || return
    if [[ -n $fragment ]]; then
        local setting
        "$source_dir/scripts/kconfig/merge_config.sh" -m -O "$output" "$output/.config" \
            "$project/configs/fragments/$fragment" || return
        "${build[@]}" olddefconfig || return
        while IFS= read -r setting; do
            [[ $setting == CONFIG_*=y ]] || continue
            if ! grep -Fxq -- "$setting" "$output/.config"; then
                printf 'Kconfig did not resolve %s\n' "$setting" >&2
                return 1
            fi
        done < "$project/configs/fragments/$fragment"
    fi
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
for artifact in arch/arm64/boot/Image System.map .config Module.symvers; do
    test -s "$output/$artifact"
done
(
    cd -- "$output"
    printf 'profile=%s\nack_revision=%s\nclang_revision=%s\ncompiler=%s\n' "$profile" "$ack" "$clang" "$compiler"
    printf 'ack_archive_sha256=%s\nclang_archive_sha256=%s\n' \
        "$(cat "$source_dir/.archive-sha256")" "$(cat "$toolchain/../.archive-sha256")"
    sha256sum arch/arm64/boot/Image System.map .config Module.symvers
) > "$output/build-manifest.txt"
printf 'Build complete. Manifest: %s/build-manifest.txt\n' "$output"
