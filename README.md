# Moto G Power 2026 kernel development

This project investigates Linux container support on the Moto G Power 2026 while keeping the original Android installation and vendor drivers. An unmodified experimental GKI baseline builds on Ubuntu 24.04. Installation support is pending official Android ABI checks, vendor module validation, and recovery verification.

The experimental PID controller build compiles but fails the vendor module CRC check. It is unsuitable for installation with the current firmware's modules.

| Device | Firmware | Running kernel | Custom kernel compatibility |
| --- | --- | --- | --- |
| Moto G Power 2026 (vegas26, ARM64) | Android 16, W1WEOS36.48-22-3-3-4-2 | 5.15.180-android13-8-00018-g9b2308ac0ad6-ab14563692 | Unknown |

## Collect a compatibility report

Install [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) and Python 3.8 or later. Connect one phone over USB, enable USB debugging, and authorize the computer when prompted. Run from the repository root.

```sh
python scripts/detect-device.py --public-report
```

Pass `--adb <path-to-adb>` if Platform-Tools is outside PATH. The script reads specific properties, the kernel release, selected config flags, and cgroup filesystem types. A JSON `null` means the tool could not confirm the value. Review the output before sharing.

Run the offline tests with `python -m unittest discover -s tests -v`.

See [device findings and build prerequisites](docs/compatibility.md) and [contribution and privacy rules](CONTRIBUTING.md).

See [building the experimental GKI baseline](docs/building.md) for Linux and WSL2 instructions and the [baseline comparison](docs/baseline-compatibility.md) for test results.
