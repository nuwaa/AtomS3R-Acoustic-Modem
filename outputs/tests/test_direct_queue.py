"""Host-side direct chat must not submit a second message before ACK."""
import sys
import threading
import unittest
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from usb_chat_web import Bridge


class DirectQueueTest(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge.__new__(Bridge)
        self.bridge.lock = threading.Lock()
        self.bridge.recent_lines = deque(maxlen=100)
        self.bridge.events = []
        self.bridge.next_id = 1
        self.bridge.bell = "off"
        self.bridge.mode = "direct"
        self.bridge.direct_queue = deque()
        self.bridge.direct_active = None
        self.commands = []
        self.bridge.write_command = self.commands.append

    def test_serializes_and_reports_delivery(self):
        self.bridge.send("一")
        self.bridge.send("二")
        self.assertEqual(len(self.commands), 1)
        self.bridge.handle_line("RELIABLE SENT ID=1 PART=1/1 PID=F0")
        self.assertEqual(len(self.commands), 2)
        self.assertIn("送達", [event["who"] for event in self.bridge.events])
        self.bridge.handle_line("RELIABLE FAILED ID=2 PART=1/1 PID=F0")
        self.assertIsNone(self.bridge.direct_active)
        self.assertEqual(len(self.bridge.direct_queue), 0)
        self.assertEqual(self.bridge.events[-1]["who"], "送信失敗")

    def test_failure_cancels_later_messages(self):
        self.bridge.send("first")
        self.bridge.send("second")
        self.bridge.handle_line("RELIABLE FAILED ID=1 PART=1/1 PID=F0")
        self.assertEqual(len(self.commands), 1)
        self.assertEqual([event["who"] for event in self.bridge.events[-2:]], ["送信失敗", "未送信"])

    def test_ip_status_does_not_advance_chat(self):
        self.bridge.send("first")
        self.bridge.send("second")
        self.bridge.handle_line("RELIABLE SENT ID=3 PART=1/1 PID=CC")
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(len(self.bridge.direct_queue), 2)


if __name__ == "__main__":
    unittest.main()
