# Moto G Power 2026 kernel development

This project develops an Android GKI kernel for the Moto G Power 2026 with Linux namespaces. The namespace-only kernel boots on the tested Android 16 firmware and runs Debian 13 ARM64 userspace. See [Debian userspace](docs/debian.md) for the launch command and test results.

The experimental PID controller build compiles but fails the vendor module CRC check. It is unsuitable for installation with the current firmware's modules.

The container-host profile builds with all 59 requested features outside the experimental group, and it also fails the vendor module CRC check. See the [container host results](docs/baseline-compatibility.md#container-host-candidate).

The namespace-only profile passes vendor CRC comparison and an ARM64 namespace smoke test. It boots on the tested phone and passes on-device namespace smoke tests. See the [boot and recovery findings](docs/recovery.md). See the [namespace-only results](docs/baseline-compatibility.md#namespace-only-candidate).

| Device | Firmware | Running kernel | Custom kernel compatibility |
| --- | --- | --- | --- |
| Moto G Power 2026 (vegas26, ARM64) | Android 16, W1WEOS36.48-22-3-3-4-2 | 5.15.180-android13-8-00018-g9b2308ac0ad6-ab14563692 (stock) | Namespace-only build booted and tested with Debian. Full hardware regression pending. |

## Collect a compatibility report

Install [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) and Python 3.8 or later. Connect one phone over USB, enable USB debugging, and authorize the computer when prompted. Run from the repository root.

```sh
python scripts/detect-device.py --public-report
```

Pass `--adb <path-to-adb>` if Platform-Tools is outside PATH. The script reads specific properties, the kernel release, selected config flags, and cgroup filesystem types. A JSON `null` means the tool could not confirm the value. Review the output before sharing.

Run the offline tests with `python -m unittest discover -s tests -v`.

See [device findings and build prerequisites](docs/compatibility.md) and [contribution and privacy rules](CONTRIBUTING.md).

See [building the experimental GKI baseline](docs/building.md) for Linux and WSL2 instructions and the [baseline comparison](docs/baseline-compatibility.md) for test results.
