import argparse
import gzip
import io
import json
import re
import subprocess
import sys

PROPERTIES = {
    "manufacturer": ("ro.product.manufacturer", r"motorola"),
    "model": ("ro.product.model", r"moto g power(?: 5g)?(?: -)?(?: \(2026\)| 2026)|XT2617(?:V|-\d{1,2})"),
    "device": ("ro.product.device", r"vegas(?:26)?"),
    "product": ("ro.product.name", r"vegas(?:26)?(?:_[a-z]{1,6}){0,3}"),
    "android": ("ro.build.version.release", r"\d{1,2}(?:\.\d{1,2}){0,2}"),
    "firmware": ("ro.build.id", r"[A-Z][A-Z0-9]{3,16}\.\d{1,4}(?:-\d{1,4}){1,8}"),
    "abi": ("ro.product.cpu.abi", r"arm64-v8a"),
    "slot": ("ro.boot.slot_suffix", r"_[ab]"),
    "verified_boot": ("ro.boot.verifiedbootstate", r"green|yellow|orange|red"),
    "bootloader": ("ro.boot.vbmeta.device_state", r"locked|unlocked"),
}
OPTIONS = (
    "PID_NS", "USER_NS", "IPC_NS", "NET_NS", "UTS_NS", "TIME_NS",
    "CGROUP_PIDS", "CGROUPS", "OVERLAY_FS", "MODVERSIONS",
    "VETH", "TUN", "BRIDGE", "NF_NAT", "SECCOMP_FILTER", "BPF_SYSCALL",
)


def allowed(value, pattern):
    value = value.decode("ascii", errors="replace").strip()
    return value if re.fullmatch(pattern, value, re.IGNORECASE | re.ASCII) else None


def config_values(data):
    if not data:
        return dict.fromkeys(OPTIONS)
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            config = stream.read(4_000_001).decode("ascii")
        if len(config) > 4_000_000 or "# Linux/" not in config:
            return dict.fromkeys(OPTIONS)
    except (OSError, EOFError, UnicodeError):
        return dict.fromkeys(OPTIONS)
    lines = set(config.splitlines())
    return {
        option: next(
            (value for line, value in (
                (f"CONFIG_{option}=y", "built-in"),
                (f"CONFIG_{option}=m", "module"),
                (f"# CONFIG_{option} is not set", "disabled"),
            ) if line in lines),
            None,
        )
        for option in OPTIONS
    }


def collect(adb):
    def read(*args):
        result = subprocess.run(
            [adb, *args], capture_output=True, timeout=15, check=False,
        )
        return result.stdout if result.returncode == 0 else b""

    if read("get-state").strip() != b"device":
        raise RuntimeError("ADB requires exactly one authorized target.")
    report = {
        name: allowed(read("shell", "getprop", prop), pattern)
        for name, (prop, pattern) in PROPERTIES.items()
    }
    report["kernel"] = allowed(
        read("shell", "uname", "-r"),
        r"\d+\.\d+\.\d+-android\d+-\d+(?:-\d+-g[0-9a-f]{7,40})?(?:-ab\d+)?",
    )
    report["config"] = config_values(read("exec-out", "cat", "/proc/config.gz"))
    mounts = read("shell", "cat", "/proc/mounts").splitlines()
    report["cgroup_filesystems"] = sorted({
        fields[2].decode("ascii") for line in mounts
        if len(fields := line.split()) >= 3 and fields[2] in (b"cgroup", b"cgroup2")
    })
    report["compatibility"] = "unverified"
    return report


def main():
    parser = argparse.ArgumentParser(description="Read an allowlisted Android compatibility report.")
    parser.add_argument("--adb", default="adb", help="Path to Google SDK Platform-Tools ADB")
    parser.add_argument("--public-report", required=True, action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(collect(args.adb), indent=2))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, subprocess.TimeoutExpired):
        print("ADB could not be started or did not respond.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
