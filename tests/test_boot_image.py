import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "inspect_boot_image", Path(__file__).resolve().parents[1] / "scripts" / "inspect-boot-image.py"
)
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class BootImageTests(unittest.TestCase):
    def test_boot_v4_and_truncated_payload(self):
        data = bytearray(4096)
        data[:8] = b"ANDROID!"
        struct.pack_into("<IIII", data, 8, 64, 0, 0, 1584)
        struct.pack_into("<I", data, 40, 4)
        data.extend(b"\x1f\x8b" + bytes(62))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "boot.img"
            path.write_bytes(data)
            report = boot.inspect(path)
            self.assertEqual(report["kernel_bytes"], 64)
            self.assertEqual(report["kernel_encoding"], "gzip")
            self.assertEqual(report["ramdisk_bytes"], 0)
            path.write_bytes(data[:-1])
            with self.assertRaisesRegex(ValueError, "shorter"):
                boot.inspect(path)

    def test_vendor_v4_reports_numeric_layout(self):
        data = bytearray(4 * 4096 + 108)
        data[:8] = b"VNDRBOOT"
        struct.pack_into("<II", data, 8, 4, 4096)
        struct.pack_into("<I", data, 24, 6000)
        struct.pack_into("<II", data, 2096, 2128, 64)
        struct.pack_into("<IIII", data, 2112, 108, 1, 108, 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vendor_boot.img"
            path.write_bytes(data)
            report = boot.inspect(path)
            self.assertEqual(report["vendor_ramdisk_fragments"], 1)
            self.assertEqual(report["dtb_bytes"], 64)
