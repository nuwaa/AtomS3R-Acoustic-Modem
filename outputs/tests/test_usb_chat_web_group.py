import sys
import threading
import unittest
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from usb_chat_web import Bridge


class FakePort:
    port = "COM6"
    def __init__(self):
        self.writes = bytearray()
    def write(self, data):
        self.writes.extend(data)
    def flush(self):
        pass


class UsbChatGroupTest(unittest.TestCase):
    def bridge(self):
        bridge = Bridge.__new__(Bridge)
        bridge.lock = threading.Lock()
        bridge.write_lock = threading.Lock()
        bridge.port = FakePort()
        bridge.mode = "direct"
        bridge.bell = "off"
        bridge.bell_pending = False
        bridge.direct_queue = deque()
        bridge.direct_active = None
        bridge.status = "COM6 接続済み"
        bridge.events = []
        bridge.recent_lines = deque(maxlen=100)
        bridge.next_id = 1
        return bridge

    def test_mode_switch_preserves_direct_and_encodes_group_utf8(self):
        bridge = self.bridge()
        bridge.send("直接")
        self.assertIn(b"z " + "直接".encode().hex().encode() + b"\n", bridge.port.writes)
        bridge.handle_line("RELIABLE SENT ID=1 PART=1/1 PID=F0")
        bridge.set_mode("group")
        bridge.send("横浜市")
        self.assertTrue(bridge.port.writes.endswith(b"group on\nk " + "横浜市".encode().hex().encode() + b"\n"))
        with self.assertRaises(ValueError):
            bridge.send("漢" * 67)  # 201 UTF-8 bytes exceeds the acoustic DATA limit.
        bridge.set_mode("direct")
        self.assertTrue(bridge.port.writes.endswith(b"group off\n"))

    def test_group_rx_and_direct_rx_are_displayed(self):
        bridge = self.bridge()
        bridge.handle_line("USB_GROUP_RX SRC=ATOMA ID=42 HEX=" + "繁體中文".encode().hex().upper())
        bridge.handle_line("USB_RX SRC=ATOMA DEST=ATOMB PID=F0 HEX=" + "横浜市".encode().hex().upper())
        self.assertEqual([event["text"] for event in bridge.events], ["繁體中文", "横浜市"])
        self.assertIn("CHAT", bridge.events[0]["who"])
        bridge.handle_line("GROUP TX FAILED (use group on; length 1..198 bytes).")
        self.assertIn("GROUP TX FAILED", bridge.status)

    def test_receiver_diagnostics_use_single_byte_commands(self):
        bridge = self.bridge()
        bridge.send(" /rx-off ")
        bridge.send("/rx-on")
        self.assertEqual(bridge.port.writes, b"ql")
        bridge.handle_line("LIVE RX stopped: 0 valid frame(s).")
        bridge.handle_line("STATE RX LISTEN (q=stop, t <text>=TX).")
        self.assertEqual([item["who"] for item in bridge.events], ["診断", "診断", "ATOM", "ATOM"])

    def test_bell103_controls_utf8_data_and_returns_to_ax25(self):
        bridge = self.bridge()
        bridge.set_mode("group")
        bridge.bell_action("caller")
        self.assertIn(b"group off\nbell103 auto caller\n", bridge.port.writes)
        with self.assertRaises(ValueError):
            bridge.send("早すぎる")
        with self.assertRaises(ValueError):
            bridge.set_mode("group")
        bridge.handle_line("BELL103 AUTO RX CONTROL type=4 state=connected")
        self.assertEqual(bridge.bell, "接続済み")
        bridge.send("横浜市")
        self.assertTrue(bridge.port.writes.endswith(b"bell103 data send " + "横浜市".encode() + b"\n"))
        with self.assertRaises(ValueError):
            bridge.send("漢" * 24)
        bridge.handle_line("BELL103 AUTO ACK OK")
        self.assertFalse(bridge.bell_pending)
        bridge.handle_line("BELL103 AUTO RX TEXT len=9: 繁體中文")
        self.assertEqual(bridge.events[-1]["text"], "繁體中文")
        bridge.bell_action("stop")
        bridge.send("直接")
        self.assertTrue(bridge.port.writes.endswith(b"bell103 auto stop\nz " + "直接".encode().hex().encode() + b"\n"))


if __name__ == "__main__":
    unittest.main()
