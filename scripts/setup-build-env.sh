#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname -s)/$(uname -m) != Linux/x86_64 ]] || ! command -v apt-get >/dev/null; then
    printf 'Use x86_64 Ubuntu 24.04 or a compatible apt-based host.\n' >&2
    exit 1
fi
privilege=()
if (( EUID != 0 )); then
    privilege=(sudo)
fi
"${privilege[@]}" apt-get update
"${privilege[@]}" apt-get install --no-install-recommends \
    build-essential bc bison flex libssl-dev libelf-dev dwarves \
    cpio kmod rsync curl openssl ca-certificates
