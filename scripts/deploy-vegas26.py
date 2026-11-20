"""Capture, package, test, flash and restore a firmware-matched vegas26 image pair."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import stat
import tarfile
import tempfile

SCRIPTS = Path(__file__).resolve().parent
PARTITIONS = ("boot", "init_boot", "vendor_boot")
POLICY_FILES = (
    "system/etc/cgroups.json",
    "system/etc/task_profiles.json",
    "system/etc/init/hw/init.rc",
    "system/lib64/libprocessgroup.so",
    "product/etc/init/init.mmi.product.rc",
    "system_ext/etc/init/hw/meta_init.system.rc",
    "vendor/etc/cgroups.json",
    "vendor/etc/task_profiles.json",
    "vendor/etc/init/hw/init.cgroup.rc",
    "vendor/etc/init/hw/init.mt6835.rc",
    "vendor/etc/init/hw/factory_init.rc",
    "vendor/etc/init/vendor.mediatek.hardware.mtkpower@1.0-init.rc",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(tool, env, serial=None):
    executable = os.environ.get(tool.upper(), tool)
    selector = os.environ.get(env) or serial
    return [executable, "-s", selector] if selector else [executable]


def invoke(args, *, capture=False, timeout=180, **kwargs):
    return subprocess.run(args, check=True, capture_output=capture, timeout=timeout, **kwargs)


def root(adb, action, **kwargs):
    return invoke([*adb, "exec-out", "su -c " + shlex.quote(action)], **kwargs)


def read_root(adb, action):
    return root(adb, action, capture=True).stdout.decode().strip()


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def block(name, slot):
    return f"/dev/block/by-name/{name}_{slot}"


def capture(work):
    adb = command("adb", "ADB_SERIAL")
    props = (
        "ro.product.device", "ro.build.version.sdk", "ro.boot.slot_suffix",
        "ro.boot.vbmeta.device_state", "ro.boot.flash.locked", "ro.serialno",
        "ro.build.fingerprint",
    )
    query = "; ".join(f"getprop {name}" for name in props)
    device, sdk, suffix, lock, locked, serial, firmware, uid = read_root(adb, query + "; id -u").splitlines()
    require(device == "vegas26" and sdk == "36" and uid == "0",
            "Expected an authorized root shell on Android 16 vegas26")
    require(suffix in ("_a", "_b"), "Expected an active A/B slot")
    require(lock == "unlocked" or locked == "0", "Expected an unlocked bootloader")
    require(re.fullmatch(r"[A-Za-z0-9_.:-]+", serial), "Cannot identify the target phone")
    adb = command("adb", "ADB_SERIAL", serial)
    require(read_root(adb, "magisk -V") == "31100", "Expected existing Magisk 31.1 root")
    release = read_root(adb, "uname -r")
    require(re.match(r"5\.15\.180-android13-8(?:-|$)", release),
            "Capture from the matching stock kernel before installing the unified pair")
    require("cgroup_no_v1=all" not in read_root(adb, "cat /proc/cmdline"),
            "Capture from the stock-policy boot, before installing the overlay")
    slot = suffix[1]
    work.mkdir(mode=0o700)
    backups = work / "backups"
    backups.mkdir()
    images = {}
    for name in PARTITIONS:
        path = block(name, slot)
        size = int(read_root(adb, f"blockdev --getsize64 {path}"))
        expected = read_root(adb, f"sha256sum {path}").split()[0]
        image = backups / f"{name}.img"
        with image.open("xb") as stream:
            root(adb, f"cat {path}", stdout=stream)
        require(image.stat().st_size == size and sha256(image) == expected,
                f"Incomplete or changed partition read for {name}")
        images[name] = {"size": size, "sha256": expected}

    with (work / "vendor-dlkm.tar").open("xb") as stream:
        root(adb, "cd /vendor_dlkm/lib/modules && tar -chf - .", stdout=stream)

    policy_hashes = {}
    for name in POLICY_FILES:
        dest = work / "firmware" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as stream:
            root(adb, f"cat /{name}", stdout=stream)
        expected = read_root(adb, f"sha256sum /{name}").split()[0]
        require(dest.stat().st_size > 0 and sha256(dest) == expected, f"Incomplete policy read for {name}")
        policy_hashes[name] = expected
    require(read_root(adb, "getprop ro.boot.slot_suffix; getprop ro.build.fingerprint").splitlines()
            == [suffix, firmware], "Firmware or active slot changed during capture")
    write_json(work / "capture.json", {
        "slot": slot, "serial": serial, "firmware": firmware, "images": images, "policy": policy_hashes,
        "vendor_dlkm": sha256(work / "vendor-dlkm.tar"),
    })
    print(f"Verified three active-slot backups and target firmware policy in {work}.")


def baseline(work):
    data = json.loads((work / "capture.json").read_text(encoding="utf-8"))
    require(data["slot"] in ("a", "b"), "Invalid captured slot")
    for name in PARTITIONS:
        file = work / "backups" / f"{name}.img"
        meta = data["images"][name]
        require(file.stat().st_size == meta["size"] and sha256(file) == meta["sha256"],
                f"Backup verification failed for {name}")
    return data


def early_modules(archive):
    data = memoryview(archive.read_bytes())
    offset = 0
    while offset + 110 <= len(data):
        header = bytes(data[offset:offset + 110])
        require(header[:6] in (b"070701", b"070702"), "Unexpected vendor ramdisk CPIO format")
        mode = int(header[14:22], 16)
        size = int(header[54:62], 16)
        name_size = int(header[94:102], 16)
        offset += 110
        name = bytes(data[offset:offset + name_size])
        require(name.endswith(b"\0"), "Invalid vendor ramdisk CPIO entry")
        offset = (offset + name_size + 3) & ~3
        if name == b"TRAILER!!!\0":
            return
        require(offset + size <= len(data), "Truncated vendor ramdisk CPIO entry")
        if stat.S_ISREG(mode) and name.endswith(b".ko\0"):
            yield data[offset:offset + size]
        offset = (offset + size + 3) & ~3
    raise ValueError("Missing vendor ramdisk CPIO trailer")


def audit_kmi(work, build, magiskboot):
    symvers = build / "Module.symvers"
    manifest = (build / "build-manifest.txt").read_text(encoding="utf-8").splitlines()
    require(f"{sha256(symvers)}  Module.symvers" in manifest, "Kernel export manifest mismatch")
    with tempfile.TemporaryDirectory(prefix="vegas26-kmi-") as temp:
        scratch = Path(temp)
        # Magiskboot returns 3 after a successful vendor_boot unpack.
        result = subprocess.run(
            [magiskboot.resolve(), "unpack", work / "backups/vendor_boot.img"], cwd=scratch, timeout=180
        )
        require(result.returncode == 3, "Magiskboot could not unpack the captured vendor_boot")
        modules = []

        def add(content):
            path = scratch / f"module-{len(modules)}.ko"
            path.write_bytes(content)
            modules.append(path)

        for archive in sorted(scratch.rglob("*.cpio")):
            for content in early_modules(archive):
                add(content)
        early_count = len(modules)
        with tarfile.open(work / "vendor-dlkm.tar") as archive:
            for member in archive:
                if member.isfile() and member.name.endswith(".ko"):
                    with archive.extractfile(member) as stream:
                        add(stream.read())
        require(early_count and len(modules) > early_count, "Both vendor module sets are required")
        print(f"Auditing {early_count} early-boot and {len(modules) - early_count} vendor_dlkm modules.", flush=True)
        invoke([sys.executable, SCRIPTS / "verify-kmi.py", "--symvers", symvers,
                "--include-module-exports", *modules], timeout=1200)


def prepare(args):
    work = args.work
    data = baseline(work)
    firmware = work / "firmware"
    for name in POLICY_FILES:
        require(sha256(firmware / name) == data["policy"][name], f"Captured policy changed for {name}")
    require(sha256(work / "vendor-dlkm.tar") == data["vendor_dlkm"], "Captured vendor modules changed")
    audit_kmi(work, args.build, args.magiskboot)
    ready = work / "prepared"
    require(not ready.exists(), "This capture already has a prepared image pair")
    with tempfile.TemporaryDirectory(prefix="vegas26-prepare-", dir=work) as temp:
        stage = Path(temp) / "prepared"
        candidates = stage / "candidates"
        candidates.mkdir(parents=True)

        def script(name, *parameters):
            invoke([sys.executable, SCRIPTS / name, *parameters], timeout=600)

        script("prepare-android-memory-v2.py", firmware, stage / "memory")
        script("prepare-android-controller-policy.py", firmware, stage / "policy",
               "--memory-init-stage", stage / "memory")
        script("stage-android-v2-overlay.py", stage / "policy", firmware / "system/lib64/libprocessgroup.so",
               args.library, stage / "overlay")
        script("package-namespace-boot.py", work / "backups/boot.img", args.build, candidates / "boot.img")
        script("package-android-v2-init-boot.py", args.magiskboot, args.avbtool,
               work / "backups/init_boot.img", stage / "overlay", candidates / "init_boot.img",
               "--magiskinit", args.magiskinit)
        write_json(stage / "candidates.json", {
            name: sha256(candidates / f"{name}.img") for name in ("boot", "init_boot")
        })
        stage.rename(ready)


def fastboot_target(data, names):
    fastboot = command("fastboot", "FASTBOOT_SERIAL", data["serial"])

    def getvar(name):
        result = invoke([*fastboot, "getvar", name], capture=True, text=True, timeout=20)
        match = re.search(rf"(?m)^(?:\(bootloader\)\s*)?{re.escape(name)}:\s*(\S+)", result.stderr + result.stdout)
        require(match, f"Bootloader did not report {name}")
        return match[1]

    require(getvar("serialno") == data["serial"], "Bootloader serial differs from the captured phone")
    require(getvar("product") in ("vegas", "vegas26", "vegas_og"), "Unexpected bootloader product")
    require(getvar("securestate") == "flashing_unlocked", "Motorola bootloader is not unlocked")
    require(getvar("is-userspace") == "no", "Enter bootloader Fastboot")
    require(getvar("current-slot") == data["slot"], "Bootloader slot differs from the captured slot")
    for name in names:
        size = getvar(f"partition-size:{name}_{data['slot']}")
        require(int(size, 0) == data["images"][name]["size"], f"Partition size changed for {name}")
    return fastboot


def android_target(data):
    adb = command("adb", "ADB_SERIAL", data["serial"])
    identity = read_root(
        adb, "id -u; getprop ro.serialno; getprop ro.boot.slot_suffix; getprop ro.build.fingerprint"
    )
    require(identity.splitlines() == ["0", data["serial"], "_" + data["slot"], data["firmware"]],
            "Android target differs from the captured firmware, slot or phone")
    return adb


def verify_boot(work, data, checks):
    adb = android_target(data)
    require(read_root(adb, "getprop sys.boot_completed") == "1", "Android boot has not completed")
    image = work / "prepared/candidates/boot.img"
    boot = block("boot", data["slot"])
    observed = read_root(adb, f"set -o pipefail; head -c {image.stat().st_size} {boot} | sha256sum")
    require(observed.split()[0] == checks["boot"], "Installed boot payload differs from the candidate")
    for name, expected in (("init_boot", checks["init_boot"]),
                           ("vendor_boot", data["images"]["vendor_boot"]["sha256"])):
        digest = read_root(adb, f"sha256sum {block(name, data['slot'])}").split()[0]
        require(digest == expected, f"Installed {name} differs from the expected image")
    require("Retention succeeded" in read_root(adb, "cat /dev/vegas26-cgroup-retention.log"),
            "The Android early overlay did not pass retention")
    cmdline = read_root(adb, "cat /proc/cmdline")
    require("cgroup_no_v1=all,named" in cmdline.split(), "The kernel did not prohibit all v1 hierarchies")
    require(" - cgroup " not in read_root(adb, "cat /proc/1/mountinfo"), "PID 1 sees a v1 mount")
    enabled = read_root(adb, "cat /sys/fs/cgroup/cgroup.subtree_control").split()
    require(set(("cpu", "cpuset", "io", "memory", "pids")).issubset(enabled),
            "Android did not delegate all runtime controllers")
    print("Verified Android boot, Magisk root, partition readbacks, retained policy, and unified controllers.")


def deploy(args):
    work = args.work
    data = baseline(work)
    action = args.action
    prepared = work / "prepared"
    candidate = prepared / "candidates"
    if action != "restore":
        checks = json.loads((prepared / "candidates.json").read_text(encoding="utf-8"))
        for name in ("boot", "init_boot"):
            require(sha256(candidate / f"{name}.img") == checks[name], f"Candidate hash changed for {name}")

    if action == "verify":
        verify_boot(work, data, checks)
        return

    if action in ("flash", "stage-init"):
        if args.skip_temporary_test:
            require(args.confirm_recovery, "Confirm that a pre-ADB recovery path was verified")
        else:
            require(args.confirm_recovery and (work / "temporary-test.json").exists(),
                    "Run the temporary test and confirm that a pre-ADB recovery path was verified")
            recorded = json.loads((work / "temporary-test.json").read_text(encoding="utf-8"))
            require(recorded == checks, "Temporary test was run with a different candidate")

    if action == "stage-init":
        adb = android_target(data)
        for name in PARTITIONS:
            digest = read_root(adb, f"sha256sum {block(name, data['slot'])}").split()[0]
            require(digest == data["images"][name]["sha256"], f"Live {name} changed since capture")
        target = block("init_boot", data["slot"])
        image = candidate / "init_boot.img"
        require(image.stat().st_size == data["images"]["init_boot"]["size"], "Invalid init_boot size")
        action = f"set -e; cat > {target}; sync"
        with image.open("rb") as stream:
            invoke([*adb, "exec-in", "su -c " + shlex.quote(action)], stdin=stream)
        require(read_root(adb, f"sha256sum {target}").split()[0] == checks["init_boot"],
                "init_boot write failed readback")
        write_json(work / "staged-init.json", checks)
        print("Verified init_boot readback. Enter bootloader Fastboot directly and flash with --staged-init.")
        return

    if action == "test":
        fastboot = fastboot_target(data, ("boot",))
        print("Trying the kernel in RAM with the existing init_boot.", flush=True)
        invoke([*fastboot, "boot", str(candidate / "boot.img")])
        if not (work / "temporary-test.json").exists():
            write_json(work / "temporary-test.json", checks)
        print("Fastboot accepted the image. Check Android and root, then return to the bootloader manually.")
        return

    names = ["init_boot", "boot"]
    if action == "restore":
        names.reverse()
        source = work / "backups"
        if args.vendor_boot:
            names.append("vendor_boot")
    else:
        source = candidate
        if args.staged_init:
            require(json.loads((work / "staged-init.json").read_text(encoding="utf-8")) == checks,
                    "Staged init_boot receipt does not match this image pair")
            names.remove("init_boot")
    fastboot = fastboot_target(data, names)
    for name in names:
        invoke([*fastboot, "flash", f"{name}_{data['slot']}", str(source / f"{name}.img")])
    print("Partition writes completed. Reboot from the bootloader after checking the result.")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="Private, device-specific working directory")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("capture", help="Read the running stock-policy phone and save its active partition images")
    prepare_parser = actions.add_parser("prepare", help="Package both images offline")
    for name in ("build", "magiskboot", "avbtool", "magiskinit", "library"):
        prepare_parser.add_argument(f"--{name}", type=Path, required=True)
    actions.add_parser("test", help="Attempt temporary fastboot boot without writing partitions")
    actions.add_parser("verify", help="Check the installed pair, Android boot and unified controllers")
    flash_parser = actions.add_parser("flash", help="Flash the checked pair to the captured active slot")
    flash_parser.add_argument("--confirm-recovery", action="store_true", required=True)
    flash_parser.add_argument("--skip-temporary-test", action="store_true")
    flash_parser.add_argument("--staged-init", action="store_true")
    stage_parser = actions.add_parser("stage-init", help="Write only the candidate init_boot from rooted Android")
    stage_parser.add_argument("--confirm-recovery", action="store_true", required=True)
    stage_parser.add_argument("--skip-temporary-test", action="store_true")
    restore_parser = actions.add_parser("restore", help="Restore the captured active boot and init_boot")
    restore_parser.add_argument("--vendor-boot", action="store_true")
    args = parser.parse_args()
    args.work = args.work.resolve()
    try:
        if args.action == "capture":
            capture(args.work)
        elif args.action == "prepare":
            prepare(args)
        else:
            deploy(args)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"Stopped after {Path(error.cmd[0]).name} failed (exit {error.returncode}). "
                    "If a partition write started, verify and restore the captured slot before booting.\n")
    except (OSError, ValueError, KeyError, IndexError, tarfile.TarError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Stopped: {error}\n")


if __name__ == "__main__":
    main()
