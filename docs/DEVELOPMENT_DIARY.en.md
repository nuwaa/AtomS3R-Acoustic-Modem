# Development diary — AtomS3R Acoustic Modem

[日本語](DEVELOPMENT_DIARY.md) | [繁體中文（臺灣）](DEVELOPMENT_DIARY.zh-TW.md) | [简体中文](DEVELOPMENT_DIARY.zh-CN.md) | **English**

A record of the acoustic TNC project using ATOM S3R and Atomic Echo Base. “Around” marks approximate dates in the early work. Hardware results are distinguished from open issues. Bell 103 work from October 11 onward took place on `feature/bell103`; it is **not** an implemented feature of the `main` snapshot. New entries will be appended in date order.

## Around October 5, 2026 — Turning sound into data

We examined PCM captured from the ATOM S3R microphone and the speaker output, then built the foundation for AX.25 frames over 1200 bps Bell 202 AFSK. Producing a sound on one device was different from decoding a frame sent through the air to a second device. We worked through the waveform and CRC diagnostics to establish two-device communication.

## Around October 6–7, 2026 — Extending to USB and IP

We separated the acoustic AX.25 path into a transport so USB CDC, SLIP, and PPP could be combined with it later. Work expanded to PC chat and continuous UDP tests, and we began an Android app that connects to an ATOM over USB-C. Text passed between a PC and an OPPO phone, and ping worked in both directions through the acoustic IP tunnel. Actual use also exposed font issues with Japanese and Traditional Chinese text and a keyboard that overlapped the Android send button; those were corrected.

## Around October 8, 2026 — Trying group chat

We moved toward direct ATOM-to-ATOM chat without a PC chat server. With future networks of three or more nodes in mind, we added group delivery and SUMMARY/NACK recovery for missing messages. Two ATOM units on COM5 and COM6 passed bidirectional UTF-8 tests. PC/OPPO chat could also run alongside ping. We adjusted glyphs that were unreadable on the ATOM's small display.

## Around October 9–10, 2026 — Android-to-Android conversation

Each of two Android devices connected to its own ATOM over USB-C, and direct chat worked in both directions. Group chat exposed a case where old messages arrived in a burst, so we revisited stored state and retransmission. We redesigned the app around the chat view and removed controls that were no longer useful. Source for a receive-only packet monitor was also prepared for a future third node; no third-device interception test has been run.

## October 11, 2026 — Adding Bell 103

We preserved the working Bell 202 / AX.25 source in a GitHub repository and organized its MIT license and dependencies. On a separate branch, we added a 300 bps Bell 103 mode in stages: dial-up-style connection sounds, FSK transmission and reception, caller/answerer roles, handshake, data, ACK, and retry. Japanese and Traditional Chinese messages worked between two Android devices and between a PC and Android. We also confirmed that disconnecting returns to AX.25. In a 30-minute hardware test, all 27 messages arrived with ACKs; seven retransmissions occurred.

## October 12, 2026 — Message order and missing text while locked

We revised display order after interruptions and reduced Bell 103 receive waiting time. A separate problem appeared on Android: the PC could report “delivered” while the first message was absent from the app after the screen had been locked. That status meant the remote ATOM had sent an acoustic ACK, not that Android had saved the text.

We therefore added a 16-entry inbox on the ATOM. Android now confirms over USB only after saving a message. After the screen had been locked for over five minutes, a long F09 message followed by short F10 appeared once each and in order. R01, delivered while the app process was stopped, was retrieved once after restart. Direct and group chat also worked in both directions. The inbox is held in RAM, however: power loss or more than 16 unconfirmed arrivals can still lose data.

Other attempts on the same day failed to obtain an acoustic ACK from the remote ATOM. This is separate from ATOM-to-Android USB delivery. The next investigation is to hold device placement constant and determine from logs whether the receiver failed to decode the frame or decoded it but failed to return an ACK.

## October 13, 2026 — Measuring Bell 103 latency

We shortened the connected-state receive window from a maximum of nine seconds to six seconds. An early decode triggered by a quiet gap can now retry after more signal arrives. After building and flashing two ATOMs, a five-minute test delivered and acknowledged all 15 messages with two retransmissions. A 30-minute test delivered all 32 messages exactly once, acknowledged all 32, and used six retransmissions.

In the 30-minute log, median time from send command to text delivery was six seconds and to ACK was nine seconds. The earlier 30-minute log measured 14 and 17 seconds respectively. Acoustic conditions and send intervals differed, so this is not a controlled performance comparison. The overture still lasts about 11 seconds; connection completed in about 20 seconds in this run. Bidirectional AX.25 direct chat passed after both the five-minute and 30-minute tests.

Later that day, we tried yielding from idle acoustic capture as soon as a USB send command arrived, provided no acoustic activity had begun. With a six-second receive window, a 30-minute test delivered all 30 messages but needed 11 retransmissions; median delivery was seven seconds. With a nine-second window, all 29 messages arrived with four retransmissions and median delivery of eight seconds. Neither setting was an unqualified improvement.

