# 用 iPhone 拍摄两台设备的声学通信

[日本語](VIDEO_SHOOTING_GUIDE.md) | [繁體中文（臺灣）](VIDEO_SHOOTING_GUIDE.zh-TW.md) | **简体中文** | [English](VIDEO_SHOOTING_GUIDE.en.md)

本脚本演示 `feature/bell103` 分支的 AX.25 / 1200 bps Bell 202 和本项目的 300 bps Bell 103 模式。iPhone 只负责拍摄；Android A、B 分别通过 USB-C 连接一台 ATOM S3R + Atomic Echo Base。ATOM 之间通过空气中的声音通信，不使用无线电发射机或聊天服务器。

```text
Android A ─USB-C─ ATOM A ))) 空气中的声音 ((( ATOM B ─USB-C─ Android B
                              ↑
                         iPhone 拍摄
```

## 拍摄前

1. 两台 Android 各连接自己的 ATOM，确认应用显示“ATOM接続済み”。必要时打开“詳細”，点击“USB再接続”并允许 USB 访问。
2. 把两台 ATOM 的扬声器和麦克风固定在先前测试成功的位置。同一个画面拍到两台 Android 和两台 ATOM。先试拍十秒，检查 iPhone 是否录到 AFSK 和拨号风格的声音。
3. 两台应用在“詳細”中选择“通信: 直接”。不要启动 IP 隧道或只接收监视模式；等待先前消息的送达确认完成。
4. 标记 A/B，保持屏幕点亮，避免私人通知入镜。尽量连续录制并保留原声。

## 片段一：AX.25 / Bell 202 双向聊天

| 步骤 | 操作 | 要拍到的证据 |
| --- | --- | --- |
| 1 | 显示两台均为“通信: 直接” | 两台 ATOM 均已通过 USB 连接 |
| 2 | A 发送 `AX25 A01 横浜市` | A 的发送音、B 的 ATOM 显示、B 应用中的正文、A 的“直接チャット送達確認” |
| 3 | A01 确认送达后，B 发送 `AX25 B01 繁體中文` | B 的发送音、A 的 ATOM 显示、A 应用中的正文、B 的送达确认 |

一次发送一条。如果失败，先保留失败画面用于诊断；重拍时改用 A02/B02。

## 片段二：Bell 103 连接音与双向聊天

保持相同的线缆和 ATOM 位置，确认没有等待中的 AX.25 消息。

| 步骤 | 操作 | 要拍到的证据 |
| --- | --- | --- |
| 1 | B 打开“詳細”并点击“応答” | B 显示 Bell 103 连接中或等待应答 |
| 2 | A 点击“Bell 103 発呼” | 完整录下 A 的 ATOM 发出的拨号风格连接音 |
| 3 | 等两台均显示“Bell 103 · 接続済み” | 连接音结束后，握手仍可能需要一些时间 |
| 4 | A 发送 `B103 A01 横浜市` | B 的正文与 A 的“Bell 103送達確認” |
| 5 | A01 确认送达后，B 发送 `B103 B01 繁體中文` | A 的正文与 B 的送达确认 |
| 6 | 两台均点击“切断” | 返回 AX.25 直接聊天 |
| 7 | 选拍：A 发送 `AX25 復帰 C01` | Bell 103 后 AX.25 仍可通信 |

Bell 103 为 300 bps，正文应简短，下一条须等待 ACK。连接音是拨号风格的再现，不是真正的电话线握手。

## 拍摄后可选：PC 自动验证

将两台 ATOM 从 Android 拔下并接到 PC，确认 Windows 分配 COM5、COM6；以下脚本默认这两个端口。先关闭 PC 聊天、IP 隧道和 Serial Monitor，再在仓库根目录运行。

```bat
TEST_AX25_DIRECT_REGRESSION.cmd
TEST_BELL103_AUTO_DATA.cmd
```

前者验证 AX.25 直接聊天双向收发；后者验证 Bell 103 自动连接、双向正文和 ACK。**ATOM 接在 Android 上拍摄时不要执行。** PASS 信息不能代替实际通信画面。

## 教材说明重点

- AX.25：ATOM 将 USB 文字封装成帧，以 1200 bps Bell 202 AFSK 音频发送，另一台 ATOM 解码。
- Bell 103：发起与应答完成握手后，以 300 bps FSK 发送正文，使用 ACK 和重传。
- 送达确认是对方 ATOM 返回的声学 ACK；视频也应拍到对方 Android 实际显示正文。
- Bell 103 正文使用本项目自定义的同步、帧格式和 CRC；尚未验证与普通电话线 Bell 103 调制解调器互通。
- 视频只证明拍摄时的摆放条件，不代表其他距离或噪声下有相同成功率。
