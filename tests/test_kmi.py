import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "verify_kmi", Path(__file__).resolve().parents[1] / "scripts" / "verify-kmi.py"
)
kmi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kmi)


class KmiTests(unittest.TestCase):
    def test_conflicting_export_crc_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Path(directory) / "kernel.symvers"
            vendor = Path(directory) / "vendor.symvers"
            kernel.write_text("0x01234567\tsymbol\tvmlinux\tEXPORT_SYMBOL\n", encoding="ascii")
            vendor.write_text("0x76543210\tsymbol\tmodule\tEXPORT_SYMBOL\n", encoding="ascii")
            self.assertEqual(kmi.read_exports([kernel]), {"symbol": "0x01234567"})
            with self.assertRaisesRegex(ValueError, "Conflicting export CRCs"):
                kmi.read_exports([kernel, vendor])

    def test_export_tool_failure_requires_an_elf_without_an_export_table(self):
        failure = subprocess.CompletedProcess(["modprobe"], 1, "", "")
        module = Path("module.ko")
        with patch.object(kmi.subprocess, "run", return_value=failure):
            with patch.object(kmi.subprocess, "check_output", return_value=".symtab __versions"):
                self.assertEqual(kmi.module_versions(module, "--show-exports"), {})
            with patch.object(kmi.subprocess, "check_output", return_value="__ksymtab"):
                with self.assertRaises(subprocess.CalledProcessError):
                    kmi.module_versions(module, "--show-exports")
