package jp.jn1eep.atomusbchat;

import android.app.Activity;
import android.app.AlertDialog;
import android.Manifest;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.res.ColorStateList;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.Insets;
import android.graphics.drawable.GradientDrawable;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.text.TextUtils;
import android.view.ViewGroup;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import java.util.Locale;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public final class MainActivity extends Activity implements UsbCdcTransport.Listener {
    private static final int VPN_REQUEST = 77;
    private UsbCdcTransport usb;
    private TextView status;
    private TextView diagnosticLog;
    private TextView modeLabel;
    private TextView monitorLog;
    private LinearLayout conversation;
    private ScrollView conversationScroll;
    private EditText message;
    private EditText command;
    private Button modeButton;
    private Button monitorButton;
    private Button sendButton;
    private Button vpnButton;
    private Button bellCallerButton;
    private Button bellAnswerButton;
    private Button bellStopButton;
    private int speakerVolume = 50;
    private int microphoneGainDb = 6;
    private int audioProfile = 1;
    private SeekBar activeVolumeSlider;
    private TextView activeVolumeValue;
    private RadioGroup activeGainChoices;
    private RadioGroup activeProfileChoices;
    private TextView activeAudioFeedback;
    private boolean updatingAudioControls;
    private boolean bellActive = false;
    private boolean bellConnected = false;
    private boolean bellPending = false;
    private boolean groupMode = false;
    private boolean monitorMode = false;
    private boolean monitorConfirmed = false;
    private int monitorPacketCount = 0;
    private final MonitorPacketDecoder monitorDecoder = new MonitorPacketDecoder();
    private boolean vpnRequested = false;
    private final AtomicInteger pingSequence = new AtomicInteger();
    private final ConcurrentHashMap<Integer, ArrayBlockingQueue<String>> icmpWaiters = new ConcurrentHashMap<>();
    private final ExecutorService commandExecutor = Executors.newSingleThreadExecutor();
    private final Handler reconnectHandler = new Handler(Looper.getMainLooper());
    private String permissionRequestedDevice;
    private long lastInboxPullMs;
    private final Runnable reconnectPoll = new Runnable() {
        @Override public void run() {
            if (!usb.isConnected()) {
                UsbDevice device = usb.find();
                if (device == null) permissionRequestedDevice = null;
                else if (usb.hasPermission(device)) usb.connect(device);
                else if (!device.getDeviceName().equals(permissionRequestedDevice)) {
                    permissionRequestedDevice = device.getDeviceName();
                    onStatus("USB許可待ち");
                    usb.request(device);
                }
            }
            if (usb.isConnected() && !bellActive && SystemClock.elapsedRealtime()-lastInboxPullMs>=5000) {
                lastInboxPullMs=SystemClock.elapsedRealtime();
                usb.requestInbox();
            }
            reconnectHandler.postDelayed(this, 1500);
        }
    };

    @SuppressWarnings("deprecation")
    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (UsbCdcTransport.ACTION_PERMISSION.equals(action)) {
                UsbDevice device = intent.getParcelableExtra(UsbManager.EXTRA_DEVICE);
                if (device != null && intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)) usb.connect(device);
                else onStatus("USB許可なし");
            } else if (UsbManager.ACTION_USB_DEVICE_ATTACHED.equals(action)) connectUsb();
            else if (UsbManager.ACTION_USB_DEVICE_DETACHED.equals(action)) {
                usb.close();
                permissionRequestedDevice = null;
                onStatus("USB切断");
            }
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        if (Build.VERSION.SDK_INT >= 30) getWindow().setDecorFitsSystemWindows(false);
        usb = new UsbCdcTransport(this, this);

        groupMode = getPreferences(MODE_PRIVATE).getBoolean("groupMode", false);
        monitorMode = getPreferences(MODE_PRIVATE).getBoolean("monitorMode", false);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(238, 244, 240));
        int lineGap = dp(20);
        if (Build.VERSION.SDK_INT >= 30) {
            root.setOnApplyWindowInsetsListener((view, windowInsets) -> {
                Insets bars = windowInsets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                Insets keyboard = windowInsets.getInsets(WindowInsets.Type.ime());
                view.setPadding(0, bars.top + lineGap, 0, Math.max(bars.bottom, keyboard.bottom));
                return windowInsets;
            });
        } else root.setPadding(0, lineGap, 0, 0);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(18), dp(10), dp(12), dp(10));
        header.setBackgroundColor(Color.WHITE);
        LinearLayout heading = new LinearLayout(this);
        heading.setOrientation(LinearLayout.VERTICAL);
        TextView title = new TextView(this);
        title.setText("ATOM Chat");
        title.setTextColor(Color.rgb(30, 56, 45));
        title.setTextSize(21);
        title.setTypeface(null, 1);
        status = new TextView(this);
        status.setText("USB接続を確認中");
        status.setTextColor(Color.rgb(91, 111, 101));
        status.setTextSize(12);
        status.setSingleLine(true);
        status.setEllipsize(TextUtils.TruncateAt.END);
        modeLabel = new TextView(this);
        modeLabel.setText(monitorMode ? "受信専用モニター" : groupMode ? "グループ CHAT" : "直接チャット");
        modeLabel.setTextColor(Color.rgb(51, 122, 78));
        modeLabel.setTextSize(12);
        heading.addView(title);
        heading.addView(status);
        heading.addView(modeLabel);
        header.addView(heading, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        TextView detailsToggle = new TextView(this);
        detailsToggle.setText("詳細  ▾");
        detailsToggle.setTextColor(Color.rgb(27, 116, 67));
        detailsToggle.setTextSize(14);
        detailsToggle.setPadding(dp(10), dp(10), dp(8), dp(10));
        header.addView(detailsToggle);
        root.addView(header);

        LinearLayout details = new LinearLayout(this);
        details.setOrientation(LinearLayout.VERTICAL);
        details.setPadding(dp(16), dp(4), dp(16), dp(12));
        details.setBackgroundColor(Color.WHITE);
        details.setVisibility(View.GONE);
        detailsToggle.setOnClickListener(v -> {
            boolean show = details.getVisibility() != View.VISIBLE;
            details.setVisibility(show ? View.VISIBLE : View.GONE);
            detailsToggle.setText(show ? "詳細  ▴" : "詳細  ▾");
        });
        LinearLayout connectionActions = new LinearLayout(this);
        connectionActions.setOrientation(LinearLayout.HORIZONTAL);
        Button connect = smallButton("USB再接続");
        connect.setOnClickListener(v -> connectUsb());
        vpnButton = smallButton("IPトンネル開始");
        vpnButton.setOnClickListener(v -> startVpn());
        connectionActions.addView(connect, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        connectionActions.addView(vpnButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        details.addView(connectionActions);
        modeButton = smallButton(groupMode ? "通信: グループ CHAT" : "通信: 直接");
        modeButton.setOnClickListener(v -> {
            boolean next = !groupMode;
            try {
                if (usb.hasDirectPending()) throw new IllegalStateException("直接チャットの送達待ちが終わってから切り替えてください");
                usb.setGroupMode(next);
                groupMode = next;
                getPreferences(MODE_PRIVATE).edit().putBoolean("groupMode", next).apply();
                modeButton.setText(next ? "通信: グループ CHAT" : "通信: 直接");
                modeLabel.setText(next ? "グループ CHAT" : "直接チャット");
                append(next ? "グループ CHAT に切り替え" : "直接通信に切り替え");
            } catch (Exception error) { onStatus(error.getMessage()); }
        });
        details.addView(modeButton);
        LinearLayout bellActions = new LinearLayout(this);
        bellActions.setGravity(Gravity.CENTER_VERTICAL);
        bellCallerButton = smallButton("Bell 103 発呼");
        bellAnswerButton = smallButton("応答");
        bellStopButton = smallButton("切断");
        bellCallerButton.setOnClickListener(v -> startBell103(true));
        bellAnswerButton.setOnClickListener(v -> startBell103(false));
        bellStopButton.setOnClickListener(v -> stopBell103());
        bellActions.addView(bellCallerButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        bellActions.addView(bellAnswerButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        bellActions.addView(bellStopButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        details.addView(bellActions);
        Button audioSettings = smallButton("音響設定  ▸");
        audioSettings.setOnClickListener(v -> showAudioSettings());
        details.addView(audioSettings);
        monitorButton = smallButton(monitorMode ? "モニターを終了" : "受信専用モニター開始");
        monitorButton.setOnClickListener(v -> setMonitorMode(!monitorMode));
        details.addView(monitorButton);
        LinearLayout commandLine = new LinearLayout(this);
        commandLine.setGravity(Gravity.CENTER_VERTICAL);
        command = new EditText(this);
        command.setHint("ping / traceroute（診断用）");
        command.setSingleLine(true);
        command.setTextSize(14);
        command.setImeOptions(EditorInfo.IME_ACTION_GO);
        Button runCommand = smallButton("実行");
        runCommand.setOnClickListener(v -> executeCommandFromInput());
        command.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId != EditorInfo.IME_ACTION_GO) return false;
            executeCommandFromInput();
            return true;
        });
        commandLine.addView(command, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        commandLine.addView(runCommand);
        details.addView(commandLine);
        diagnosticLog = new TextView(this);
        diagnosticLog.setTextSize(12);
        diagnosticLog.setTextColor(Color.rgb(92, 104, 97));
        diagnosticLog.setMaxLines(4);
        diagnosticLog.setTextIsSelectable(true);
        details.addView(diagnosticLog);
        root.addView(details);

        conversationScroll = new ScrollView(this);
        conversationScroll.setFillViewport(true);
        conversationScroll.setClipToPadding(false);
        conversationScroll.setPadding(dp(12), dp(14), dp(12), dp(14));
        conversation = new LinearLayout(this);
        conversation.setOrientation(LinearLayout.VERTICAL);
        conversationScroll.addView(conversation);
        monitorLog = new TextView(this);
        monitorLog.setTextSize(12);
        monitorLog.setTextColor(Color.rgb(30, 47, 37));
        monitorLog.setTypeface(Typeface.MONOSPACE);
        monitorLog.setTextIsSelectable(true);
        monitorLog.setPadding(dp(8), dp(8), dp(8), dp(8));
        monitorLog.setText("CRC正常なAX.25パケットを待っています。\n");
        root.addView(conversationScroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        addNotice("メッセージを送ると、ここに表示されます");

        LinearLayout composer = new LinearLayout(this);
        composer.setGravity(Gravity.CENTER_VERTICAL);
        composer.setPadding(dp(12), dp(8), dp(12), dp(8));
        composer.setBackgroundColor(Color.WHITE);
        message = new EditText(this);
        message.setHint("メッセージ");
        message.setSingleLine(true);
        message.setTextSize(16);
        message.setPadding(dp(14), dp(10), dp(14), dp(10));
        message.setBackground(rounded(Color.rgb(247, 249, 247), dp(22)));
        message.setImeOptions(EditorInfo.IME_ACTION_SEND);
        sendButton = new Button(this);
        sendButton.setText("送信");
        sendButton.setTextColor(Color.WHITE);
        sendButton.setAllCaps(false);
        sendButton.setBackgroundTintList(ColorStateList.valueOf(Color.rgb(33, 171, 89)));
        sendButton.setOnClickListener(v -> sendMessage());
        message.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId != EditorInfo.IME_ACTION_SEND) return false;
            sendMessage();
            return true;
        });
        composer.addView(message, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        LinearLayout.LayoutParams sendParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        sendParams.leftMargin = dp(8);
        composer.addView(sendButton, sendParams);
        root.addView(composer);
        setContentView(root);
        refreshMonitorUi();
        java.util.List<InboxStore.Item> saved=usb.savedInbox();
        if(!saved.isEmpty()){
            addNotice("保存済みの受信履歴（"+saved.size()+"件）");
            for(InboxStore.Item item:saved)addBubble(item.source,item.text,false);
        }

        IntentFilter filter = new IntentFilter();
        filter.addAction(UsbCdcTransport.ACTION_PERMISSION);
        filter.addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED);
        filter.addAction(UsbManager.ACTION_USB_DEVICE_DETACHED);
        registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED);
        connectUsb();
        reconnectHandler.postDelayed(reconnectPoll, 1500);
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private TextView audioLabel(String text, int size) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(size);
        label.setTextColor(Color.rgb(39, 49, 44));
        label.setPadding(0, dp(8), 0, dp(4));
        return label;
    }

    private void refreshAudioControls() {
        updatingAudioControls = true;
        if (activeVolumeSlider != null) activeVolumeSlider.setProgress(speakerVolume);
        if (activeVolumeValue != null) activeVolumeValue.setText(speakerVolume + "%");
        if (activeGainChoices != null) activeGainChoices.check(2000 + microphoneGainDb / 6);
        if (activeProfileChoices != null) activeProfileChoices.check(3000 + audioProfile);
        updatingAudioControls = false;
    }

    private void applyAudioSettings(int volume, int gainDb, boolean setVolume, boolean setGain) {
        try {
            if (!usb.isConnected()) throw new IllegalStateException("ATOMをUSB接続してから調整してください");
            if (setVolume) usb.setSpeakerVolume(volume);
            if (setGain) usb.setMicrophoneGain(gainDb);
            speakerVolume = volume;
            microphoneGainDb = gainDb;
            refreshAudioControls();
            if (activeAudioFeedback != null) activeAudioFeedback.setText("ATOMへ設定を送信しました。反映結果を確認中…");
        } catch (RuntimeException error) {
            refreshAudioControls();
            if (activeAudioFeedback != null) activeAudioFeedback.setText(error.getMessage());
            onStatus(error.getMessage());
        }
    }

    private void showAudioSettings() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(20), dp(12), dp(20), dp(18));
        card.setBackgroundColor(Color.WHITE);
        scroll.addView(card);
        card.addView(audioLabel("音響TNC — 音響設定", 18));
        card.addView(audioLabel("動作環境", 13));
        RadioGroup profiles = new RadioGroup(this);
        String[] profileNames = {"近距離（低ゲイン）", "標準", "騒音環境（試験用）", "カスタム設定"};
        for (int index = 0; index < profileNames.length; index++) {
            RadioButton choice = new RadioButton(this);
            choice.setId(3000 + index);
            choice.setText(profileNames[index]);
            choice.setTextSize(14);
            profiles.addView(choice);
        }
        activeProfileChoices = profiles;
        card.addView(profiles);
        card.addView(audioLabel("スピーカー音量", 16));
        TextView volumeValue = audioLabel(speakerVolume + "%", 14);
        activeVolumeValue = volumeValue;
        card.addView(volumeValue);
        SeekBar slider = new SeekBar(this);
        slider.setMax(100);
        activeVolumeSlider = slider;
        card.addView(slider);
        card.addView(audioLabel("小                                                        大", 12));
        card.addView(audioLabel("マイクゲイン", 16));
        RadioGroup gains = new RadioGroup(this);
        gains.setOrientation(RadioGroup.HORIZONTAL);
        for (int gain = 0; gain <= 42; gain += 6) {
            RadioButton choice = new RadioButton(this);
            choice.setId(2000 + gain / 6);
            choice.setText(String.valueOf(gain));
            choice.setTextSize(13);
            gains.addView(choice);
        }
        activeGainChoices = gains;
        // A horizontal container keeps all eight 6 dB steps reachable on narrow phones.
        android.widget.HorizontalScrollView horizontal = new android.widget.HorizontalScrollView(this);
        horizontal.addView(gains);
        card.addView(horizontal);
        card.addView(audioLabel("0～42 dB、6 dB刻み。大きすぎると雑音や音割れに注意してください。", 12));
        card.addView(audioLabel("受信診断", 16));
        card.addView(audioLabel("PCMレベル: 未測定\nクリッピング: 未測定\n受信成功率: 未測定", 13));
        TextView feedback = audioLabel("ATOMから現在の設定を取得中…", 12);
        activeAudioFeedback = feedback;
        card.addView(feedback);
        refreshAudioControls();
        profiles.setOnCheckedChangeListener((group, checkedId) -> {
            if (updatingAudioControls) return;
            int selected = checkedId - 3000;
            if (selected < 0 || selected > 3) return;
            audioProfile = selected;
            if (selected == 0) applyAudioSettings(35, 0, true, true);
            else if (selected == 1) applyAudioSettings(50, 6, true, true);
            else if (selected == 2) applyAudioSettings(75, 12, true, true);
        });
        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser) volumeValue.setText(progress + "%");
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {
                audioProfile = 3;
                applyAudioSettings(seekBar.getProgress(), microphoneGainDb, true, false);
            }
        });
        gains.setOnCheckedChangeListener((group, checkedId) -> {
            if (updatingAudioControls || checkedId < 2000 || checkedId > 2007) return;
            audioProfile = 3;
            applyAudioSettings(speakerVolume, (checkedId - 2000) * 6, false, true);
        });
        AlertDialog dialog = new AlertDialog.Builder(this).setView(scroll).setPositiveButton("閉じる", null).create();
        dialog.setOnDismissListener(ignored -> {
            activeVolumeSlider = null;
            activeVolumeValue = null;
            activeGainChoices = null;
            activeProfileChoices = null;
            activeAudioFeedback = null;
        });
        dialog.show();
        try { usb.requestAudioSettings(); }
        catch (RuntimeException error) { feedback.setText(error.getMessage()); }
    }

    private GradientDrawable rounded(int color, int radius) {
        GradientDrawable background = new GradientDrawable();
        background.setColor(color);
        background.setCornerRadius(radius);
        return background;
    }

    private Button smallButton(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextSize(12);
        button.setMinHeight(dp(38));
        return button;
    }

    private void addNotice(String text) {
        TextView notice = new TextView(this);
        notice.setText(text);
        notice.setTextColor(Color.rgb(111, 127, 118));
        notice.setTextSize(12);
        notice.setGravity(Gravity.CENTER);
        notice.setPadding(dp(8), dp(8), dp(8), dp(14));
        conversation.addView(notice);
    }

    private void addBubble(String sender, String text, boolean outgoing) {
        runOnUiThread(() -> {
            LinearLayout row = new LinearLayout(this);
            row.setGravity(outgoing ? Gravity.END : Gravity.START);
            LinearLayout.LayoutParams rowParams = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            rowParams.bottomMargin = dp(12);
            LinearLayout stack = new LinearLayout(this);
            stack.setOrientation(LinearLayout.VERTICAL);
            TextView name = new TextView(this);
            name.setText(outgoing ? "自分" : sender);
            name.setTextColor(Color.rgb(104, 124, 113));
            name.setTextSize(11);
            name.setGravity(outgoing ? Gravity.END : Gravity.START);
            name.setPadding(dp(5), 0, dp(5), dp(3));
            stack.addView(name);
            TextView body = new TextView(this);
            body.setText(text);
            body.setTextColor(Color.rgb(30, 47, 37));
            body.setTextSize(16);
            body.setTextIsSelectable(true);
            body.setMaxWidth((int)(getResources().getDisplayMetrics().widthPixels * 0.78f));
            body.setPadding(dp(13), dp(10), dp(13), dp(10));
            body.setBackground(rounded(outgoing ? Color.rgb(201, 244, 193) : Color.WHITE, dp(18)));
            stack.addView(body);
            row.addView(stack);
            conversation.addView(row, rowParams);
            conversationScroll.post(() -> conversationScroll.fullScroll(View.FOCUS_DOWN));
        });
    }

    private void sendMessage() {
        if (monitorMode) return;
        String text = message.getText().toString();
        if (text.isEmpty()) return;
        try {
            if (bellActive) {
                if (!bellConnected) { onStatus("Bell 103接続待ちです"); return; }
                if (bellPending) { onStatus("前のBell 103本文のACK待ちです"); return; }
                usb.sendBell103(text);
                bellPending = true;
                addBubble("自分 (Bell 103)", text, true);
                message.setText("");
                return;
            }
            if (text.equals("/rx-off") || text.equals("/rx-on")) {
                boolean enabled = text.equals("/rx-on");
                usb.setAcousticReceiverEnabled(enabled);
                append("診断: ATOMへ音響受信の" + (enabled ? "再開" : "停止") + "を指示しました");
                message.setText("");
                return;
            }
            if (groupMode) usb.sendGroup(text);
            else usb.send(text);
            addBubble(groupMode ? "自分" : "自分（送信待ち）", text, true);
            message.setText("");
        } catch (Exception error) {
            onStatus(error.getMessage());
        }
    }

    private void startBell103(boolean caller) {
        if (monitorMode) { onStatus("モニターを終了してからBell 103を開始してください"); return; }
        if (usb.hasDirectPending()) { onStatus("直接チャットの送達待ちが終わってから切り替えてください"); return; }
        try {
            vpnRequested = false;
            AtomVpnService.attachUsb(null);
            stopService(new Intent(this, AtomVpnService.class));
            usb.startBell103(caller);
            bellActive = true;
            bellConnected = false;
            bellPending = false;
            groupMode = false;
            getPreferences(MODE_PRIVATE).edit().putBoolean("groupMode", false).apply();
            modeButton.setText("通信: 直接");
            refreshMonitorUi();
            addNotice("Bell 103 " + (caller ? "発呼中" : "応答待ち") + "。双方が接続済みになるまで送信できません");
        } catch (Exception error) { onStatus(error.getMessage()); }
    }

    private void stopBell103() {
        try {
            usb.stopBell103();
            bellActive = false;
            bellConnected = false;
            bellPending = false;
            refreshMonitorUi();
            addNotice("Bell 103切断。AX.25に戻りました");
        } catch (Exception error) { onStatus(error.getMessage()); }
    }

    private void connectUsb() {
        UsbDevice device = usb.find();
        if (device == null) { onStatus(usb.describeDevices()); return; }
        if (usb.isConnected()) return;
        if (usb.hasPermission(device)) usb.connect(device);
        else { permissionRequestedDevice = device.getDeviceName(); onStatus("USB許可待ち"); usb.request(device); }
    }

    private void startVpn() {
        if (bellActive) { onStatus("Bell 103を切断してからIPトンネルを開始してください"); return; }
        if (monitorMode) { onStatus("モニター中はIPトンネルを開始できません"); return; }
        Intent permission = android.net.VpnService.prepare(this);
        if (permission != null) startActivityForResult(permission, VPN_REQUEST);
        else enableVpn();
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == VPN_REQUEST && resultCode == RESULT_OK) enableVpn();
        else if (requestCode == VPN_REQUEST) onStatus("VPN許可なし");
    }

    private void enableVpn() {
        vpnRequested = true;
        AtomVpnService.attachUsb(usb::sendIpv4);
        startService(new Intent(this, AtomVpnService.class));
        onStatus("IPトンネル 10.77.0.2 開始中");
    }

    private void executeCommandFromInput() {
        String line = command.getText().toString().trim();
        if (line.isEmpty()) return;
        command.setText("");
        executeCommand(line);
    }

    private void executeCommand(String line) {
        append("$ " + line);
        commandExecutor.execute(() -> {
            String[] words = line.trim().split("\\s+");
            String name = words[0].toLowerCase(Locale.ROOT);
            if ("help".equals(name)) {
                append("commands: ping <IPv4>, traceroute <IPv4>, help");
            } else if (("ping".equals(name) || "traceroute".equals(name)) && words.length == 2) {
                byte[] destination = parseIpv4(words[1]);
                if (destination == null) append("IPv4アドレスが不正です: " + words[1]);
                else if ("ping".equals(name)) runPing(words[1], destination);
                else runTraceroute(words[1], destination);
            } else {
                append("usage: ping <IPv4> | traceroute <IPv4> | help");
            }
        });
    }

    private void runPing(String destinationText, byte[] destination) {
        int sequence = pingSequence.incrementAndGet() & 0xffff;
        ArrayBlockingQueue<String> reply = new ArrayBlockingQueue<>(1);
        icmpWaiters.put(sequence, reply);
        try {
            long started = System.currentTimeMillis();
            usb.sendIpv4(makePing(sequence, destination, 64));
            append("ICMP Echo送信: " + destinationText + " seq=" + sequence);
            String source = reply.poll(60, TimeUnit.SECONDS);
            if (source == null) append("ping timeout: " + destinationText);
            else append("reply from " + source + ": seq=" + sequence + " time=" + (System.currentTimeMillis() - started) + " ms");
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        } catch (Exception error) {
            append("ping送信失敗: " + error.getMessage());
        } finally {
            icmpWaiters.remove(sequence);
        }
    }

    private void runTraceroute(String destinationText, byte[] destination) {
        append("traceroute to " + destinationText + ", max 8 hops");
        for (int ttl = 1; ttl <= 8; ttl++) {
            int sequence = pingSequence.incrementAndGet() & 0xffff;
            ArrayBlockingQueue<String> reply = new ArrayBlockingQueue<>(1);
            icmpWaiters.put(sequence, reply);
            try {
                long started = System.currentTimeMillis();
                usb.sendIpv4(makePing(sequence, destination, ttl));
                String source = reply.poll(60, TimeUnit.SECONDS);
                if (source == null) append(String.format(Locale.ROOT, "%2d  *", ttl));
                else {
                    append(String.format(Locale.ROOT, "%2d  %s  %d ms", ttl, source, System.currentTimeMillis() - started));
                    if (destinationText.equals(source)) break;
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
                return;
            } catch (Exception error) {
                append("traceroute送信失敗: " + error.getMessage());
                return;
            } finally {
                icmpWaiters.remove(sequence);
            }
        }
    }

    private static byte[] makePing(int sequence, byte[] destination, int ttl) {
        byte[] packet = new byte[36];
        packet[0] = 0x45; packet[2] = 0; packet[3] = 36;
        packet[6] = 0x40; packet[8] = (byte) ttl; packet[9] = 1;
        packet[12] = 10; packet[13] = 77; packet[14] = 0; packet[15] = 2;
        System.arraycopy(destination, 0, packet, 16, 4);
        packet[20] = 8; packet[24] = (byte) 0xa7; packet[25] = 0x02;
        packet[26] = (byte) (sequence >>> 8); packet[27] = (byte) sequence;
        byte[] marker = {'A','T','O','M','P','I','N','G'};
        System.arraycopy(marker, 0, packet, 28, marker.length);
        int icmpChecksum = checksum(packet, 20, 16);
        packet[22] = (byte) (icmpChecksum >>> 8); packet[23] = (byte) icmpChecksum;
        int ipChecksum = checksum(packet, 0, 20);
        packet[10] = (byte) (ipChecksum >>> 8); packet[11] = (byte) ipChecksum;
        return packet;
    }

    private static byte[] parseIpv4(String text) {
        String[] parts = text.split("\\.", -1);
        if (parts.length != 4) return null;
        byte[] address = new byte[4];
        try {
            for (int i = 0; i < 4; i++) {
                int value = Integer.parseInt(parts[i]);
                if (value < 0 || value > 255) return null;
                address[i] = (byte) value;
            }
            return address;
        } catch (NumberFormatException error) { return null; }
    }

    private static String sourceAddress(byte[] packet) {
        return String.format(Locale.ROOT, "%d.%d.%d.%d", packet[12] & 255, packet[13] & 255, packet[14] & 255, packet[15] & 255);
    }

    private static int checksum(byte[] data, int offset, int length) {
        int sum = 0;
        for (int i = offset; i < offset + length; i += 2) {
            sum += (data[i] & 255) << 8;
            if (i + 1 < offset + length) sum += data[i + 1] & 255;
        }
        while ((sum >>> 16) != 0) sum = (sum & 0xffff) + (sum >>> 16);
        return (~sum) & 0xffff;
    }

    private void append(String text) { runOnUiThread(() -> {
        String next = diagnosticLog.getText() + text + "\n";
        if (next.length() > 2400) next = next.substring(next.length() - 2400);
        diagnosticLog.setText(next);
    }); }
    private void setMonitorMode(boolean enabled) {
        if (bellActive) { onStatus("Bell 103を切断してからモニターに切り替えてください"); return; }
        try {
            if (enabled) {
                vpnRequested = false;
                AtomVpnService.attachUsb(null);
                stopService(new Intent(this, AtomVpnService.class));
                usb.setGroupMode(false);
            }
            usb.setMonitorMode(enabled);
            monitorMode = enabled;
            monitorConfirmed = false;
            getPreferences(MODE_PRIVATE).edit().putBoolean("monitorMode", enabled).apply();
            if (!enabled) usb.setGroupMode(groupMode);
            refreshMonitorUi();
        } catch (Exception error) { onStatus(error.getMessage()); }
    }
    private void refreshMonitorUi() {
        modeLabel.setText(bellActive ? (bellConnected ? "Bell 103 · 接続済み" : "Bell 103 · 接続中") : monitorMode ? (monitorConfirmed ? "受信専用モニター · " + monitorPacketCount + " packets" : "モニター確認待ち") :
                groupMode ? "グループ CHAT" : "直接チャット");
        modeButton.setEnabled(!monitorMode && !bellActive);
        vpnButton.setEnabled(!monitorMode && !bellActive);
        message.setEnabled(!monitorMode);
        sendButton.setEnabled(!monitorMode && (!bellActive || bellConnected));
        command.setEnabled(!monitorMode && !bellActive);
        bellCallerButton.setEnabled(!monitorMode && !bellActive);
        bellAnswerButton.setEnabled(!monitorMode && !bellActive);
        bellStopButton.setEnabled(bellActive);
        monitorButton.setEnabled(!bellActive);
        monitorButton.setText(monitorMode ? "モニターを終了" : "受信専用モニター開始");
        conversationScroll.removeAllViews();
        conversationScroll.addView(monitorMode ? monitorLog : conversation);
    }
    @Override public void onStatus(String text) { runOnUiThread(() -> {
        String shown = text;
        if (text.startsWith("AUDIO CONFIG ")) {
            java.util.regex.Matcher settings = java.util.regex.Pattern.compile("volume=(\\d+) gain_db=(\\d+)").matcher(text);
            if (settings.find()) {
                speakerVolume = Integer.parseInt(settings.group(1));
                microphoneGainDb = Integer.parseInt(settings.group(2));
                audioProfile = speakerVolume == 35 && microphoneGainDb == 0 ? 0
                        : speakerVolume == 50 && microphoneGainDb == 6 ? 1
                        : speakerVolume == 75 && microphoneGainDb == 12 ? 2 : 3;
                refreshAudioControls();
                if (activeAudioFeedback != null) activeAudioFeedback.setText("ATOMに反映済み: 音量 " + speakerVolume + "% / マイク " + microphoneGainDb + " dB");
            }
            return;
        } else if (text.startsWith("ERROR: audio ")) {
            if (activeAudioFeedback != null) activeAudioFeedback.setText(text);
        }
        if (text.startsWith("USB-C接続済み")) {monitorConfirmed = false;bellActive = false;bellConnected = false;bellPending = false;refreshMonitorUi();shown = "ATOM接続済み";}
        else if (text.startsWith("BELL103 AUTO RX CONTROL") && text.contains("state=connected")) {bellConnected = true;refreshMonitorUi();shown = "Bell 103接続済み";}
        else if (text.startsWith("BELL103 SESSION STOP") || text.startsWith("BELL103 AUTO CONNECT TIMEOUT")) {bellActive = false;bellConnected = false;bellPending = false;refreshMonitorUi();shown = "Bell 103切断";}
        else if (text.startsWith("BELL103 AUTO ACK OK")) {bellPending = false;shown = "Bell 103送達確認";}
        else if (text.startsWith("BELL103 AUTO DATA RETRIES EXHAUSTED") || text.startsWith("BELL103 DATA QUEUE FAILED") || text.startsWith("ERROR: Bell 103")) bellPending = false;
        else if (text.startsWith("AX25 DIRECT SENT")) {shown = "直接チャット送達確認";addNotice(shown);}
        else if (text.startsWith("AX25 DIRECT FAILED") || text.startsWith("AX25 DIRECT BUSY_OR_INVALID")) {shown = "直接チャット送信失敗・後続は未送信";addNotice(shown);}
        else if (text.startsWith("AX25 DIRECT USB_DISCONNECTED")) {shown = "USB切断・直接チャットは未送信";addNotice(shown);}
        else if (text.startsWith("STATE RX LISTEN")) shown = "ATOM接続済み・受信中";
        else if (text.startsWith("LIVE RX stopped")) shown = "受信停止中";
        else if (text.equals("USB切断")) {bellActive = false;bellConnected = false;bellPending = false;refreshMonitorUi();shown = "ATOM未接続";}
        else if (text.startsWith("MONITOR MODE=on")) {
            monitorConfirmed = true;
            shown = "ATOM接続済み・受信専用";
            refreshMonitorUi();
        }
        else if (text.startsWith("MONITOR MODE=off")) monitorConfirmed = false;
        if (text.equals("USB切断")) monitorConfirmed = false;
        status.setText(shown);
        if (!text.startsWith("STATE RX LISTEN")) append(text);
        if (text.startsWith("USB-C接続済み")) {
            try { startForegroundService(new Intent(this, UsbConnectionService.class)); }
            catch (RuntimeException error) { append("USB背景受信の開始失敗: " + error.getMessage()); }
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
                    && !getPreferences(MODE_PRIVATE).getBoolean("notificationPrompted", false)) {
                getPreferences(MODE_PRIVATE).edit().putBoolean("notificationPrompted", true).apply();
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 103);
            }
        } else if (text.equals("USB切断")) stopService(new Intent(this, UsbConnectionService.class));
        if(text.startsWith("USB-C接続済み"))status.postDelayed(() -> {
            try {
                if (monitorMode) {usb.setGroupMode(false);usb.setMonitorMode(true);}
                else if (!bellActive) usb.setGroupMode(groupMode);
                usb.requestAudioSettings();
                if (vpnRequested && !monitorMode) {
                    AtomVpnService.attachUsb(usb::sendIpv4);
                    startService(new Intent(this, AtomVpnService.class));
                }
            } catch (Exception error) { status.setText(error.getMessage()); }
        }, 1000);
    }); }
    @Override public void onMessage(String source, String destination, String text) { addBubble(source, text, false); }
    @Override public void onGroupMessage(String source, String text) { addBubble(source, text, false); }
    @Override public void onBell103Message(String text) { addBubble("Bell 103", text, false); }
    @Override public void onMonitorPacket(String source,String destination,int control,int pid,byte[] payload) {
        if (!monitorMode || !monitorConfirmed) return;
        runOnUiThread(() -> {
            if (!monitorMode || !monitorConfirmed) return;
            String stamp = new java.text.SimpleDateFormat("HH:mm:ss", Locale.JAPAN).format(new java.util.Date());
            String item = monitorDecoder.describe(source, destination, control, pid, payload);
            String next = monitorLog.getText() + "\n[" + stamp + "] " + item + "\n";
            if (next.length() > 30000) next = next.substring(next.length() - 26000);
            monitorLog.setText(next);
            monitorPacketCount++;
            modeLabel.setText("受信専用モニター · " + monitorPacketCount + " packets");
            conversationScroll.post(() -> conversationScroll.fullScroll(View.FOCUS_DOWN));
        });
    }
    @Override public void onIpv4Packet(byte[] packet) {
        if (packet.length >= 28 && ((packet[0] & 255) >>> 4) == 4) {
            int header = (packet[0] & 15) * 4;
            if (packet[9] == 1 && header >= 20 && packet.length >= header + 8) {
                int type = packet[header] & 255;
                int sequence = ((packet[header + 6] & 255) << 8) | (packet[header + 7] & 255);
                if (type == 0) {
                    ArrayBlockingQueue<String> waiter = icmpWaiters.get(sequence);
                    if (waiter != null) waiter.offer(sourceAddress(packet));
                } else if (type == 11 && packet.length >= header + 8 + 28) {
                    int embedded = header + 8;
                    int embeddedHeader = (packet[embedded] & 15) * 4;
                    int sequenceOffset = embedded + embeddedHeader + 6;
                    if (embeddedHeader >= 20 && packet.length >= sequenceOffset + 2) {
                        int originalSequence = ((packet[sequenceOffset] & 255) << 8) | (packet[sequenceOffset + 1] & 255);
                        ArrayBlockingQueue<String> waiter = icmpWaiters.get(originalSequence);
                        if (waiter != null) waiter.offer(sourceAddress(packet));
                    }
                } else if (type == 8) append("ICMP Echo Request受信 from " + sourceAddress(packet) + " seq=" + sequence);
            }
        }
        AtomVpnService.receiveFromUsb(packet);
    }
    @Override protected void onDestroy() { reconnectHandler.removeCallbacks(reconnectPoll); commandExecutor.shutdownNow(); unregisterReceiver(receiver); usb.close(); stopService(new Intent(this, UsbConnectionService.class)); super.onDestroy(); }
}
