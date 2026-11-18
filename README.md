# Moto G Power 2026 namespace kernel

Tested on the Moto G Power 2026 (vegas26), Android 16 firmware `W1WEOS36.48-22-3-3-4-2`. The namespace kernel boots Android and runs Debian 13 ARM64 alongside it.

1. [Build the namespace kernel](docs/building.md) and check the vendor module CRCs.
2. [Prepare the boot image, verify stock recovery, and install](docs/recovery.md).
3. [Download Debian, set up automatic startup, and enter its shell](docs/debian.md).

```sh
python3 scripts/install-debian.py
adb shell -t "su -c '/system/bin/sh /data/adb/debian-shell --enter'"
```

See the [verified kernel results](docs/baseline-compatibility.md), [Debian test results](docs/debian.md#test-results), and [contribution and privacy rules](CONTRIBUTING.md).
