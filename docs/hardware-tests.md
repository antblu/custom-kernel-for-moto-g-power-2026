# Android hardware test checklist

Record the public device codename, firmware build, kernel release, and the result of each check. Use Passed, Failed, Skipped, Not run, or Unsupported. Mark a check Passed only after observing the expected behavior. Keep screen recordings, carrier details, test account data, and raw Android logs in private storage.

Run the checks first on the original kernel to establish what works with the device, plan, and accessories available. Repeat the same checks after any separately authorized candidate boot. An unavailable network or accessory is a reason to skip the affected check.

| Check | Expected behavior |
| --- | --- |
| Android, display, and touch | Lock screen and launcher render. Touch, rotation, brightness, and screen timeout work. |
| Wi-Fi and Bluetooth | Connect to a test network and transfer data. Pair an audio device and play sound. |
| 4G, 5G, and cellular data | Registration and data work on each radio mode supported by the test plan and coverage. |
| Voice, VoLTE, SMS, and MMS | Use a consenting test contact for calls and messages. Verify audio in both directions and receipt of each supported message type. |
| Camera, microphone, and speakers | Capture from front and rear cameras. Record sound and play it through the speaker and earpiece. |
| GPU and media | Render an accelerated application. Play and record a supported hardware-accelerated video format. |
| GPS and sensors | Verify a location fix and sensor response while keeping readings private. Check fingerprint unlock if already configured. |
| USB modes | Verify ADB and file transfer, then test a USB peripheral and tethering with the appropriate host. |
| Power and thermal | Check charging, temperature under normal load, and repeated screen-off suspend and resume. |
| Linux runtimes | Run the [kernel discovery report](../README.md), then test each intended chroot or container runtime separately. |

All checks other than stock-kernel ADB connectivity remain Not run for this project milestone.
