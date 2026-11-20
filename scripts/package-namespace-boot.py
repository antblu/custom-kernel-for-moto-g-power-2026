"""Package the audited ARM64 Image using the matching stock v4 boot header."""

import argparse
import gzip
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

PAGE = 4096


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock_boot", type=Path)
    parser.add_argument("build_output", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    image = (args.build_output / "arch/arm64/boot/Image").read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    manifest = (args.build_output / "build-manifest.txt").read_text().splitlines()
    if (f"{digest}  arch/arm64/boot/Image" not in manifest or
            "profile=experimental-namespaces-pids-vxlan-k3s-unified" not in manifest or image[56:60] != b"ARM\x64"):
        parser.error("Expected a manifest-verified namespace build.")
    inspector = Path(__file__).with_name("inspect-boot-image.py")
    info = json.loads(subprocess.check_output([sys.executable, inspector, args.stock_boot]))
    if (info["type"] != "boot" or info["header_version"] != 4 or
            info["ramdisk_bytes"] or info["boot_signature_bytes"]):
        parser.error("Expected the matching stock v4 partition without an embedded ramdisk.")
    with args.stock_boot.open("rb") as stock:
        header = bytearray(stock.read(PAGE))
    partition_size = args.stock_boot.stat().st_size

    encoding = info["kernel_encoding"]
    if encoding == "gzip":
        payload = gzip.compress(image, mtime=0)
    elif encoding == "arm64-image":
        payload = image
    elif encoding in ("lz4-legacy", "lz4-frame"):
        options = ["-l"] if encoding == "lz4-legacy" else []
        payload = subprocess.run(["lz4", "-z", "-c", *options], input=image,
                                 capture_output=True, check=True).stdout
    else:
        parser.error("Unknown stock kernel encoding.")
    padding = bytes(-len(payload) % PAGE)
    if PAGE + len(payload) + len(padding) > partition_size:
        parser.error("The candidate exceeds the boot partition size.")
    struct.pack_into("<I", header, 8, len(payload))
    with args.output.open("xb") as output:
        output.write(header)
        output.write(payload)
        output.write(padding)
    print("Wrote unsigned v4 image. Keep the image private and verify rollback before flashing.")


if __name__ == "__main__":
    main()
