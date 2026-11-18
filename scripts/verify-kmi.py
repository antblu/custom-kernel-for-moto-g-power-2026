"""Compare vendor module import CRCs against kernel and companion exports."""

import argparse
from pathlib import Path
import re
import subprocess
import sys

CRC = re.compile(r"0x[0-9a-fA-F]{8}")


def read_exports(paths):
    exports = {}
    for path in paths:
        for line in path.read_text(encoding="ascii").splitlines():
            fields = line.split()
            if len(fields) < 4 or not CRC.fullmatch(fields[0]):
                raise ValueError("Invalid Module.symvers entry.")
            crc, symbol = fields[:2]
            crc = crc.lower()
            if exports.setdefault(symbol, crc) != crc:
                raise ValueError(f"Conflicting export CRCs for {symbol}.")
    if not exports:
        raise ValueError("No exported symbol CRCs available.")
    return exports


def module_versions(path, mode):
    result = subprocess.run(
        ["modprobe", mode, str(path.resolve())],
        capture_output=True, text=True, encoding="ascii", timeout=30,
    )
    if result.returncode and mode == "--show-exports":
        sections = subprocess.check_output(
            ["readelf", "-SW", str(path.resolve())],
            stderr=subprocess.PIPE, text=True, encoding="ascii", timeout=30,
        )
        if "__ksymtab" not in sections:
            return {}
    result.check_returncode()
    versions = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2 or not CRC.fullmatch(fields[0]):
            raise ValueError("Unexpected modprobe version record.")
        crc, symbol = fields
        crc = crc.lower()
        if versions.setdefault(symbol, crc) != crc:
            raise ValueError(f"Conflicting module CRCs for {symbol}.")
    return versions


def module_imports(path):
    return module_versions(path, "--show-modversions")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symvers", type=Path, required=True, action="append")
    parser.add_argument("--include-module-exports", action="store_true")
    parser.add_argument("modules", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        exports = read_exports(args.symvers)
        if args.include_module_exports:
            for module in args.modules:
                for symbol, crc in module_versions(module, "--show-exports").items():
                    if exports.setdefault(symbol, crc) != crc:
                        raise ValueError(f"Conflicting export CRCs for {symbol}.")
        passed = True
        for number, module in enumerate(args.modules, 1):
            imports = module_imports(module)
            missing = sorted(set(imports) - exports.keys())
            mismatches = sorted(
                name for name, crc in imports.items() if name in exports and exports[name] != crc
            )
            if not imports or missing or mismatches:
                passed = False
            print(f"Module {number}: {len(imports)} versioned imports")
            for symbol in missing:
                print(f"  unresolved: {symbol}")
            for symbol in mismatches:
                print(f"  CRC mismatch: {symbol}")
            if not imports:
                print("  no versioned imports found")
        return 0 if passed else 1
    except (OSError, ValueError, subprocess.SubprocessError):
        print("Could not read a complete export or module version table.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