Keeping the nine-second limit, we changed end-of-burst detection to use the average sound level over roughly 0.13 seconds. This avoids brief microphone noise repeatedly breaking the quiet-period test; a valid CRC still decides whether to end capture early. A five-minute test delivered 16 messages with two retransmissions. A 30-minute test delivered all 32 messages exactly once, acknowledged all 32, and needed no retransmissions. Its median delivery time was ten seconds and median ACK time was 12 seconds, so delivery latency did not improve in every run. The overture was unchanged, and bidirectional AX.25 direct chat passed afterward. Differences between runs remain indicative because acoustic conditions were not fully controlled.

## October 18, 2026 — Receiving klesis Web chat audio on ATOM

On `feature/ggwave`, we added a receive-only mode for audio from [klesis Web chat](https://github.com/nolimitwaiz/klesis). The existing ATOM-to-ATOM ggwave chat uses fixed-length frames with its own fragmentation and ACKs; klesis uses variable-length frames, so it has a separate decoder mode. Android 0.4.3 adds a “Receive Web audio” control and displays decoded text in the usual chat view. Both firmware and Android builds passed.

The COM5 ATOM decoded “こんにちは”, “你好”, and “Hello” sent over the air from klesis in Audible Normal mode; the dedicated test passed. After stopping Web reception, AX.25 direct chat passed in both directions with text and delivery confirmation. With this ATOM attached to the first OPPO, `Web確認 こんにちは` appeared both in the app and on the ATOM display.

We flashed the second ATOM (COM6) and installed the updated app on the second OPPO. Flash and installation passed, and `Web確認 你好` from klesis appeared in both that OPPO's chat and its ATOM display. Audible Normal is the Web audio mode verified on hardware. Fast/Fastest, 44.1 kHz browser audio, ultrasonic modes, and ATOM-to-klesis transmission remain untested. Web reception is receive-only and cannot run alongside the existing ggwave chat mode.

## October 25, 2026 — Can You Hear the Data? receiver and display

The `feature/ggwave` firmware was adapted to receive the variable-length ggwave Audible Normal signal from [Can You Hear the Data?](https://github.com/nuwaa/Can-You-Hear-the-Data). Normal boot now starts Web audio reception automatically. This remains separate from the fixed-length ATOM-to-ATOM DT chat and ACK protocol. The user flashed the two ATOM S3R units on COM5 and COM6 and confirmed the receive state after startup.

On the 128×128 display, Japanese and Simplified Chinese text is supported, and half-width kana is drawn at an eight-pixel width. The user confirmed this width on both devices after a correction. The firmware also includes 16×16, 32-color sprites generated from 3,963 Unicode 18.0 fully qualified Noto Emoji sequences. Initial hardware output was predominantly blue; an RGB565 type correction restored red in ❤️ and 🇯🇵, which the user confirmed on both devices.

The verified build used ESP32 Arduino core 3.3.2, M5Atomic-EchoBase 1.0.2, M5GFX 0.2.32, ESP32S3 Dev Module, 8 MB flash, Default 8MB partition, OPI PSRAM, and USB CDC On Boot. The app-only binary SHA-256 was `A4EB341E1EEC0346B470E9C9A37FCB6CDF599B15600E15CDABA88EEBD92AD4EA`. Browser sample rates, acoustic distance, background-noise conditions, and delivery success rates were not recorded.

## October 26, 2026 — Browser installation and four-language guide

The [browser installer](https://nuwaa.github.io/Can-You-Hear-the-Data/install.html), added in [Web app PR #4](https://github.com/nuwaa/Can-You-Hear-the-Data/pull/4), lets a user flash an ATOM S3R without setting up Arduino. It uses ESP Web Tools and asks the user to confirm the board and replacement of existing firmware and saved settings. ESP32-S3 detection alone does not identify the board as an ATOM S3R.

The distributed merged image contains the app already verified on hardware; only unused trailing `0xFF` bytes were removed from the original 8 MB image. The 3,080,192-byte distributed file has SHA-256 `cb56a9d5905437ce034bc71c88ffb731ab5c09648e004527efa2989a855b6960`. This differs from the app-only hash above because it covers a different file. The Web app build checks its size, hash, and image layout. After publication, the user confirmed browser flashing and subsequent operation on an ATOM S3R. The number of devices tested through the browser, computer environment, flashing time, and failure rate were not recorded.

[Web app PR #5](https://github.com/nuwaa/Can-You-Hear-the-Data/pull/5) added separate installer pages in English, Simplified Chinese, Traditional Chinese, and Japanese. Their content and confirmation gate were checked in headless Chrome, and all four pages were confirmed published. Flashing from each language page was not separately tested on hardware. The [Web app support history](https://github.com/nuwaa/Can-You-Hear-the-Data/blob/main/docs/ATOM_S3R_SUPPORT_HISTORY.md) records the distribution details.
