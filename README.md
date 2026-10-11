# AtomS3R Acoustic Modem

M5Stack ATOM S3R と ATOMIC ECHO BASE（Atomic Voice Base）を使う、音響 AX.25 モデムの現行ソースの保存版です。PC または Android を USB-C で ATOM に接続し、ATOM 間では空中の 1200 bps Bell 202 AFSK で通信します。無線送信機は使用しません。

## ハードウェア

- 各ノード: ATOM S3R、ATOMIC ECHO BASE、USB-C データケーブル、USB ホストとなる PC または Android 端末
- 2 ノード間: 一方のスピーカー音が他方のマイクに届く配置。2 台の Android 間チャットなら上記一式を 2 組使用
- ES8311 コーデックを使用。ファームウェア内の配線は SDA=GPIO38、SCL=39、I2S BCLK=8、WS=6、TX=5、RX=7

## 開発環境と依存関係

- Arduino IDE または Arduino CLI、Espressif `esp32` Arduino core **3.3.2**
- ボード: **ESP32S3 Dev Module**、Flash **8 MB**、PSRAM **OPI**、**USB CDC On Boot** 有効
- Arduino ライブラリ: [M5Atomic-EchoBase](https://github.com/m5stack/M5Atomic-EchoBase) **1.0.2**、[M5GFX](https://github.com/m5stack/M5GFX) **0.2.32**
- Android アプリ: Android Studio、JDK 17、Android SDK Platform 37。Gradle Wrapper **9.6.0** と Android Gradle Plugin **9.4.0** を使用
- PC 側 Python ツール: Python 3 と `pyserial`。IP トンネルを Windows で使用するときは [Wintun](https://www.wintun.net/) を別途入手

依存ライブラリのソースと Wintun DLL は同梱していません。各ライセンスは [THIRD_PARTY.md](THIRD_PARTY.md) を参照してください。

## ビルド

1. Arduino IDE のボードマネージャーで Espressif `esp32` 3.3.2、ライブラリマネージャーで上記 2 ライブラリを導入します。
2. [outputs/AtomS3R_AfskRx/AtomS3R_AfskRx.ino](outputs/AtomS3R_AfskRx/AtomS3R_AfskRx.ino) を開き、上記ボード設定を選びます。各 ATOM の USB ポートを指定して検証・書き込みします。既存端末の設定を保ちたい場合、書き込み前に設定と接続先を確認してください。
3. Android アプリは [outputs/android/AtomUsbChat](outputs/android/AtomUsbChat) を Android Studio で開いて同期し、`app` の debug APK をビルドします。コマンドラインでは同ディレクトリで Windows は `gradlew.bat :app:assembleDebug`、macOS/Linux は `./gradlew :app:assembleDebug` です。

WindowsでESP32-S3のフルビルドを再現する場合は、[build.settings.example.json](outputs/environment/build.settings.example.json) を参考に `outputs/environment/settings.json` を作り、各依存物のローカルパスを設定して [BUILD_BELL103_FIRMWARE.cmd](BUILD_BELL103_FIRMWARE.cmd) を実行します。PythonがPATHにない場合は `settings.json` に `"python": "C:/path/to/python.exe"` を追加します。`settings.json` と生成物はGitの対象外です。現在のBell 103開発ブランチでは、各段階のファームウェア検証にこの手順を使用します。

公開用コピーでは、この PC 固有のデバッグ署名ファイルへの絶対パスを Android のビルド設定から除きました。Android 標準のデバッグ署名を使用します。アプリ本体の Java、マニフェスト、リソースは現行ソースをそのまま収録しています。

## USB 接続と使用

Android 端末は USB ホスト（OTG）を有効にし、USB-C で ATOM に接続します。アプリで「ATOM USB接続」を押して USB アクセスを許可し、「USB-C接続済み」を確認します。通常のチャットは「直接」、複数ノード用の配信と欠落回復は「グループ CHAT」を選びます。IP 通信を使用するときだけ「IPトンネル開始」を押し、Android の VPN 許可を承認します。これによりアプリ内のチャットとは別に IP パケットを音響リンクへ流せます。

PC 側は ATOM の USB CDC シリアルポートを使用します。まずシリアルモニターで **115200 bps** に接続し、`?` でコマンド一覧を表示できます。Python の PC チャット画面を使う場合は、[outputs/environment/settings.example.json](outputs/environment/settings.example.json) を `outputs/environment/settings.json` にコピーし、ポート名と Python ライブラリの場所を設定します。`pyserial` を導入後、リポジトリ直下で `python outputs/usb_chat_web.py --port COM6` のように起動し、`http://127.0.0.1:8766/` を PC のブラウザで開きます。ローカル設定は Git へ登録しないでください。同じ COM ポートを複数のプログラムで同時に開けません。

## 実装済み機能と状態

- ES8311 の 48 kHz PCM 入出力、1200/2200 Hz Bell 202 AFSK、1200 bps AX.25 UI フレーム、HDLC/NRZI、FCS/CRC 検証
- Serial での受信フレーム 16 進表示、本文表示、録音後デコード、送信、ライブ受信
- UTF-8 の直接チャット、分割・ACK・再送。グループ CHAT の SUMMARY/NACK による欠落回復、古いメッセージの再表示抑止
- Android USB ホスト接続、PC USB CDC 接続、任意の IPv4 トンネル、ping/traceroute、チャットと IP 通信の併用
- 2 台の ATOM と Android/PC で直接・グループの双方向チャットと ping を確認済み。Android 2 台の直接チャットも確認済み
- 受信専用パケットモニターのソースは含みますが、3 台目の実機による傍受試験は未実施です

音響経路は半二重で、音量・配置・周囲雑音によって成功率と遅延が変わります。PC 診断ツールやテスト用ソースは `outputs/` に保存しています。録音、ログ、端末 Flash バックアップ、APK、ローカル設定は公開対象から除外しています。

## 今後

`feature/bell103` ブランチでBell 103方式の300 bps音響モデムを段階的に開発中です。`AcousticMode` の区別とSerialの `acoustic show|ax25|bell103` を追加しました。`bell103 tone` はダイヤルアップ風の接続音を再生する診断コマンドです。この音は参考実装の段階構成をもとにしたもので、V.34の完全なネゴシエーションではありません。

Phase 3では、独立したBell 103 FSK診断経路を追加しました。`bell103 selftest` は送受両バンドの合成PCMをCRCまで自己検査し、`bell103 rx answer` と `bell103 tx originate <UTF-8>`、または逆の役割の組み合わせで6秒録音後に短文を復号できます。送信最大80 UTF-8バイト、300 bps、8N1、役割別の2バンド、独自のB103同期とCRC-16を使用します。**この診断経路は未接続の一方向送信で、受信準備の確認・ACK・再送はまだありません**。`acoustic bell103` は接続手順の実装まで拒否され、現行AX.25経路が引き続き動作します。PC/AndroidのBell 103操作画面も未実装です。

Phase 3の空中試験では、COM5とCOM6の2台で両バンド・両方向の短文をCRC正常で受信しました。再現には `TEST_BELL103_AIR.cmd` を使用します。Phase 4では独立した `Bell103Session` に、HELLO→READY→CONFIRM→ESTABLISHEDの接続制御、セッションIDの照合、重複制御メッセージへの応答、タイムアウトを追加し始めました。`bell103 session selftest` はこの状態遷移の内部試験で、COM6の実機で通過しました。

Phase 4の実機診断用に `bell103 session caller|answerer|tx|rx|show|stop` を追加しました。`caller`/`answerer` でAX.25のライブ受信を止めてBell 103側に切り替え、`tx`/`rx` を交互に実行して4通の制御メッセージを空中で往復させます。`stop` でAX.25へ戻します。2台のPC接続ATOMでの試験は `TEST_BELL103_SESSION_AIR.cmd` を使用します。**この4往復の空中試験はまだ未実施で、手動ステップ式の診断です。常時受信、接続後の本文通信、データACK、再送は今後の実装です。**

## ライセンス

このリポジトリで作成したソースは [MIT License](LICENSE) です。第三者の依存物は各配布元のライセンスに従います。
