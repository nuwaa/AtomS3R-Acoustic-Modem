# Filming a two-node acoustic link with an iPhone

[日本語](VIDEO_SHOOTING_GUIDE.md) | [繁體中文（臺灣）](VIDEO_SHOOTING_GUIDE.zh-TW.md) | [简体中文](VIDEO_SHOOTING_GUIDE.zh-CN.md) | **English**

This script demonstrates the `feature/bell103` branch: AX.25 over 1200 bps Bell 202 and the project's 300 bps Bell 103 mode. Use an iPhone only as the camera. Android A and B each host one ATOM S3R + Atomic Echo Base over USB-C. The ATOM units exchange sound through the air; there is no radio transmitter or chat server.

```text
Android A ─USB-C─ ATOM A ))) sound through air ((( ATOM B ─USB-C─ Android B
                               ↑
                         iPhone camera
```

## Before recording

1. Connect each Android device to its ATOM. Confirm that the app shows “ATOM接続済み” (ATOM connected). If needed, open “詳細” (Details), tap “USB再接続” (Reconnect USB), and grant USB access.
2. Fix the ATOM speaker/microphone placement used in successful tests. Frame both Android screens and both ATOM units. Record a ten-second sample to check that the iPhone captures the AFSK tones and dial-up-style sound.
3. In both apps, use Details to select “通信: 直接” (Direct). Do not start the IP tunnel or receive-only monitor. Wait for any earlier delivery to finish.
4. Label the devices A and B, keep their screens awake, and keep private notifications out of frame. Prefer continuous footage with sound.

## Clip 1 — AX.25 / Bell 202 direct chat

| Step | Action | Evidence to capture |
| --- | --- | --- |
| 1 | Show “通信: 直接” on both apps | Both ATOM units connected over USB |
| 2 | Send `AX25 A01 横浜市` from A | A's tone, B's ATOM display, text in B's app, and “直接チャット送達確認” on A |
| 3 | After A01 is acknowledged, send `AX25 B01 繁體中文` from B | B's tone, A's ATOM display, text in A's app, and delivery confirmation on B |

Send one message at a time. If a take fails, record the failure for diagnosis and use A02/B02 for the next attempt.

## Clip 2 — Bell 103 connection sound and two-way chat

Keep the same cables and ATOM placement. Wait until no AX.25 delivery is pending.

| Step | Action | Evidence to capture |
| --- | --- | --- |
| 1 | On B, open Details and tap “応答” (Answer) | B shows Bell 103 connecting or waiting to answer |
| 2 | On A, tap “Bell 103 発呼” (Call) | Record the whole dial-up-style sound from A's ATOM |
| 3 | Wait until both apps show “Bell 103 · 接続済み” | Connection can take time after the sound ends |
| 4 | Send `B103 A01 横浜市` from A | Text in B's app and “Bell 103送達確認” on A |
| 5 | After A01 is acknowledged, send `B103 B01 繁體中文` from B | Text in A's app and delivery confirmation on B |
| 6 | Tap “切断” (Disconnect) on both | Return to AX.25 direct chat |
| 7 | Optional: send `AX25 復帰 C01` from A | AX.25 still works after Bell 103 |

Keep Bell 103 messages short. It runs at 300 bps and waits for an ACK before accepting the next message. The connection sound recreates dial-up audio; it is not actual telephone-line negotiation.

## Optional PC verification after filming

Disconnect both ATOM units from Android and connect them to the PC. Confirm that Windows assigns COM5 and COM6; these scripts assume those port numbers. Close PC chat, IP tunnel, and Serial Monitor, then run the commands from the repository root.

```bat
TEST_AX25_DIRECT_REGRESSION.cmd
TEST_BELL103_AUTO_DATA.cmd
```

The first tests bidirectional AX.25 direct chat; the second tests Bell 103 automatic connection, bidirectional data, and ACK on COM5/COM6. **Do not run them while filming with the ATOM units connected to Android.** A PASS line alone does not replace footage of the actual exchange.

## Explanations for teaching

- AX.25: the ATOM turns USB text into a frame, transmits it as 1200 bps Bell 202 AFSK audio, and the other ATOM decodes it.
- Bell 103: caller and answerer establish a session, then exchange 300 bps FSK text with ACK and retransmission.
- A delivery confirmation is an acoustic ACK from the remote ATOM. Also show the text appearing in the remote Android app.
- Bell 103 text uses project-specific synchronization, framing, and CRC. Interoperability with ordinary telephone-line Bell 103 modems has not been verified.
- The video demonstrates the recorded placement; it does not establish delivery rates at other distances or noise levels.
