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
