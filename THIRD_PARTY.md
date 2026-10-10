# Third-party dependencies

The repository does not vendor the Arduino core, Arduino libraries, Android SDK, Python packages, or Wintun DLL. Install them from their publishers and follow their respective licenses.

| Dependency | Tested version | Upstream | License information |
| --- | --- | --- | --- |
| M5Atomic-EchoBase | 1.0.2 | https://github.com/m5stack/M5Atomic-EchoBase | MIT; see upstream `LICENSE` |
| M5GFX | 0.2.32 | https://github.com/m5stack/M5GFX | MIT; see upstream `LICENSE` |
| Arduino ESP32 core | 3.3.2 | https://github.com/espressif/arduino-esp32 | See upstream license and bundled component notices |
| Android Gradle Plugin / SDK | 9.4.0 / Platform 37 | https://developer.android.com/studio | See Google's distribution terms and component licenses |
| Gradle Wrapper bootstrap JAR | 9.6.0 | https://github.com/gradle/gradle | Apache License 2.0; the wrapper JAR is included so the Android build can bootstrap |
| pyserial | Environment dependent | https://github.com/pyserial/pyserial | See upstream license |
| Wintun | Optional | https://www.wintun.net/ | See upstream license and redistribution terms; DLL not included |
| dbhq-uk/modem `overture.rs` | Reference for Bell 103 dial-up sound sequence | https://github.com/dbhq-uk/modem/blob/main/modem-core/src/overture.rs | MIT; Copyright (c) 2026 DBHQ Ventures Ltd. See [license notice](third_party/DBHQ_MODEM_LICENSE). The Bell 103 overture module acknowledges this reference. |

The project's MIT license does not replace these third-party terms.
