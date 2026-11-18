"""Print numeric metadata for Android v3 and v4 boot images without extracting data."""

import argparse
import json
from pathlib import Path
import struct
import sys

BOOT_PAGE = 4096


def page_aligned(size, page):
    return ((size + page - 1) // page) * page


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def kernel_encoding(data):
    if data.startswith(b"\x1f\x8b"):
        return "gzip"
    if data.startswith(b"\x02\x21\x4c\x18"):
        return "lz4-legacy"
    if data.startswith(b"\x04\x22\x4d\x18"):
        return "lz4-frame"
    if data[56:60] == b"ARM\x64":
        return "arm64-image"
    return "unknown"


def boot_info(header, image_size, stream):
    version = u32(header, 40)
    if version not in (3, 4):
        raise ValueError("Only Android boot header v3 and v4 are supported.")
    header_size = u32(header, 20)
    if header_size != (1584 if version == 4 else 1580):
        raise ValueError("Unexpected boot header size.")
    kernel, ramdisk = struct.unpack_from("<II", header, 8)
    signature = u32(header, 1580) if version == 4 else 0
    regions = [size for size in (kernel, ramdisk, signature) if size]
    required = BOOT_PAGE + sum(page_aligned(size, BOOT_PAGE) for size in regions[:-1])
    required += regions[-1] if regions else 0
    if image_size < required:
        raise ValueError("Image is shorter than its boot header declares.")
    encoding = None
    if kernel:
        stream.seek(BOOT_PAGE)
        encoding = kernel_encoding(stream.read(min(kernel, 64)))
    return {
        "type": "boot",
        "header_version": version,
        "kernel_bytes": kernel,
        "kernel_encoding": encoding,
        "ramdisk_bytes": ramdisk,
        "boot_signature_bytes": signature,
    }


def vendor_info(header, image_size):
    version, page = struct.unpack_from("<II", header, 8)
    if version not in (3, 4):
        raise ValueError("Only vendor boot header v3 and v4 are supported.")
    header_size, dtb = struct.unpack_from("<II", header, 2096)
    if page < 2048 or page > 65536 or page & (page - 1):
        raise ValueError("Invalid vendor boot page size.")
    if header_size != (2128 if version == 4 else 2112):
        raise ValueError("Unexpected vendor boot header size.")
    ramdisk = u32(header, 24)
    table, fragments, entry, bootconfig = (0, 0, 0, 0)
    if version == 4:
        table, fragments, entry, bootconfig = struct.unpack_from("<IIII", header, 2112)
        if table != fragments * entry or (fragments and entry < 108):
            raise ValueError("Invalid vendor ramdisk table size.")
    regions = [size for size in (header_size, ramdisk, dtb, table, bootconfig) if size]
    required = sum(page_aligned(size, page) for size in regions[:-1]) + regions[-1]
    if image_size < required:
        raise ValueError("Image is shorter than its vendor boot header declares.")
    return {
        "type": "vendor_boot",
        "header_version": version,
        "page_bytes": page,
        "vendor_ramdisk_bytes": ramdisk,
        "vendor_ramdisk_fragments": fragments,
        "dtb_bytes": dtb,
        "bootconfig_bytes": bootconfig,
    }


def inspect(path):
    with path.open("rb") as stream:
        header = stream.read(BOOT_PAGE)
        stream.seek(0, 2)
        image_size = stream.tell()
        if header.startswith(b"ANDROID!"):
            return boot_info(header, image_size, stream)
        if header.startswith(b"VNDRBOOT"):
            return vendor_info(header, image_size)
        raise ValueError("Unknown Android boot image magic.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.image), indent=2))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, struct.error):
        print("Could not read a complete boot image header.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
