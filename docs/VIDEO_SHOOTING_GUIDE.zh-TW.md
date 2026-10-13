# 用 iPhone 拍攝兩台裝置的音響通訊

[日本語](VIDEO_SHOOTING_GUIDE.md) | **繁體中文（臺灣）** | [简体中文](VIDEO_SHOOTING_GUIDE.zh-CN.md) | [English](VIDEO_SHOOTING_GUIDE.en.md)

本腳本示範 `feature/bell103` 分支的 AX.25 / 1200 bps Bell 202 與本專案的 300 bps Bell 103 模式。iPhone 僅用於攝影；Android A、B 各以 USB-C 連接一台 ATOM S3R + Atomic Echo Base。ATOM 之間透過空氣中的聲音通訊，不使用無線電發射機或聊天伺服器。

```text
Android A ─USB-C─ ATOM A ))) 空氣中的聲音 ((( ATOM B ─USB-C─ Android B
                              ↑
                         iPhone 攝影
```

## 拍攝前

1. 兩台 Android 各連接自己的 ATOM，確認應用程式顯示「ATOM接続済み」。必要時開啟「詳細」並按「USB再接続」，允許 USB 存取。
2. 將兩台 ATOM 的喇叭與麥克風固定在先前測試成功的位置。同一畫面拍到兩台 Android 和兩台 ATOM。先試拍十秒，檢查 iPhone 是否錄到 AFSK 與撥號風格的聲音。
3. 兩台應用程式在「詳細」中選擇「通信: 直接」。不要啟動 IP 通道或僅接收監控；等先前訊息的送達確認完成。
4. 標示 A/B，保持螢幕亮著，避免私人通知入鏡。盡量連續錄影並保留原聲。

## 片段一：AX.25 / Bell 202 雙向聊天

| 步驟 | 操作 | 要拍到的證據 |
| --- | --- | --- |
| 1 | 顯示兩台均為「通信: 直接」 | 兩台 ATOM 均已透過 USB 連線 |
| 2 | A 傳送 `AX25 A01 横浜市` | A 的傳送音、B 的 ATOM 顯示、B 應用程式的本文、A 的「直接チャット送達確認」 |
| 3 | A01 確認送達後，B 傳送 `AX25 B01 繁體中文` | B 的傳送音、A 的 ATOM 顯示、A 應用程式的本文、B 的送達確認 |

一次傳一則。如果失敗，先保留失敗畫面以利診斷；重拍時改用 A02/B02。

## 片段二：Bell 103 連線音與雙向聊天

維持相同的線材與 ATOM 位置，確認沒有等待中的 AX.25 訊息。

| 步驟 | 操作 | 要拍到的證據 |
| --- | --- | --- |
| 1 | B 開啟「詳細」並按「応答」 | B 顯示 Bell 103 連線中或等待應答 |
| 2 | A 按「Bell 103 発呼」 | 完整錄下 A 的 ATOM 發出的撥號風格連線音 |
| 3 | 等兩台均顯示「Bell 103 · 接続済み」 | 連線音結束後，交握仍可能花一些時間 |
| 4 | A 傳送 `B103 A01 横浜市` | B 的本文與 A 的「Bell 103送達確認」 |
| 5 | A01 確認送達後，B 傳送 `B103 B01 繁體中文` | A 的本文與 B 的送達確認 |
| 6 | 兩台均按「切断」 | 返回 AX.25 直接聊天 |
| 7 | 選拍：A 傳送 `AX25 復帰 C01` | Bell 103 後 AX.25 仍可通訊 |

Bell 103 為 300 bps，本文應簡短，下一則須等 ACK。連線音是撥號風格的再現，不是真正的電話線交握。

## 拍攝後選做：PC 自動驗證

將兩台 ATOM 從 Android 拔下並接到 PC，確認 Windows 指派 COM5、COM6；以下腳本預設這兩個埠。先關閉 PC 聊天、IP 通道與 Serial Monitor，再於儲存庫根目錄執行。

```bat
TEST_AX25_DIRECT_REGRESSION.cmd
TEST_BELL103_AUTO_DATA.cmd
```

前者驗證 AX.25 直接聊天雙向收發；後者驗證 Bell 103 自動連線、雙向本文與 ACK。**ATOM 接在 Android 上拍攝時不要執行。** PASS 訊息不能代替實際通訊影像。

## 教材說明重點

- AX.25：ATOM 將 USB 文字製成訊框，以 1200 bps Bell 202 AFSK 音訊傳送，另一台 ATOM 解碼。
- Bell 103：發呼與應答完成交握後，以 300 bps FSK 傳送本文，使用 ACK 與重傳。
- 送達確認是對方 ATOM 回覆的音響 ACK；影片也應拍到對方 Android 實際顯示本文。
- Bell 103 本文使用本專案自訂的同步、訊框格式與 CRC；尚未驗證與一般電話線 Bell 103 數據機互通。
- 影片只證明拍攝當下的擺放條件，不代表其他距離或噪音下也有相同成功率。
