#!/usr/bin/env bash
set -euo pipefail

cache=${KERNEL_BUILD_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/moto-g-power-2026-kernel}
mkdir -p -- "$cache"
cache=$(cd -- "$cache" && pwd -P)
exec 9>"$cache/fetch.lock"
flock 9

fetch() (
    local name=$1 revision=$2 url=$3 archive=$4 checksum=$5 target staging input
    target="$cache/$name-$revision"
    if [[ -d $target && $(cat "$target/.source-revision" 2>/dev/null) == "$revision" &&
          $(cat "$target/.archive-sha256" 2>/dev/null) == "$checksum" ]]; then
        return
    fi
    if [[ -e $target ]]; then
        printf 'Incomplete or unexpected source directory: %s\n' "$target" >&2
        return 1
    fi
    staging=$(mktemp -d "$cache/.fetch.XXXXXXXX")
    trap 'rm -rf -- "$staging"' EXIT
    mkdir "$staging/tree"
    input="$cache/$archive"
    if [[ ! -f $cache/$archive ]]; then
        input="$staging/$archive"
        curl --fail --location --retry 2 --silent --show-error "$url" -o "$input"
    fi
    if [[ $(sha256sum < "$input" | cut -d ' ' -f 1) != "$checksum" ]]; then
        printf 'SHA-256 mismatch for %s\n' "$archive" >&2
        return 1
    fi
    if [[ $input != "$cache/$archive" ]]; then
        mv -- "$input" "$cache/$archive"
    fi
    tar -xzf "$cache/$archive" -C "$staging/tree"
    printf '%s\n' "$revision" > "$staging/tree/.source-revision"
    printf '%s\n' "$checksum" > "$staging/tree/.archive-sha256"
    mv -T -- "$staging/tree" "$target"
)

ack=9b2308ac0ad616788fb57ba688aa07f0ff221355
clang=5538393cf30cb39da6d53730a9b85f36958230da
fetch ack "$ack" "https://android.googlesource.com/kernel/common/+archive/$ack.tar.gz" \
    "ack-$ack.tar.gz" 8958fc617980ab37f8c1277a53e8f9d28c61f3ba1e65c417fa24ef8eb08050bc
fetch clang "$clang" "https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+archive/$clang/clang-r450784e.tar.gz" \
    "clang-$clang.tar.gz" 23093368e6b8cb7c66467375220db22a024c652c3fd77499d666b048c51b4d87
