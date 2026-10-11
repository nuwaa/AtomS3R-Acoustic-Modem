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

Phase 3では、独立したBell 103 FSK診断経路を追加しました。`bell103 selftest` は送受両バンドの合成PCMをCRCまで自己検査し、`bell103 rx answer` と `bell103 tx originate <UTF-8>`、または逆の役割の組み合わせで6秒録音後に短文を復号できます。送信最大80 UTF-8バイト、300 bps、8N1、役割別の2バンド、独自のB103同期とCRC-16を使用します。この診断経路は接続手順と別の一方向試験です。

Phase 3の空中試験では、COM5とCOM6の2台で両バンド・両方向の短文をCRC正常で受信しました。再現には `TEST_BELL103_AIR.cmd` を使用します。Phase 4では独立した `Bell103Session` に、HELLO→READY→CONFIRM→ESTABLISHEDの接続制御、セッションIDの照合、重複制御メッセージへの応答、タイムアウトを追加し始めました。`bell103 session selftest` はこの状態遷移の内部試験で、COM6の実機で通過しました。

Phase 4の実機診断用に `bell103 session caller|answerer|tx|rx|show|stop` を追加しました。`caller`/`answerer` でAX.25のライブ受信を止めてBell 103側に切り替え、`tx`/`rx` を交互に実行して4通の制御メッセージを空中で往復させます。`stop` でAX.25へ戻します。2台のPC接続ATOMでの試験は `TEST_BELL103_SESSION_AIR.cmd` を使用します。この4往復は実機で通過しましたが、手動ステップ式の診断です。

接続制御の4往復はCOM5・COM6間の空中試験で通過しました。続いて実験用の `bell103 data send <UTF-8>|tx|rx|show` と `Bell103DataLink` を追加しました。接続後の本文は最大70 UTF-8バイトで、停止待ち方式のACK、18秒後の再送判定、重複DATAの一回だけの表示を実装しています。録音窓の境界でACKを取りこぼす場合に備え、ACKは2回送ります。`bell103 data selftest` はCOM6で、`TEST_BELL103_DATA_AIR.cmd` はCOM5・COM6間で両方向の本文とACKを確認済みです。`TEST_BELL103_RETRY_AIR.cmd` ではACKを1回失わせ、同じDATAの再送を受けても本文を重複表示せず、ACKを再送して復旧しました。

次の段階として `bell103 auto caller|answerer|show|stop` を追加しました。この試験版はATOM自身が録音窓を繰り返し、接続制御・DATA・ACKの送受と再送判定を進めます。`TEST_BELL103_AUTO_CONNECT.cmd` は2台に開始指示を1回ずつ送り、以後PCからTX/RXステップ指示を出さずに接続を確認します。`TEST_BELL103_AUTO_DATA.cmd` では2台間の接続に続き、短文AUTO01/AUTO02とACKが双方向に届くことを確認しました。続けて `TEST_AX25_DIRECT_REGRESSION.cmd` でAX.25直接チャットの双方向が通過しました。録音窓の境界でフレームを取りこぼす可能性は残るため、再送で回復します。

Phase 5のPCブラウザ画面とAndroidアプリには、Bell 103の発呼・応答・切断、接続表示、UTF-8短文の送受信を追加しました。PC画面は [START_BELL103_PC_CHAT.cmd](START_BELL103_PC_CHAT.cmd) または `python outputs/usb_chat_web.py --port COM6` で起動し、Android APKは [BUILD_BELL103_ANDROID.cmd](BUILD_BELL103_ANDROID.cmd) で作れます。Android 2台へワイヤレスADBで入れる場合は、各端末でVPNを一時切断してから [INSTALL_BELL103_ANDROID_WIRELESS.cmd](INSTALL_BELL103_ANDROID_WIRELESS.cmd) を1回ずつ実行します。Bell 103の送信はACKを待って次の本文を受け付けます。Bell 103中はAX.25の直接・グループ選択およびAndroidのIPトンネル操作を無効にし、切断後はAX.25に戻します。Android APKのビルド、Android 2台およびPC↔AndroidでのBell 103双方向本文・ACK、切断後のAX.25双方向チャットは実機で通過しました。

発呼側の `bell103 auto caller` はダイヤルアップ風の接続音を再生し、約250msの無音区間を置いてHELLOを送ります。応答側の `bell103 auto answerer` は先に受信待ちに入ります。READY/CONFIRM/ESTABLISHEDの往復が完了するまで本文は送れません。2台の実機で接続音→HELLOの順序、自動接続、双方向本文・ACKを確認しました。PCブラウザから発呼してAndroidが応答する操作でも、接続音、双方向本文・ACK、切断後のAX.25直接・グループチャットが通過しました。接続音は再現音であり、V.34の実際のネゴシエーションではありません。録音窓の境界や騒音下を含む長時間試験は未実施です。

回帰・繰り返し試験では、PC↔AndroidのIPトンネルで両方向のpingが応答しました。[TEST_BELL103_STRESS.cmd](TEST_BELL103_STRESS.cmd) は2台のPC接続ATOMで接続音付きBell 103接続後、短文6通を交互に送って本文・ACK・重複表示を確認し、実機でPASSしました。続けたAX.25直接チャット回帰も双方向PASSです。[TEST_BELL103_1MIN.cmd](TEST_BELL103_1MIN.cmd) と [TEST_BELL103_30MIN.cmd](TEST_BELL103_30MIN.cmd) は経過時間を測定し、交互の短文・ACK・一回だけの着信を検査し、終了時にAX.25へ戻します。COM5・COM6での30分試験は27通すべて着信・ACK、7回の再送でPASSしました。結果はローカルの `outputs/runs` に保存されます。この結果は今回の配置・音量での確認であり、騒音下や長時間連続運用の保証ではありません。

## ライセンス

このリポジトリで作成したソースは [MIT License](LICENSE) です。第三者の依存物は各配布元のライセンスに従います。
