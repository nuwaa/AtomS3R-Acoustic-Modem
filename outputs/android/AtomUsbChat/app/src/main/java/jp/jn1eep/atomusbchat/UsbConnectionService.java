package jp.jn1eep.atomusbchat;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

/** Keeps the USB chat reader process active while the screen is locked. */
public final class UsbConnectionService extends Service {
    private static final String CHANNEL = "atom_usb_connection";
    private static final int NOTIFICATION_ID = 103;
    private static final long WAKE_LOCK_TIMEOUT_MS = 10 * 60 * 1000L;
    private static final long WAKE_LOCK_RENEW_MS = 9 * 60 * 1000L;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private PowerManager.WakeLock wakeLock;
    private final Runnable renewWakeLock = new Runnable() {
        @Override public void run() {
            if (wakeLock == null) return;
            wakeLock.acquire(WAKE_LOCK_TIMEOUT_MS);
            handler.postDelayed(this, WAKE_LOCK_RENEW_MS);
        }
    };

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(CHANNEL, "ATOM USB通信", NotificationManager.IMPORTANCE_LOW));
        Intent open = new Intent(this, MainActivity.class).setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent openIntent = PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle("ATOM Chat")
                .setContentText("USB-Cで音響チャットを受信中")
                .setContentIntent(openIntent)
                .setOngoing(true)
                .build();
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
            else startForeground(NOTIFICATION_ID, notification);
            PowerManager powerManager = (PowerManager) getSystemService(POWER_SERVICE);
            wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "jp.jn1eep.atomusbchat:usb-reader");
            wakeLock.setReferenceCounted(false);
            renewWakeLock.run();
        } catch (RuntimeException error) {
            Log.e("AtomUsbChat", "Cannot keep USB reader in foreground", error);
            stopSelf();
        }
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) { return START_NOT_STICKY; }
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public void onDestroy() {
        handler.removeCallbacks(renewWakeLock);
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        wakeLock = null;
        super.onDestroy();
    }
}
