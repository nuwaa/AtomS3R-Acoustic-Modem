# AtomS3R Acoustic Modem

**日本語** | [繁體中文（臺灣）](README.zh-TW.md) | [简体中文](README.zh-CN.md) | [English](README.en.md)

この `feature/ggwave` ブランチは、M5Stack ATOM S3R と ATOMIC ECHO BASE（Atomic Voice Base）を使う音響モデムの開発版です。保存済みのBell 202 / AX.25（1200 bps）、Bell 103（300 bps）に、切替可能なggwaveを追加しています。PCまたはAndroidをUSB-CでATOMに接続し、ATOM間は空中の音で通信します。無線送信機は使用しません。AX.25のみの保存版は[mainブランチ](https://github.com/nuwaa/AtomS3R-Acoustic-Modem/tree/main)とタグ `v0.3.1` にあります。

10月5日からの作業と実機試験は [開発日記](docs/DEVELOPMENT_DIARY.md) に記録し、以後の作業も追記します。

2台の実機デモをiPhoneで撮る手順は[撮影台本](docs/VIDEO_SHOOTING_GUIDE.md)を参照してください。

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

Androidアプリの「詳細」→「音響設定」で、ATOMのスピーカー音量（0～100%）とES8311マイクゲイン（0～42 dB、6 dB刻み）を変更できます。近距離・標準・騒音環境（試験用）のプリセットとカスタム設定があり、ATOMは値を保存して再接続後も使います。初期値は50%・6 dBです。画面下部の受信診断値は現在「未測定」の表示で、測定機能はまだありません。PCのシリアルからは `audio show`、`audio volume 50`、`audio gain 6` を使用できます。音量・ゲインはAX.25とBell 103で共用します。

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

Phase 3では、独立したBell 103 FSK診断経路を追加しました。`bell103 selftest` は送受両バンドの合成PCMをCRCまで自己検査し、`bell103 rx answer` と `bell103 tx originate <UTF-8>`、または逆の役割の組み合わせで6秒録音後に短文を復号できます。送信最大80 UTF-8バイト、300 bps、8N1、役割別の2バンド、独自のB103同期とCRC-16を使用します。接続音は再現音であり、独自フレーミングのため一般の電話回線用Bell 103モデムとの相互接続は検証していません。この診断経路は接続手順と別の一方向試験です。

Phase 3の空中試験では、COM5とCOM6の2台で両バンド・両方向の短文をCRC正常で受信しました。再現には `TEST_BELL103_AIR.cmd` を使用します。Phase 4では独立した `Bell103Session` に、HELLO→READY→CONFIRM→ESTABLISHEDの接続制御、セッションIDの照合、重複制御メッセージへの応答、タイムアウトを追加し始めました。`bell103 session selftest` はこの状態遷移の内部試験で、COM6の実機で通過しました。

Phase 4の実機診断用に `bell103 session caller|answerer|tx|rx|show|stop` を追加しました。`caller`/`answerer` でAX.25のライブ受信を止めてBell 103側に切り替え、`tx`/`rx` を交互に実行して4通の制御メッセージを空中で往復させます。`stop` でAX.25へ戻します。2台のPC接続ATOMでの試験は `TEST_BELL103_SESSION_AIR.cmd` を使用します。この4往復は実機で通過しましたが、手動ステップ式の診断です。

接続制御の4往復はCOM5・COM6間の空中試験で通過しました。続いて実験用の `bell103 data send <UTF-8>|tx|rx|show` と `Bell103DataLink` を追加しました。接続後の本文は最大70 UTF-8バイトで、停止待ち方式のACK、18秒後の再送判定、重複DATAの一回だけの表示を実装しています。録音窓の境界でACKを取りこぼす場合に備え、ACKは2回送ります。`bell103 data selftest` はCOM6で、`TEST_BELL103_DATA_AIR.cmd` はCOM5・COM6間で両方向の本文とACKを確認済みです。`TEST_BELL103_RETRY_AIR.cmd` ではACKを1回失わせ、同じDATAの再送を受けても本文を重複表示せず、ACKを再送して復旧しました。

次の段階として `bell103 auto caller|answerer|show|stop` を追加しました。この試験版はATOM自身が録音窓を繰り返し、接続制御・DATA・ACKの送受と再送判定を進めます。`TEST_BELL103_AUTO_CONNECT.cmd` は2台に開始指示を1回ずつ送り、以後PCからTX/RXステップ指示を出さずに接続を確認します。`TEST_BELL103_AUTO_DATA.cmd` では2台間の接続に続き、短文AUTO01/AUTO02とACKが双方向に届くことを確認しました。続けて `TEST_AX25_DIRECT_REGRESSION.cmd` でAX.25直接チャットの双方向が通過しました。録音窓の境界でフレームを取りこぼす可能性は残るため、再送で回復します。

Phase 5のPCブラウザ画面とAndroidアプリには、Bell 103の発呼・応答・切断、接続表示、UTF-8短文の送受信を追加しました。PC画面は [START_BELL103_PC_CHAT.cmd](START_BELL103_PC_CHAT.cmd) または `python outputs/usb_chat_web.py --port COM6` で起動し、Android APKは [BUILD_BELL103_ANDROID.cmd](BUILD_BELL103_ANDROID.cmd) で作れます。Android 2台へワイヤレスADBで入れる場合は、各端末でVPNを一時切断してから [INSTALL_BELL103_ANDROID_WIRELESS.cmd](INSTALL_BELL103_ANDROID_WIRELESS.cmd) を1回ずつ実行します。Bell 103の送信はACKを待って次の本文を受け付けます。Bell 103中はAX.25の直接・グループ選択およびAndroidのIPトンネル操作を無効にし、切断後はAX.25に戻します。Android APKのビルド、Android 2台およびPC↔AndroidでのBell 103双方向本文・ACK、切断後のAX.25双方向チャットは実機で通過しました。

発呼側の `bell103 auto caller` はダイヤルアップ風の接続音を再生し、約250msの無音区間を置いてHELLOを送ります。応答側の `bell103 auto answerer` は先に受信待ちに入ります。READY/CONFIRM/ESTABLISHEDの往復が完了するまで本文は送れません。2台の実機で接続音→HELLOの順序、自動接続、双方向本文・ACKを確認しました。PCブラウザから発呼してAndroidが応答する操作でも、接続音、双方向本文・ACK、切断後のAX.25直接・グループチャットが通過しました。接続音は再現音であり、V.34の実際のネゴシエーションではありません。

受信窓の途中でもCRCが正常なBell 103フレームを復号できた時点で処理を進めるようにしました。COM5・COM6の短時間試験では、同じ2通・ACK 2件・再送0件の条件で、経過時間は以前の約155秒から約124秒でした。試験には2通目までの45秒待機が含まれるため、これは個々の本文の送達時間ではありません。雑音や配置が変わる場合の速度・成功率は別途確認が必要です。

AX.25グループCHATは欠落した本文より新しい本文を一時保留し、SUMMARY/NACKで回復した場合に送信元ごとのID順で表示します。実機の意図的な欠落試験 `TEST_AX25_GROUP_ORDER.cmd` で、音響受信順が逆転しても画面表示順が正常になることを確認しました。直接チャットはPCブラウザ、PCの「ATOM Peer Chat」、Androidで送達確認まで後続を最大16件待機させ、送信失敗時は後続を未送信として止めます。Android 2台の実機では、長いE01と直後のE02が順番どおり各1回届き、両方の送達確認が出ました。受信停止中のE03失敗後、待機中のE04は送信されず、再開後のE05だけが届きました。PC側「ATOM Peer Chat」からAndroidへの実機試験でも、ロック中の長文E24→短文E25が各1回順番どおり届き、E26失敗後のE27は未送信、受信再開後はE28だけが届きました。PCの「送達」は相手ATOMからのACKであり、Androidアプリの表示までを保証するものではありません。

PCの「ATOM Peer Chat」は [START_PC_PEER_CHAT.cmd](START_PC_PEER_CHAT.cmd) にCOMポートを渡して起動できます。WindowsのIPトンネルにはローカルに導入したWintun DLLが必要です。`outputs/environment/settings.json` に `wintun_dll` のパスを設定し、この設定ファイルはGitへ登録しないでください。Androidアプリは、USB接続中にフォアグラウンドサービスとCPUの部分Wake Lockを使用し、通知の許可を求めます。USB切断時はサービスとWake Lockを解除します。画面ロック中の短時間実機試験は通過しましたが、5分ロック試験では本文の欠落を確認しました。初回はColorOSがアプリを強制終了し、バックグラウンド動作を「制限なし」に変更した再試験では強制終了なしでも先行する長文がアプリに表示されませんでした。PCの「送達」は相手ATOMのACKであり、Androidアプリの表示を保証しません。長時間の電池消費も未評価です。

欠落対策として、通常USBモードでAndroidが `inbox on` を送ると、ATOMは受信したAX.25直接・グループの本文をRAM内の16件の受信箱に保管します。Androidは各本文をアプリの保存領域へ同期保存してから `inbox ack` を返し、USB再接続時および接続中の定期的な `inbox pull` で未確認分を再取得します。同一セッション・連番の再取得は重複表示しません。PCの既存チャット、SLIP/PPP、IPv4、Bell 103の経路では受信箱を有効にしません。受信箱は再起動・電源断で消え、17件以上の未確認着信では古いものから失われます。実機では5分以上の画面ロック中に短文F04と長文F09→短文F10を送達し、Androidアプリに各1回、順番どおり表示されました。アプリを停止したまま送達したR01も、再起動後に1回だけ再取得されました。直接・グループの双方向チャットも通過しました。一方、同じ試験中に音響ACKが得られず失敗した試行があり、騒音や配置による音響リンクの成功率改善と、長時間の連続運用は未検証です。

回帰・繰り返し試験では、PC↔AndroidのIPトンネルで両方向のpingが応答しました。[TEST_BELL103_STRESS.cmd](TEST_BELL103_STRESS.cmd) は2台のPC接続ATOMで接続音付きBell 103接続後、短文6通を交互に送って本文・ACK・重複表示を確認し、実機でPASSしました。続けたAX.25直接チャット回帰も双方向PASSです。[TEST_BELL103_1MIN.cmd](TEST_BELL103_1MIN.cmd) と [TEST_BELL103_30MIN.cmd](TEST_BELL103_30MIN.cmd) は経過時間を測定し、交互の短文・ACK・一回だけの着信を検査し、終了時にAX.25へ戻します。COM5・COM6での30分試験は27通すべて着信・ACK、7回の再送でPASSしました。結果はローカルの `outputs/runs` に保存されます。この結果は今回の配置・音量での確認であり、騒音下や長時間連続運用の保証ではありません。

## ライセンス

このリポジトリで作成したソースは [MIT License](LICENSE) です。第三者の依存物は各配布元のライセンスに従います。ggwave-arduino 0.1.10 は [公式ソース](https://github.com/ggerganov/ggwave-arduino) のコミット `2e13b3cf515166317a29bbb7643042ce78650e22` を [third_party/ggwave-arduino](third_party/ggwave-arduino) に同梱し、その [MITライセンス](third_party/ggwave-arduino/LICENSE) と内部の [Reed–Solomon MITライセンス](third_party/ggwave-arduino/src/ggwave/reed-solomon/LICENSE) を保持しています。

## ggwave 開発モード（実機検証中）

公式ggwaveの `DT_FASTEST`（可聴音、固定長16バイト）を独立した第三の通信モードとして追加しました。UTF-8で1通1〜16バイトを扱い、「こんにちは」（15バイト）、「你好」（6バイト）、「Hello」（5バイト）が収まります。長文分割、ACK、再送はまだありません。48 kHzのES8311 I2S PCMと、公式コーデックの24 kHz・512サンプルフレームとの間で2:1変換します。送信中は受信コーデックを停止し、終了後に受信待機へ戻します。音量・マイクゲインは従来と同じATOM保存値を使用します。Bell 103の接続音やAX.25との同時動作はしません。

シリアルでは両ATOMに `ggwave on` を送り、片方から `ggwave send こんにちは`、次に逆方向へ `ggwave send 你好`、最後に `ggwave send Hello` を送ります。`GGWAVE RX TEXT:` の後に本文が出たら復号成功です。終了は両方で `ggwave off` です。PCにCOM5・COM6で2台接続している場合は [TEST_GGWAVE_AIR.cmd](TEST_GGWAVE_AIR.cmd) を使用できます。Androidアプリ0.4.0では「詳細」→「ggwaveを開始」で同じチャット欄を使い、「ggwaveを終了」でAX.25へ戻ります。ggwave中のIPトンネル、グループCHAT、Bell 103は無効です。

PC上では公式ggwave 0.4.0の送受信で、上記3言語を24 kHz固定長DT信号として符号化・復号し、48 kHzへの変換を挟んでも往復することを確認しました。**ATOM実機のggwave送受信、Android↔ATOM、公式PC波形との実機相互通信、メモリ・CPU使用量、既存AX.25/Bell 103の回帰はまだ未検証です。** 実機の結果を得るまでは動作済みとみなしません。
