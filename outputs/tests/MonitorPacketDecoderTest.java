package jp.jn1eep.atomusbchat;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.zip.CRC32;

public final class MonitorPacketDecoderTest {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    private static byte[] group(String message) {
        byte[] text = message.getBytes(StandardCharsets.UTF_8);
        byte[] p = new byte[22 + text.length];
        p[0] = 'G'; p[1] = 'C'; p[2] = 1; p[3] = 1;
        p[4] = 42;
        System.arraycopy("ATOMA ".getBytes(StandardCharsets.US_ASCII), 0, p, 8, 6);
        System.arraycopy("CHAT  ".getBytes(StandardCharsets.US_ASCII), 0, p, 14, 6);
        p[20] = (byte) text.length; p[21] = (byte) (text.length >>> 8);
        System.arraycopy(text, 0, p, 22, text.length);
        return p;
    }
    private static byte[] reliable(byte[] text, int index, long crc) {
        int count = (text.length + 63) / 64;
        int offset = index * 64;
        int size = Math.min(64, text.length - offset);
        byte[] p = new byte[15 + size];
        p[0] = 'R'; p[1] = 'L'; p[2] = 1; p[3] = 1;
        p[4] = 17; p[6] = (byte) index; p[7] = (byte) count;
        p[8] = (byte) text.length; p[9] = (byte) (text.length >>> 8);
        for (int i = 0; i < 4; i++) p[10 + i] = (byte) (crc >>> (8 * i));
        p[14] = (byte) 0xf0;
        System.arraycopy(text, offset, p, 15, size);
        return p;
    }
    public static void main(String[] args) {
        MonitorPacketDecoder decoder = new MonitorPacketDecoder();
        String group = decoder.describe("ATOMA", "CHAT", 3, 0xf1, group("横浜市 グループ"));
        check(group.contains("CRC OK") && group.contains("GROUP DATA #42") &&
                group.contains("横浜市 グループ"), "group frame detail");
        String text = "直接チャットの分割を確認します。ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
        byte[] utf8 = text.getBytes(StandardCharsets.UTF_8);
        check(utf8.length > 64, "test must use two fragments");
        CRC32 crc = new CRC32(); crc.update(utf8);
        byte[] first = reliable(utf8, 0, crc.getValue());
        byte[] second = reliable(utf8, 1, crc.getValue());
        check(!decoder.describe("ATOMA", "ATOMB", 3, 0xcf, first).contains("再構成した本文"),
                "premature reassembly");
        check(decoder.describe("ATOMA", "ATOMB", 3, 0xcf, second).contains(text),
                "direct UTF-8 reassembly");
        check(decoder.describe("ATOMA", "ATOMB", 3, 0xcf, second).contains("再送・受信済み"),
                "duplicate retry label");
        byte[] invalid = Arrays.copyOf(second, second.length);
        invalid[15] ^= 1;
        MonitorPacketDecoder broken = new MonitorPacketDecoder();
        broken.describe("ATOMA", "ATOMB", 3, 0xcf, first);
        check(broken.describe("ATOMA", "ATOMB", 3, 0xcf, invalid).contains("再構成CRC不一致"),
                "reassembly CRC rejection");
        System.out.println("PASS: group UTF-8, fragmented direct UTF-8, duplicate, reassembly CRC");
    }
}
