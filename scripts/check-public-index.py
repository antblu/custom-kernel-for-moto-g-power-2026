"""Reject obvious private files and labeled identifiers in the Git index."""

from pathlib import PurePosixPath
import re
import subprocess
import sys

PRIVATE_DIRS = {"private", "secrets", "backups", "firmware", "dumps", ".cache", "out"}
PRIVATE_NAMES = {"id_rsa", "id_ed25519", ".env"}
PRIVATE_SUFFIXES = {
    ".img", ".bin", ".mbn", ".elf", ".ko", ".dtbo", ".raw",
    ".zip", ".gz", ".tar", ".xz", ".zst", ".pem", ".key", ".p12", ".pfx",
}
IDENTIFIER = re.compile(
    r"""(?im)^\s*["']?(?:imei[12]?|meid|imsi|iccid|eid|serial(?:_?number)?|android_?id|mac(?:_?address)?)["']?"""
    r"""\s*[:=]\s*["']?[a-z0-9][a-z0-9:-]{7,}\b"""
)


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def private_path(name):
    path = PurePosixPath(name.lower())
    return (
        not PRIVATE_DIRS.isdisjoint(path.parts[:-1])
        or "logs/raw" in str(path.parent)
        or path.name in PRIVATE_NAMES
        or path.name.startswith(".env.")
        or path.suffix in PRIVATE_SUFFIXES
    )


def main():
    findings = 0
    try:
        entries = git("ls-files", "--stage", "-z").split(b"\0")
        for entry in filter(None, entries):
            metadata, raw_name = entry.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split()
            if stage != "0" or mode not in {"100644", "100755"} or private_path(raw_name.decode("utf-8")):
                findings += 1
                continue
            if int(git("cat-file", "-s", object_id)) > 512_000:
                findings += 1
                continue
            content = git("cat-file", "blob", object_id)
            try:
                text = content.decode("utf-8")
            except UnicodeError:
                findings += 1
                continue
            if "\0" in text or IDENTIFIER.search(text):
                findings += 1
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError):
        print("Could not inspect the entire Git index.", file=sys.stderr)
        return 2
    if findings:
        print(f"Public index check rejected {findings} entries. Inspect the staged files locally.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
