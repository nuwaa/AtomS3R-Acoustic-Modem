# AtomS3R Acoustic Modem

[日本語](README.md) | [繁體中文（臺灣）](README.zh-TW.md) | **简体中文** | [English](README.en.md)

此 `feature/bell103` 分支是 M5Stack ATOM S3R 与 ATOMIC ECHO BASE（Atomic Voice Base）声学调制解调器的开发版。在保存的 1200 bps Bell 202 / AX.25 模式之外，加入了可切换的 300 bps Bell 103 模式。电脑或 Android 设备通过 USB-C 连接 ATOM；两台 ATOM 通过空气中的声音通信，不使用无线电发射机。仅含 AX.25 的保存版仍位于 `main` 和标签 `v0.3.1`。

10 月 5 日以来的开发过程与实机测试记录在[开发日记](docs/DEVELOPMENT_DIARY.zh-CN.md)，后续也会继续补充。

## 硬件

- 每个节点：ATOM S3R、ATOMIC ECHO BASE、USB-C 数据线，以及充当 USB 主机的电脑或 Android 设备。
- 两个节点：摆放时要让一方的扬声器声音传到另一方的麦克风。两台 Android 设备互聊需要两套完整设备。
- 使用 ES8311 音频编解码器。固件引脚：SDA=GPIO38、SCL=39、I2S BCLK=8、WS=6、TX=5、RX=7。

## 开发环境与依赖

- Arduino IDE 或 Arduino CLI，搭配 Espressif `esp32` Arduino core **3.3.2**。
- 开发板设置：**ESP32S3 Dev Module**、Flash **8 MB**、PSRAM **OPI**，启用 **USB CDC On Boot**。
- Arduino 库：[M5Atomic-EchoBase](https://github.com/m5stack/M5Atomic-EchoBase) **1.0.2**、[M5GFX](https://github.com/m5stack/M5GFX) **0.2.32**。
- Android 应用：Android Studio、JDK 17、Android SDK Platform 37；Gradle Wrapper **9.6.0**、Android Gradle Plugin **9.4.0**。
- 电脑端 Python 工具：Python 3 和 `pyserial`。Windows IP 隧道所需的 [Wintun](https://www.wintun.net/) 需另行获取。

仓库不附带 Arduino core、上述库源码或 Wintun DLL。许可证信息见[第三方依赖](THIRD_PARTY.md)。

## 构建

1. 在 Arduino IDE 的开发板管理器中安装 Espressif `esp32` 3.3.2，并在库管理器中安装上述两个库。
2. 打开 [AtomS3R_AfskRx.ino](outputs/AtomS3R_AfskRx/AtomS3R_AfskRx.ino)，选择上述开发板设置，再指定各 ATOM 的 USB 端口进行验证和烧录。覆盖已有设备之前，请确认目标端口和设备设置。
3. 使用 Android Studio 打开 [AtomUsbChat](outputs/android/AtomUsbChat)，同步项目并构建 `app` 的 debug APK。也可以在该目录运行 Windows 下的 `gradlew.bat :app:assembleDebug`，或 macOS/Linux 下的 `./gradlew :app:assembleDebug`。

公开版已移除开发电脑专用的调试签名文件绝对路径，改用 Android 标准调试签名。应用的 Java 源码、manifest 和资源均包含在内。

## USB 连接与使用

在 Android 上启用 USB 主机（OTG），然后用 USB-C 连接 ATOM。在应用中点击「ATOM USB接続」、允许 USB 访问，并确认显示「USB-C接続済み」。普通聊天选择「直接」；多节点发送和丢失消息恢复选择「グループ CHAT」。仅在需要 IP 通信时点击「IPトンネル開始」，并同意 Android 的 VPN 请求。IP 数据包独立于应用内聊天，通过声学链路传输。

电脑端使用 ATOM 的 USB CDC 串口。先以 **115200 bps** 打开串口监视器，输入 `?` 可查看命令列表。若使用 Python 聊天界面，请把 [settings.example.json](outputs/environment/settings.example.json) 复制为 `outputs/environment/settings.json`，填写端口名和 Python 库路径。安装 `pyserial` 后，可在仓库根目录运行 `python outputs/usb_chat_web.py --port COM6`，然后在电脑浏览器打开 `http://127.0.0.1:8766/`。不要将本地设置提交到 Git；同一个 COM 端口不能由多个程序同时打开。

## 已实现功能与验证状态

- ES8311 的 48 kHz PCM 输入／输出、1200/2200 Hz Bell 202 AFSK、1200 bps AX.25 UI 帧、HDLC/NRZI 和 FCS/CRC 校验。
- 通过 Serial 显示接收帧的十六进制数据及正文；录音后解码、发送和实时接收。
- UTF-8 直接聊天，支持分段、ACK 和重传；群组 CHAT 使用 SUMMARY/NACK 恢复丢失消息并抑制旧消息重复显示。
- Android USB 主机和电脑 USB CDC 连接；可选 IPv4 隧道、ping/traceroute，以及聊天与 IP 通信并用。
- 已用两台 ATOM 和 Android／电脑验证双向直接聊天、群组聊天及 ping；两台 Android 设备之间的直接聊天也已验证。
- 已包含只接收数据包监视模式的源码，但尚未使用第三台实机进行监听测试。

声学链路为半双工；音量、设备位置和环境噪声会影响成功率及延迟。电脑诊断工具和测试源码位于 `outputs/`。录音、日志、设备 Flash 备份、APK 和本地设置不在公开内容中。

## Bell 103 开发状态

Bell 103 已提供拨号风格连接音、发起／应答握手、半双工 UTF-8 文字、ACK 与重传，可以从电脑和 Android 聊天界面操作。10 月 13 日两台 ATOM 的 30 分钟实机测试中，32 条消息各送达一次、收到 32 次 ACK，没有重传；之后 AX.25 直接聊天也双向通过。这只是当时设备摆放条件下的结果，不保证其他声学环境。连接音没有修改；等待时间和限制记录在开发日记中。

## 许可证

本项目自行编写的源码采用 [MIT License](LICENSE)。第三方组件仍遵循各自的许可条款，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。
