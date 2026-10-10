package jp.jn1eep.atomusbchat;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.zip.CRC32;

/** Formats CRC-valid AX.25 payloads and reassembles direct-chat RL fragments. */
final class MonitorPacketDecoder {
    private static final int MAX_ASSEMBLIES = 8;
    private static final long ASSEMBLY_LIFETIME_MS = 60000;
    private final LinkedHashMap<String, Assembly> assemblies = new LinkedHashMap<>();
    private final LinkedHashMap<String, Boolean> completed = new LinkedHashMap<>();

    String describe(String source, String destination, int control, int pid, byte[] payload) {
        StringBuilder result = new StringBuilder(String.format(Locale.ROOT,
                "%s > %s  CTRL=%02X PID=%02X LEN=%d  CRC OK", source, destination,
                control, pid, payload.length));
        if (pid == 0xf1) describeGroup(result, payload);
        else if (pid == 0xcf) describeReliable(result, source, payload);
        else if (pid == 0xf0) result.append("\n本文: ").append(new String(payload, StandardCharsets.UTF_8));
        else if (pid == 0xcc) appendIpv4(result, payload);
        result.append("\nHEX ");
        for (byte value : payload) result.append(String.format(Locale.ROOT, "%02X", value & 255));
        return result.toString();
    }

    private static void describeGroup(StringBuilder result, byte[] p) {
        if (p.length < 22 || p[0] != 'G' || p[1] != 'C' || p[2] != 1) return;
        int size = u16(p, 20);
        if (size != p.length - 22) return;
        long id = u32(p, 4);
        String from = new String(p, 8, 6, StandardCharsets.US_ASCII).trim();
        if (p[3] == 1) result.append("\nGROUP DATA #").append(id).append(" from ").append(from)
                .append("\n本文: ").append(new String(p, 22, size, StandardCharsets.UTF_8));
        else if (p[3] == 2 && size == 6) result.append("\nGROUP NACK #").append(id)
                .append(" for ").append(new String(p, 22, 6, StandardCharsets.US_ASCII).trim());
        else if (p[3] == 3 && size == 4) result.append("\nGROUP SUMMARY #").append(id)
                .append(" oldest=").append(u32(p, 22));
    }

    private void describeReliable(StringBuilder result, String source, byte[] p) {
        if (p.length < 15 || p[0] != 'R' || p[1] != 'L' || p[2] != 1) return;
        int id = u16(p, 4), index = p[6] & 255, count = p[7] & 255;
        int total = u16(p, 8), applicationPid = p[14] & 255;
        long checksum = u32(p, 10);
        if (p[3] == 2) {
            result.append(String.format(Locale.ROOT, "\nRELIABLE ACK #%d part %d/%d", id, index + 1, count));
            return;
        }
        if (p[3] != 1 || count < 1 || count > 24 || index >= count ||
                total < 1 || total > 1500 || p.length <= 15) return;
        result.append(String.format(Locale.ROOT, "\nRELIABLE DATA #%d part %d/%d app=%02X",
                id, index + 1, count, applicationPid));
        long now = System.currentTimeMillis();
        assemblies.entrySet().removeIf(entry -> now - entry.getValue().created > ASSEMBLY_LIFETIME_MS);
        String key = source + ":" + id + ":" + checksum;
        if (completed.containsKey(key)) { result.append(" (再送・受信済み)"); return; }
        Assembly assembly = assemblies.get(key);
        if (assembly == null || assembly.count != count || assembly.total != total || assembly.pid != applicationPid) {
            assembly = new Assembly(count, total, applicationPid, checksum, now);
            assemblies.put(key, assembly);
            if (assemblies.size() > MAX_ASSEMBLIES) assemblies.remove(assemblies.keySet().iterator().next());
        }
        int expected = index + 1 == count ? total - index * 64 : 64;
        if (expected <= 0 || p.length != 15 + expected) return;
        if (assembly.parts[index] == null) {
            assembly.parts[index] = java.util.Arrays.copyOfRange(p, 15, p.length);
            assembly.received++;
        }
        if (assembly.received != count) return;
        byte[] full = new byte[total];
        for (int i = 0; i < count; i++) {
            if (assembly.parts[i] == null) return;
            System.arraycopy(assembly.parts[i], 0, full, i * 64, assembly.parts[i].length);
        }
        CRC32 crc = new CRC32(); crc.update(full);
        if (crc.getValue() != checksum) { result.append("\n再構成CRC不一致"); assemblies.remove(key); return; }
        assemblies.remove(key);
        completed.put(key, Boolean.TRUE);
        if (completed.size() > 32) completed.remove(completed.keySet().iterator().next());
        if (applicationPid == 0xf0) result.append("\n再構成した本文: ")
                .append(new String(full, StandardCharsets.UTF_8));
        else if (applicationPid == 0xcc) appendIpv4(result, full);
        else result.append("\n再構成 ").append(total).append(" bytes");
    }

    private static void appendIpv4(StringBuilder result, byte[] p) {
        if (p.length < 20 || (p[0] & 0xf0) != 0x40) return;
        result.append(String.format(Locale.ROOT, "\nIPv4 %d.%d.%d.%d > %d.%d.%d.%d protocol=%d",
                p[12] & 255, p[13] & 255, p[14] & 255, p[15] & 255,
                p[16] & 255, p[17] & 255, p[18] & 255, p[19] & 255, p[9] & 255));
    }

    private static int u16(byte[] p, int at) { return (p[at] & 255) | ((p[at + 1] & 255) << 8); }
    private static long u32(byte[] p, int at) {
        return ((long) p[at] & 255) | (((long) p[at + 1] & 255) << 8) |
                (((long) p[at + 2] & 255) << 16) | (((long) p[at + 3] & 255) << 24);
    }
    private static final class Assembly {
        final int count, total, pid; final long crc, created; final byte[][] parts;
        int received;
        Assembly(int count, int total, int pid, long crc, long created) {
            this.count = count; this.total = total; this.pid = pid; this.crc = crc;
            this.created = created; this.parts = new byte[count][];
        }
    }
}
