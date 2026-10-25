# AtomS3R Acoustic Modem

[日本語](README.md) | [繁體中文（臺灣）](README.zh-TW.md) | [简体中文](README.zh-CN.md) | **English**

**Current ATOM S3R receiver for [Can You Hear the Data?](https://github.com/nuwaa/Can-You-Hear-the-Data):** The `feature/ggwave` firmware now starts audible ggwave web reception on normal boot and displays Japanese, Simplified Chinese, half-width kana, and color emoji. See the [current Japanese README](README.md) and the [hardware receiver guide](https://github.com/nuwaa/Can-You-Hear-the-Data/blob/main/docs/ATOM_S3R_RECEIVER.md). The Bell 103 description below reflects the earlier development stage.

The [browser installer](https://nuwaa.github.io/Can-You-Hear-the-Data/install.en.html) can flash this receiver firmware without an Arduino setup. On October 26, 2026, the user installed the line-break build from the browser on two ATOM S3R units and confirmed that both displays showed multiline text correctly. The [development diary](docs/DEVELOPMENT_DIARY.en.md) records the firmware and distribution work.

This `feature/bell103` branch is a development version of the acoustic modem for the M5Stack ATOM S3R and ATOMIC ECHO BASE (Atomic Voice Base). It adds a selectable 300 bps Bell 103 mode alongside the preserved 1200 bps Bell 202 / AX.25 mode. A PC or Android device connects to an ATOM over USB-C; two ATOM units communicate through the air, without a radio transmitter. The AX.25-only snapshot remains on the [main branch](https://github.com/nuwaa/AtomS3R-Acoustic-Modem/tree/main) and tag `v0.3.1`.

Work and hardware tests since October 5 are recorded in the [development diary](docs/DEVELOPMENT_DIARY.en.md), which will be extended as development continues.

See the [filming guide](docs/VIDEO_SHOOTING_GUIDE.en.md) for a two-node iPhone demonstration.

## Hardware

- Each node: an ATOM S3R, ATOMIC ECHO BASE, USB-C data cable, and a PC or Android device acting as USB host.
- Two nodes: place them so each speaker can be heard by the other microphone. Android-to-Android chat needs two complete node sets.
- ES8311 codec. Firmware pin assignments: SDA=GPIO38, SCL=39, I2S BCLK=8, WS=6, TX=5, RX=7.

## Development environment and dependencies

- Arduino IDE or Arduino CLI with Espressif `esp32` Arduino core **3.3.2**.
- Board: **ESP32S3 Dev Module**; **8 MB** flash; **OPI** PSRAM; **USB CDC On Boot** enabled.
- Arduino libraries: [M5Atomic-EchoBase](https://github.com/m5stack/M5Atomic-EchoBase) **1.0.2** and [M5GFX](https://github.com/m5stack/M5GFX) **0.2.32**.
- Android app: Android Studio, JDK 17, Android SDK Platform 37, Gradle Wrapper **9.6.0**, and Android Gradle Plugin **9.4.0**.
- PC Python tools: Python 3 and `pyserial`. For the Windows IP tunnel, obtain [Wintun](https://www.wintun.net/) separately.

The Arduino core and libraries and the Wintun DLL are not bundled. See [third-party dependencies](THIRD_PARTY.md) for license information.

## Build

1. Install Espressif `esp32` 3.3.2 in the Arduino IDE Board Manager and the two libraries above in Library Manager.
2. Open [AtomS3R_AfskRx.ino](outputs/AtomS3R_AfskRx/AtomS3R_AfskRx.ino), select the board settings above, and verify/upload to each ATOM's USB port. Check the device settings and target before overwriting an existing unit.
3. Open [AtomUsbChat](outputs/android/AtomUsbChat) in Android Studio, sync the project, and build the `app` debug APK. From that directory, use `gradlew.bat :app:assembleDebug` on Windows or `./gradlew :app:assembleDebug` on macOS/Linux.

The published copy omits the absolute path to a debug-signing file specific to the development PC and uses Android's standard debug signing. The app's Java source, manifest, and resources are included.

## USB connection and use

Enable USB host (OTG) on Android and connect the ATOM with USB-C. In the app, tap “ATOM USB接続”, grant USB access, and check for “USB-C接続済み”. Choose “直接” for ordinary chat or “グループ CHAT” for multi-node delivery and missing-message recovery. Only when IP communication is needed, tap “IPトンネル開始” and approve Android's VPN request. This carries IP packets over the acoustic link independently of the in-app chat.

On a PC, use the ATOM's USB CDC serial port. A serial monitor at **115200 bps** accepts `?` for a command list. To run the Python chat UI, copy [settings.example.json](outputs/environment/settings.example.json) to `outputs/environment/settings.json` and set the port and Python library locations. After installing `pyserial`, run, for example, `python outputs/usb_chat_web.py --port COM6` from the repository root, then open `http://127.0.0.1:8766/` on the PC. Do not commit local settings. Only one program can open a COM port at a time.

In the Android app, open **Details → Audio settings** to adjust the ATOM speaker volume (0–100%) and ES8311 microphone gain (0–42 dB in 6 dB steps). Near-field, standard, and experimental noisy-environment presets are available alongside custom settings. The ATOM saves the values across reconnects; defaults are 50% and 6 dB. The receive-diagnostics fields currently say “not measured”; measurement is not implemented. Over USB serial, use `audio show`, `audio volume 50`, or `audio gain 6`. Both AX.25 and Bell 103 use these settings.

## Implemented features and verification

- ES8311 48 kHz PCM input/output; 1200/2200 Hz Bell 202 AFSK; 1200 bps AX.25 UI frames; HDLC/NRZI; FCS/CRC validation.
- Serial hexadecimal and text display of received frames, recording and later decoding, transmission, and live reception.
- UTF-8 direct chat with fragmentation, ACK, and retry; group CHAT with SUMMARY/NACK recovery and suppression of old-message redisplay.
- Android USB host and PC USB CDC connections; optional IPv4 tunnel; ping/traceroute; chat and IP communication together.
- Bidirectional direct/group chat and ping verified with two ATOM units and Android/PC. Direct chat between two Android devices was also verified.
- Receive-only packet monitor source is included; monitoring with a third physical node has not been tested.

The acoustic path is half-duplex. Volume, placement, and ambient noise affect delivery rate and latency. PC diagnostic tools and test sources are in `outputs/`. Recordings, logs, device flash backups, APKs, and local settings are excluded from publication.

## Bell 103 development status

Bell 103 provides dial-up-style connection sound, caller/answerer handshake, half-duplex UTF-8 text, ACK, and retransmission through the PC and Android chat controls. It uses project-specific synchronization and framing; interoperability with ordinary telephone-line Bell 103 modems has not been verified. On two ATOM units, the October 13 hardware run delivered 32 messages exactly once with 32 ACKs and no retransmissions in 30 minutes; AX.25 direct chat passed afterward. This is a result for that device placement, not a guarantee under other acoustic conditions. Connection sound remains unchanged. The development diary records timing experiments and limitations.

## License

Project-authored source is under the [MIT License](LICENSE). Third-party components retain their own terms; see [THIRD_PARTY.md](THIRD_PARTY.md).
