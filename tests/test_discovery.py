import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "detect_device", Path(__file__).resolve().parents[1] / "scripts" / "detect-device.py"
)
detect_device = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detect_device)


class DiscoveryTests(unittest.TestCase):
    def test_only_allowlisted_data_reaches_report(self):
        def adb(command, **kwargs):
            args = command[1:]
            if args == ["get-state"]:
                output = b"device"
            elif args == ["shell", "getprop", "ro.product.device"]:
                output = b"vegas26"
            elif args == ["shell", "cat", "/proc/mounts"]:
                output = b"host.test /secret-path cgroup2 rw 0 0"
            elif args == ["exec-out", "cat", "/proc/config.gz"]:
                output = gzip.compress(
                    b'# Linux/arm64\n# CONFIG_PID_NS is not set\nCONFIG_OVERLAY_FS=y\n'
                    b'CONFIG_LOCALVERSION="private-token"\n'
                )
            else:
                self.assertEqual(len(args), 3)
                output = b"private-token 123456789012345"
            return subprocess.CompletedProcess(command, 0, output, b"private-stderr")

        with patch.object(detect_device.subprocess, "run", side_effect=adb):
            report = detect_device.collect("adb")
        payload = json.dumps(report)
        for forbidden in ("private", "123456789012345", "secret-path", "host.test"):
            self.assertNotIn(forbidden, payload)
        self.assertEqual(report["device"], "vegas26")
        self.assertIsNone(report["model"])
        self.assertEqual(report["config"]["PID_NS"], "disabled")
        self.assertEqual(report["config"]["OVERLAY_FS"], "built-in")
        self.assertIsNone(report["config"]["USER_NS"])
        self.assertEqual(report["cgroup_filesystems"], ["cgroup2"])

    def test_disconnected_target_stops_collection(self):
        with patch.object(detect_device.subprocess, "run") as adb:
            adb.return_value = subprocess.CompletedProcess([], 1, b"", b"private")
            with self.assertRaisesRegex(RuntimeError, "one authorized target"):
                detect_device.collect("adb")
            adb.assert_called_once()

    def test_invalid_config_is_unknown(self):
        self.assertTrue(all(value is None for value in detect_device.config_values(b"invalid").values()))
