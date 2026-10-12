# AtomS3R Acoustic Modem

[日本語](README.md) | **繁體中文（臺灣）** | [简体中文](README.zh-CN.md) | [English](README.en.md)

這是使用 M5Stack ATOM S3R 與 ATOMIC ECHO BASE（Atomic Voice Base）的音響 AX.25 數據機原始碼保存版。電腦或 Android 裝置透過 USB-C 連接 ATOM；兩台 ATOM 則以空氣中的 1200 bps Bell 202 AFSK 傳輸資料，不使用無線電發射機。本頁說明 `main` 分支的保存版；Bell 103 功能另於 `feature/bell103` 分支開發。

10 月 5 日起的開發過程與實機測試記錄在[開發日誌](docs/DEVELOPMENT_DIARY.zh-TW.md)，後續也會持續補充。

## 硬體

- 每個節點：ATOM S3R、ATOMIC ECHO BASE、USB-C 資料線，以及作為 USB 主機的電腦或 Android 裝置。
- 兩個節點：擺放時須讓一方的喇叭聲能傳到另一方的麥克風。兩台 Android 互聊需要兩組完整設備。
- 使用 ES8311 音訊編解碼器。韌體腳位：SDA=GPIO38、SCL=39、I2S BCLK=8、WS=6、TX=5、RX=7。

## 開發環境與相依套件

- Arduino IDE 或 Arduino CLI，搭配 Espressif `esp32` Arduino core **3.3.2**。
- 開發板設定：**ESP32S3 Dev Module**、Flash **8 MB**、PSRAM **OPI**，並啟用 **USB CDC On Boot**。
- Arduino 函式庫：[M5Atomic-EchoBase](https://github.com/m5stack/M5Atomic-EchoBase) **1.0.2**、[M5GFX](https://github.com/m5stack/M5GFX) **0.2.32**。
- Android 應用程式：Android Studio、JDK 17、Android SDK Platform 37；Gradle Wrapper **9.6.0**、Android Gradle Plugin **9.4.0**。
- 電腦端 Python 工具：Python 3 與 `pyserial`。Windows IP 通道所需的 [Wintun](https://www.wintun.net/) 須另外取得。

本儲存庫未附上 Arduino core、上述函式庫原始碼或 Wintun DLL。授權資訊請見[第三方相依套件](THIRD_PARTY.md)。

## 建置

1. 在 Arduino IDE 的開發板管理員安裝 Espressif `esp32` 3.3.2，並在函式庫管理員安裝上述兩個函式庫。
2. 開啟 [AtomS3R_AfskRx.ino](outputs/AtomS3R_AfskRx/AtomS3R_AfskRx.ino)，選擇上述開發板設定，再指定各 ATOM 的 USB 連接埠進行驗證與燒錄。若裝置已有設定，燒錄前請確認目標與設定。
3. 用 Android Studio 開啟 [AtomUsbChat](outputs/android/AtomUsbChat)，同步專案並建置 `app` 的 debug APK。也可在該目錄執行 Windows 的 `gradlew.bat :app:assembleDebug`，或 macOS/Linux 的 `./gradlew :app:assembleDebug`。

公開版已移除開發電腦專用的除錯簽章檔絕對路徑，改用 Android 標準除錯簽章。應用程式的 Java 原始碼、manifest 與資源均包含在內。

## USB 連接與使用

在 Android 啟用 USB 主機（OTG），再以 USB-C 連接 ATOM。於應用程式按「ATOM USB接続」、允許 USB 存取，並確認畫面顯示「USB-C接続済み」。一般聊天選「直接」；多節點傳送及遺失訊息復原選「グループ CHAT」。只有需要 IP 通訊時才按「IPトンネル開始」並允許 Android 的 VPN 要求。IP 封包會獨立於應用程式內的聊天，透過音響鏈路傳送。

電腦端使用 ATOM 的 USB CDC 序列埠。先以 **115200 bps** 開啟序列監控程式，輸入 `?` 可查看指令清單。若要使用 Python 聊天介面，請將 [settings.example.json](outputs/environment/settings.example.json) 複製為 `outputs/environment/settings.json`，填入連接埠及 Python 函式庫位置。安裝 `pyserial` 後，可在儲存庫根目錄執行 `python outputs/usb_chat_web.py --port COM6`，再於電腦瀏覽器開啟 `http://127.0.0.1:8766/`。請勿將本機設定提交至 Git；同一個 COM 埠無法同時由多個程式開啟。

## 已實作功能與驗證狀態

- ES8311 的 48 kHz PCM 輸入／輸出、1200/2200 Hz Bell 202 AFSK、1200 bps AX.25 UI 訊框、HDLC/NRZI，以及 FCS/CRC 驗證。
- 透過 Serial 顯示接收訊框的十六進位資料與本文；錄音後解碼、傳送與即時接收。
- UTF-8 直接聊天，支援分段、ACK 與重傳；群組 CHAT 以 SUMMARY/NACK 復原遺失訊息並避免舊訊息重複顯示。
- Android USB 主機與電腦 USB CDC 連接；選用的 IPv4 通道、ping/traceroute，以及聊天與 IP 通訊並用。
- 已以兩台 ATOM 與 Android／電腦驗證雙向直接聊天、群組聊天及 ping；兩台 Android 間的直接聊天也已驗證。
- 已包含僅接收的封包監控模式原始碼，但尚未以第三台實機進行側錄測試。

音響鏈路為半雙工；音量、裝置位置與環境雜音會影響成功率及延遲。電腦診斷工具與測試原始碼位於 `outputs/`。錄音、日誌、裝置 Flash 備份、APK 及本機設定不列入公開內容。

## 後續規劃

計畫加入可與現有 AX.25/Bell 202 路徑切換的 300 bps Bell 103 音響模式。**此 `main` 保存版尚未包含該功能**；相關開發位於 `feature/bell103`。

## 授權

本專案自行撰寫的原始碼採用 [MIT License](LICENSE)。第三方元件仍依各自授權條款使用，請見 [THIRD_PARTY.md](THIRD_PARTY.md)。
