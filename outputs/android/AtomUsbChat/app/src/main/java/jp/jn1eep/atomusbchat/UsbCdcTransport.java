package jp.jn1eep.atomusbchat;

import android.app.PendingIntent;
import android.content.*;
import android.hardware.usb.*;
import android.util.Log;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.ArrayDeque;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class UsbCdcTransport {
    interface Listener { void onStatus(String text); void onMessage(String source,String destination,String text); void onGroupMessage(String source,String text); void onBell103Message(String text); void onIpv4Packet(byte[] packet); void onMonitorPacket(String source,String destination,int control,int pid,byte[] payload); }
    static final String ACTION_PERMISSION="jp.jn1eep.atomusbchat.USB_PERMISSION";
    private final Context context;private final UsbManager manager;private final Listener listener;private UsbDeviceConnection connection;private UsbInterface dataInterface;private UsbEndpoint input,output;private Thread reader;private String connectedDeviceName;private final AtomicBoolean running=new AtomicBoolean();private volatile boolean bellMode;
    private final ExecutorService writer=Executors.newSingleThreadExecutor(task->{Thread thread=new Thread(task,"atom-usb-writer");thread.setDaemon(true);return thread;});
    private static final Pattern DIRECT_STATUS=Pattern.compile("^RELIABLE (START|SENT|FAILED|BUSY_OR_INVALID)\\b.*PID=F0\\b");
    private final ArrayDeque<byte[]> directQueue=new ArrayDeque<>();
    private boolean directActive;
    private static final Pattern GROUP_RX=Pattern.compile("^USB_GROUP_RX SRC=([A-Z0-9]{1,6}) ID=(\\d+) HEX=([0-9A-Fa-f]+)$");
    private static final Pattern MONITOR_RX=Pattern.compile("^USB_MON_RX SRC=([A-Z0-9-]{1,9}) DEST=([A-Z0-9-]{1,9}) CTRL=([0-9A-Fa-f]{2}) PID=([0-9A-Fa-f]{2}) LEN=(\\d+) HEX=([0-9A-Fa-f]*)$");
    private static final Pattern INBOX_RX=Pattern.compile("^USB_INBOX SESSION=([0-9A-Fa-f]{8}) SEQ=(\\d+) SRC=([A-Z0-9]{1,6}) DEST=([A-Z0-9]{1,6}) PID=([0-9A-Fa-f]{2}) HEX=([0-9A-Fa-f]+)$");
    private final InboxStore inboxStore;
    private volatile boolean inboxReady;
    UsbCdcTransport(Context context,Listener listener){this.context=context;this.listener=listener;manager=(UsbManager)context.getSystemService(Context.USB_SERVICE);inboxStore=new InboxStore(context);}
    java.util.List<InboxStore.Item> savedInbox(){return inboxStore.history();}
    void requestInbox(){if(inboxReady&&running.get()&&!bellMode)sendRaw("inbox pull\n".getBytes(StandardCharsets.US_ASCII));}
    private static final int ESPRESSIF_VENDOR_ID=0x303a;
    UsbDevice find(){
        UsbDevice fallback=null;
        for(UsbDevice device:manager.getDeviceList().values()){
            for(int i=0;i<device.getInterfaceCount();i++){
                UsbInterface face=device.getInterface(i);
                if(!hasBulkPair(face))continue;
                if(face.getInterfaceClass()==UsbConstants.USB_CLASS_CDC_DATA)return device;
                if(device.getVendorId()==ESPRESSIF_VENDOR_ID)fallback=device;
            }
        }
        return fallback;
    }
    String describeDevices(){
        if(manager.getDeviceList().isEmpty())return "USB機器が見つかりません（OTG・ケーブル・給電を確認）";
        StringBuilder text=new StringBuilder("対応USBなし ");
        for(UsbDevice device:manager.getDeviceList().values()){
            text.append(String.format(Locale.ROOT,"VID=%04X PID=%04X ",device.getVendorId(),device.getProductId()));
            for(int i=0;i<device.getInterfaceCount();i++){
                UsbInterface face=device.getInterface(i);
                text.append(String.format(Locale.ROOT,"IF%d=%02X/%02X/%02X EP%d ",face.getId(),face.getInterfaceClass(),face.getInterfaceSubclass(),face.getInterfaceProtocol(),face.getEndpointCount()));
            }
        }
        return text.toString().trim();
    }
    private static boolean hasBulkPair(UsbInterface face){
        boolean in=false,out=false;
        for(int k=0;k<face.getEndpointCount();k++){
            UsbEndpoint endpoint=face.getEndpoint(k);
            if(endpoint.getType()!=UsbConstants.USB_ENDPOINT_XFER_BULK)continue;
            if(endpoint.getDirection()==UsbConstants.USB_DIR_IN)in=true;else out=true;
        }
        return in&&out;
    }
    boolean hasPermission(UsbDevice device){return manager.hasPermission(device);}
    synchronized boolean isConnected(){return running.get()&&connection!=null&&connectedDeviceName!=null&&manager.getDeviceList().containsKey(connectedDeviceName);}
    void request(UsbDevice device){PendingIntent intent=PendingIntent.getBroadcast(context,0,new Intent(ACTION_PERMISSION).setPackage(context.getPackageName()),PendingIntent.FLAG_IMMUTABLE);manager.requestPermission(device,intent);}
    synchronized boolean connect(UsbDevice device){close();UsbInterface found=null;UsbEndpoint in=null,out=null;for(int pass=0;pass<2&&found==null;pass++)for(int i=0;i<device.getInterfaceCount();i++){UsbInterface face=device.getInterface(i);boolean standard=face.getInterfaceClass()==UsbConstants.USB_CLASS_CDC_DATA;boolean espressif=device.getVendorId()==ESPRESSIF_VENDOR_ID;if((pass==0&&!standard)||(pass==1&&(!espressif||standard)))continue;UsbEndpoint candidateIn=null,candidateOut=null;for(int k=0;k<face.getEndpointCount();k++){UsbEndpoint endpoint=face.getEndpoint(k);if(endpoint.getType()!=UsbConstants.USB_ENDPOINT_XFER_BULK)continue;if(endpoint.getDirection()==UsbConstants.USB_DIR_IN)candidateIn=endpoint;else candidateOut=endpoint;}if(candidateIn!=null&&candidateOut!=null){found=face;in=candidateIn;out=candidateOut;break;}}
        UsbDeviceConnection opened=manager.openDevice(device);if(opened==null||found==null||!opened.claimInterface(found,true)){if(opened!=null)opened.close();listener.onStatus("USB CDC接続失敗: "+describeDevices());return false;}connection=opened;dataInterface=found;input=in;output=out;connectedDeviceName=device.getDeviceName();running.set(true);inboxReady=false;bellMode=false;reader=new Thread(this::readLoop,"atom-usb-reader");reader.start();listener.onStatus(String.format(Locale.ROOT,"USB-C接続済み VID=%04X PID=%04X IF=%d",device.getVendorId(),device.getProductId(),found.getId()));sendRaw("inbox on\n".getBytes(StandardCharsets.US_ASCII));return true;}
    synchronized void send(String text){byte[] utf8=text.getBytes(StandardCharsets.UTF_8);if(utf8.length<1||utf8.length>1500)throw new IllegalArgumentException("1..1500 UTF-8 bytes");if(!running.get())throw new IllegalStateException("USB未接続");if(directQueue.size()>=16)throw new IllegalStateException("直接チャットの送信待ちは16件までです");directQueue.addLast(utf8);startNextDirect();}
    private synchronized void startNextDirect(){if(directActive||directQueue.isEmpty())return;directActive=true;sendCommand('z',directQueue.peekFirst());}
    private synchronized void completeDirect(String result){if(directQueue.isEmpty())return;directQueue.removeFirst();directActive=false;if(!result.equals("SENT")){int cancelled=directQueue.size();directQueue.clear();listener.onStatus("AX25 DIRECT "+result+" cancelled="+cancelled);return;}listener.onStatus("AX25 DIRECT SENT remaining="+directQueue.size());startNextDirect();}
    synchronized boolean hasDirectPending(){return !directQueue.isEmpty();}
    void sendGroup(String text){byte[] utf8=text.getBytes(StandardCharsets.UTF_8);if(utf8.length<1||utf8.length>198)throw new IllegalArgumentException("グループ本文は1..198 UTF-8 bytes");sendCommand('k',utf8);}
    void startBell103(boolean caller){sendRaw("group off\n".getBytes(StandardCharsets.US_ASCII));bellMode=true;sendRaw(("bell103 auto "+(caller?"caller":"answerer")+"\n").getBytes(StandardCharsets.US_ASCII));}
    void stopBell103(){sendRaw("bell103 auto stop\n".getBytes(StandardCharsets.US_ASCII));bellMode=false;requestInbox();}
    void sendBell103(String text){byte[] utf8=text.getBytes(StandardCharsets.UTF_8);if(utf8.length<1||utf8.length>70||text.indexOf('\n')>=0||text.indexOf('\r')>=0)throw new IllegalArgumentException("Bell 103本文は改行なしのUTF-8で1..70バイト");sendRaw(("bell103 data send "+text+"\n").getBytes(StandardCharsets.UTF_8));}
    void requestAudioSettings(){sendRaw("audio show\n".getBytes(StandardCharsets.US_ASCII));}
    void setSpeakerVolume(int percent){if(percent<0||percent>100)throw new IllegalArgumentException("音量は0～100%です");sendRaw(("audio volume "+percent+"\n").getBytes(StandardCharsets.US_ASCII));}
    void setMicrophoneGain(int gainDb){if(gainDb<0||gainDb>42||gainDb%6!=0)throw new IllegalArgumentException("マイクゲインは0～42 dBの6 dB刻みです");sendRaw(("audio gain "+gainDb+"\n").getBytes(StandardCharsets.US_ASCII));}
    void setAcousticReceiverEnabled(boolean enabled){sendRaw(new byte[]{(byte)(enabled?'l':'q')});}
    void setGroupMode(boolean enabled){sendRaw(("group "+(enabled?"on":"off")+"\n").getBytes(StandardCharsets.US_ASCII));}
    void setMonitorMode(boolean enabled){sendRaw(("monitor "+(enabled?"on":"off")+"\n").getBytes(StandardCharsets.US_ASCII));}
    void sendIpv4(byte[] packet){if(packet.length<20||packet.length>1500||((packet[0]&0xff)>>>4)!=4)return;sendCommand('y',packet);}
    private void sendCommand(char commandName,byte[] payload){StringBuilder hex=new StringBuilder(payload.length*2);for(byte value:payload)hex.append(String.format(Locale.ROOT,"%02x",value&255));sendRaw((commandName+" "+hex+"\n").getBytes(StandardCharsets.US_ASCII));}
    private void sendRaw(byte[] command){if(!running.get())throw new IllegalStateException("USB未接続");writer.execute(()->{for(int pos=0;pos<command.length&&running.get();pos+=32){int n=Math.min(32,command.length-pos);UsbDeviceConnection active=connection;UsbEndpoint endpoint=output;if(active==null||endpoint==null||active.bulkTransfer(endpoint,command,pos,n,2000)<0){listener.onStatus("USB送信失敗");return;}try{Thread.sleep(10);}catch(InterruptedException ignored){Thread.currentThread().interrupt();return;}}});}
    private void readLoop(){byte[] block=new byte[512];ByteArrayOutputStream line=new ByteArrayOutputStream();while(running.get()){int n=connection.bulkTransfer(input,block,block.length,250);if(n<0)continue;for(int i=0;i<n;i++){int value=block[i]&255;if(value=='\n'){parse(line.toString(StandardCharsets.UTF_8));line.reset();}else if(value!='\r'&&line.size()<4096)line.write(value);}}}
    private boolean parseInboxLine(String line){
        if(line.startsWith("USB_INBOX READY ")){inboxReady=true;requestInbox();return true;}
        Matcher inbox=INBOX_RX.matcher(line);
        if(!inbox.matches())return false;
        try {
            String key=inbox.group(1)+":"+inbox.group(2);
            byte[] payload=java.util.HexFormat.of().parseHex(inbox.group(6));
            boolean group=inbox.group(5).equalsIgnoreCase("F1");
            if(!group&&!inbox.group(5).equalsIgnoreCase("F0"))return true;
            String text=new String(payload,StandardCharsets.UTF_8);
            InboxStore.Result saved=inboxStore.save(key,inbox.group(3),text,group);
            if(saved==InboxStore.Result.FAILED){listener.onStatus("USB受信履歴の保存に失敗しました");return true;}
            Log.i("AtomUsbChat","USB_INBOX "+saved+" key="+key+" bytes="+payload.length);
            if(saved==InboxStore.Result.NEW){
                if(group)listener.onGroupMessage(inbox.group(3),text);
                else listener.onMessage(inbox.group(3),inbox.group(4),text);
            }
            if(!bellMode)sendRaw(("inbox ack "+inbox.group(1)+" "+inbox.group(2)+"\n").getBytes(StandardCharsets.US_ASCII));
        } catch(IllegalArgumentException error){listener.onStatus("USB受信履歴の形式が不正です");}
        return true;
    }
    private void parse(String line){if(parseInboxLine(line))return;if(line.startsWith("AUDIO CONFIG ")||line.startsWith("ERROR: audio ")){listener.onStatus(line);return;}if(line.startsWith("BELL103 SESSION STOP")||line.startsWith("BELL103 AUTO CONNECT TIMEOUT")){bellMode=false;requestInbox();}if(line.startsWith("USB_RX "))Log.i("AtomUsbChat", "USB_RX line received bytes="+line.length());Matcher directStatus=DIRECT_STATUS.matcher(line);if(directStatus.find()){String state=directStatus.group(1);if(!state.equals("START"))completeDirect(state);return;}if(line.startsWith("BELL103 AUTO RX TEXT ")){int colon=line.indexOf(": ");if(colon>=0)listener.onBell103Message(line.substring(colon+2));return;}if(line.startsWith("BELL103 AUTO RX CONTROL")||line.startsWith("BELL103 SESSION STOP")||line.startsWith("BELL103 AUTO CONNECT TIMEOUT")||line.startsWith("BELL103 AUTO ACK OK")||line.startsWith("BELL103 AUTO DATA RETRIES EXHAUSTED")||line.startsWith("BELL103 DATA QUEUE FAILED")||line.startsWith("ERROR: Bell 103")){listener.onStatus(line);return;}if(line.startsWith("GROUP TX FAILED")||line.startsWith("LIVE RX stopped")||line.startsWith("STATE RX LISTEN")||line.startsWith("MONITOR MODE=")){listener.onStatus(line);return;}Matcher monitor=MONITOR_RX.matcher(line);if(monitor.matches()){try{byte[] bytes=java.util.HexFormat.of().parseHex(monitor.group(6));if(bytes.length==Integer.parseInt(monitor.group(5)))listener.onMonitorPacket(monitor.group(1),monitor.group(2),Integer.parseInt(monitor.group(3),16),Integer.parseInt(monitor.group(4),16),bytes);}catch(IllegalArgumentException ignored){}return;}Matcher group=GROUP_RX.matcher(line);if(group.matches()){try{byte[] bytes=java.util.HexFormat.of().parseHex(group.group(3));listener.onGroupMessage(group.group(1),new String(bytes,StandardCharsets.UTF_8));}catch(IllegalArgumentException ignored){}return;}if(!line.startsWith("USB_RX "))return;int src=line.indexOf("SRC="),dst=line.indexOf(" DEST="),pid=line.indexOf(" PID="),hex=line.indexOf(" HEX=");if(src<0||dst<0||pid<0||hex<0)return;String pidValue=line.substring(pid+5,hex);try{byte[] bytes=java.util.HexFormat.of().parseHex(line.substring(hex+5));if(pidValue.equalsIgnoreCase("F0"))listener.onMessage(line.substring(src+4,dst),line.substring(dst+6,pid),new String(bytes,StandardCharsets.UTF_8));else if(pidValue.equalsIgnoreCase("CC"))listener.onIpv4Packet(bytes);}catch(IllegalArgumentException ignored){}}
    synchronized void close(){running.set(false);inboxReady=false;bellMode=false;int abandoned=directQueue.size();directQueue.clear();directActive=false;if(abandoned>0)listener.onStatus("AX25 DIRECT USB_DISCONNECTED cancelled="+abandoned);if(reader!=null)reader.interrupt();if(connection!=null){if(dataInterface!=null)connection.releaseInterface(dataInterface);connection.close();}reader=null;connection=null;connectedDeviceName=null;dataInterface=null;input=null;output=null;}
}
