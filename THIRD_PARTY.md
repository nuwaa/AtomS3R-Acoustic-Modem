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

## Emoji artwork and sequence data

`outputs/AtomS3R_AfskRx/EmojiSprites.cpp` contains 16×16, 32-color images derived from [Noto Emoji](https://github.com/googlefonts/noto-emoji), revision `e20cbc2bbec1926686be9f9bee7d1d2cfa1fea0e` (v2026-09-24-unicode18_0), using its `2D/png/32` and `3D/png/32` artwork. Copyright 2013 Google LLC and contributors. The artwork is distributed under Apache License 2.0; its license text is retained at [third_party/noto-emoji/LICENSE](third_party/noto-emoji/LICENSE). Region flag artwork comes from Noto Emoji's `third_party/region-flags`, which that project describes as public domain or otherwise exempt from copyright.

Emoji sequences come from the [Unicode emoji-test.txt download](https://www.unicode.org/Public/emoji/latest/emoji-test.txt), Version 18.0, dated 2026-04-30, SHA256 `8F3735CDA1F92A779D78AF67CF86066BB1F07143DC22F2AC29394D9BC57AB21A`; copyright 2026 Unicode, Inc. See the [Unicode terms of use](https://www.unicode.org/terms_of_use.html). The generated table includes the 3,963 fully-qualified sequences and aliases with U+FE0F removed (5,143 accepted UTF-8 keys).

To regenerate, install Python and `pip install -r tools/requirements-emoji.txt`, check out the Noto Emoji revision above, download the Unicode 18.0 `emoji-test.txt` (verify its SHA256 above), then run:

```sh
python tools/generate_emoji_sprites.py --noto /path/to/noto-emoji --emoji-test /path/to/emoji-test.txt
```

The generated C++ files are included so ordinary Arduino builds do not require Python, Pillow, or the original PNG files.
