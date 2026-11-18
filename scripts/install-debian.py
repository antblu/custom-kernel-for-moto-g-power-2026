"""Download and install the tested Debian 13 ARM64 userspace and boot service."""

import argparse
import gzip
import hashlib
import ipaddress
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

IMAGE = "docker.io/library/debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2"
ROOT = "/data/adb/debian-trixie"
BUSYBOX = "/data/adb/magisk/busybox"
LAUNCHER = "/data/adb/debian-shell"
SERVICE = "/data/adb/service.d/90-debian-trixie.sh"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def export_rootfs(archive):
    subprocess.run(["docker", "pull", "--platform", "linux/arm64", IMAGE], check=True)
    container = subprocess.check_output(
        ["docker", "create", "--platform", "linux/arm64", IMAGE], text=True
    ).strip()
    try:
        with gzip.open(archive, "wb") as output:
            with subprocess.Popen(["docker", "export", container], stdout=subprocess.PIPE) as process:
                shutil.copyfileobj(process.stdout, output)
                if process.wait():
                    raise RuntimeError("Docker root filesystem export failed.")
    finally:
        subprocess.run(["docker", "rm", container], stdout=subprocess.DEVNULL, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--reuse", action="store_true", help="Preserve an existing Debian install.")
    args = parser.parse_args()
    scripts = Path(__file__).resolve().parent

    def shell(command, timeout=25, check=True):
        return subprocess.run(
            [args.adb, "shell", "su -c " + shlex.quote(command)], check=check,
            capture_output=True, text=True, timeout=timeout,
        )

    def upload(source, destination):
        with source.open("rb") as stream:
            subprocess.run(
                [args.adb, "exec-in", "su -c " + shlex.quote(f"umask 077; cat > {destination}")],
                stdin=stream, check=True, timeout=180,
            )
        received = shell(f"sha256sum {destination}").stdout.split()
        if not received or received[0] != digest(source):
            raise RuntimeError("Transferred file checksum mismatch.")

    if shell("getprop ro.product.device; uname -r").stdout.split() != ["vegas26", "5.15.180"]:
        raise RuntimeError("Expected the Moto G Power 2026 running the namespace kernel.")
    shell(f"test -x {BUSYBOX} && unshare -p -f true")
    stage = ROOT + ".install-" + uuid.uuid4().hex
    shell(f"umask 077; mkdir {stage}")
    with tempfile.TemporaryDirectory() as work:
        if args.reuse:
            shell(f"test -x {ROOT}/bin/bash && grep -qx VERSION_CODENAME=trixie {ROOT}/etc/os-release")
        else:
            shell(f"test ! -e {ROOT}")
            archive = Path(work) / "rootfs.tar.gz"
            export_rootfs(archive)
            upload(archive, f"{stage}/rootfs.tar.gz")
            shell(f"mkdir {stage}/root && {BUSYBOX} tar -xzf {stage}/rootfs.tar.gz -C {stage}/root "
                  f"&& test -x {stage}/root/bin/bash && test ! -e {ROOT} && mv {stage}/root {ROOT} "
                  f"&& rm {stage}/rootfs.tar.gz", timeout=180)

        connectivity = shell("dumpsys connectivity").stdout
        active = re.search(r"Active default network:\s*(\d+)", connectivity)
        if not active:
            raise RuntimeError("Android has no active network for installing tini.")
        servers = []
        for line in connectivity.splitlines():
            if f"network{{{active[1]}}}" not in line.lower():
                continue
            dns = re.search(r"DnsAddresses:\s*\[([^\]]*)\]", line)
            if dns:
                for item in re.split(r"[,\s]+", dns[1]):
                    try:
                        servers.append(str(ipaddress.ip_address(item.strip("/"))))
                    except ValueError:
                        pass
        if not servers:
            raise RuntimeError("Android's active network did not provide DNS servers.")
        resolver = "".join(f"nameserver {server}\n" for server in dict.fromkeys(servers))
        shell(f"printf %s {shlex.quote(resolver)} > {ROOT}/etc/resolv.conf")
        upload(scripts / "debian-shell.sh", f"{stage}/launcher")
        shell(f"mv {stage}/launcher {LAUNCHER} && chmod 700 {LAUNCHER}")
        shell(f"/system/bin/sh {LAUNCHER} apt-get -o APT::Update::Error-Mode=any update", timeout=180)
        shell(f"/system/bin/sh {LAUNCHER} apt-get install -y --no-install-recommends tini", timeout=180)
        upload(scripts / "debian-startup.sh", f"{stage}/startup")
        shell(f"mkdir -p /data/adb/service.d && mv {stage}/startup {SERVICE} "
              f"&& chmod 700 {SERVICE} && rmdir {stage}")
    print("Debian is installed. The Magisk startup service runs at the next Android boot.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Debian installer command failed (exit {error.returncode}).") from None
