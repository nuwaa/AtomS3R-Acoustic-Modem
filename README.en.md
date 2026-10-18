# AtomS3R Acoustic Modem

[日本語](README.md) | [繁體中文（臺灣）](README.zh-TW.md) | [简体中文](README.zh-CN.md) | **English**

This is a snapshot of the working acoustic AX.25 modem source for the M5Stack ATOM S3R and ATOMIC ECHO BASE (Atomic Voice Base). A PC or Android device connects to an ATOM over USB-C; two ATOM units communicate through the air using 1200 bps Bell 202 AFSK. No radio transmitter is used. This page describes the `main` snapshot; Bell 103 and ggwave are developed on separate branches.

Work and hardware tests since October 5 are recorded in the [development diary](docs/DEVELOPMENT_DIARY.en.md), which will be extended as development continues.

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

## Implemented features and verification

- ES8311 48 kHz PCM input/output; 1200/2200 Hz Bell 202 AFSK; 1200 bps AX.25 UI frames; HDLC/NRZI; FCS/CRC validation.
- Serial hexadecimal and text display of received frames, recording and later decoding, transmission, and live reception.
- UTF-8 direct chat with fragmentation, ACK, and retry; group CHAT with SUMMARY/NACK recovery and suppression of old-message redisplay.
- Android USB host and PC USB CDC connections; optional IPv4 tunnel; ping/traceroute; chat and IP communication together.
- Bidirectional direct/group chat and ping verified with two ATOM units and Android/PC. Direct chat between two Android devices was also verified.
- Receive-only packet monitor source is included; monitoring with a third physical node has not been tested.

The acoustic path is half-duplex. Volume, placement, and ambient noise affect delivery rate and latency. PC diagnostic tools and test sources are in `outputs/`. Recordings, logs, device flash backups, APKs, and local settings are excluded from publication.

## Development branches and diaries

This `main` branch preserves the 1200 bps AX.25 / Bell 202 version. The additional acoustic modes are being tested on separate branches. Their diaries distinguish hardware results from work that has not yet been verified.

| Branch | What the diary covers | Diary |
| --- | --- | --- |
| `main` | Early AX.25, USB chat, group chat, and IP tunnel development (from about October 5) | [AX.25 development diary](docs/DEVELOPMENT_DIARY.en.md) |
| [`feature/bell103`](https://github.com/nuwaa/AtomS3R-Acoustic-Modem/tree/feature/bell103) | Dial-up-style overture, 300 bps Bell 103, connection, text/ACK, retries, reception while Android is locked, and latency tests | [Bell 103 branch diary](https://github.com/nuwaa/AtomS3R-Acoustic-Modem/blob/feature/bell103/docs/DEVELOPMENT_DIARY.en.md) |
| [`feature/ggwave`](https://github.com/nuwaa/AtomS3R-Acoustic-Modem/tree/feature/ggwave) | Short and fragmented 280-character ggwave messages, audio level controls, klesis Web audio reception, and two-ATOM/OPPO tests | [ggwave branch diary (through October 18)](https://github.com/nuwaa/AtomS3R-Acoustic-Modem/blob/feature/ggwave/docs/DEVELOPMENT_DIARY.en.md) |

Bell 103 and ggwave are **not included in the `main` firmware**. Consult the relevant branch README, build instructions, and hardware test record before using either mode.

## License

Project-authored source is under the [MIT License](LICENSE). Third-party components retain their own terms; see [THIRD_PARTY.md](THIRD_PARTY.md).

