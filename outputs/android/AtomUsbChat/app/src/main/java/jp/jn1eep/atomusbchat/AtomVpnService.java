package jp.jn1eep.atomusbchat;

import android.content.Intent;
import android.net.VpnService;
import android.os.ParcelFileDescriptor;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicBoolean;

public final class AtomVpnService extends VpnService {
    interface PacketSender { void send(byte[] packet); }
    private static volatile AtomVpnService active;
    private static volatile PacketSender usbSender;
    private ParcelFileDescriptor tunnel;
    private FileInputStream input;
    private FileOutputStream output;
    private Thread reader;
    private final AtomicBoolean running = new AtomicBoolean();

    static void attachUsb(PacketSender sender) { usbSender = sender; }
    static void receiveFromUsb(byte[] packet) {
        AtomVpnService service = active;
        if (service == null || service.output == null) return;
        try { synchronized (service.output) { service.output.write(packet); } }
        catch (IOException ignored) { }
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (tunnel == null) startTunnel();
        return START_STICKY;
    }

    private void startTunnel() {
        tunnel = new Builder().setSession("ATOM Acoustic IP")
                .setMtu(1500).addAddress("10.77.0.2", 32).addRoute("10.77.0.1", 32)
                .establish();
        if (tunnel == null) { stopSelf(); return; }
        input = new FileInputStream(tunnel.getFileDescriptor());
        output = new FileOutputStream(tunnel.getFileDescriptor());
        active = this;
        running.set(true);
        reader = new Thread(this::readLoop, "atom-vpn-reader");
        reader.start();
    }

    private void readLoop() {
        byte[] buffer = new byte[1500];
        while (running.get()) try {
            int length = input.read(buffer);
            if (length >= 20 && ((buffer[0] & 0xff) >>> 4) == 4) {
                byte[] packet = java.util.Arrays.copyOf(buffer, length);
                PacketSender sender = usbSender;
                if (sender != null) try { sender.send(packet); } catch (RuntimeException ignored) { }
            }
        } catch (IOException error) { break; }
    }

    @Override public void onDestroy() {
        running.set(false);
        if (reader != null) reader.interrupt();
        try { if (tunnel != null) tunnel.close(); } catch (IOException ignored) { }
        if (active == this) active = null;
        super.onDestroy();
    }
}
