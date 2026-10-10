"""Exercise a USB drop and recovery without requiring Wintun or an ATOM."""
import contextlib
import io
import queue
import sys
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wintun_bridge as bridge


class FakePort:
    def __init__(self, disconnect_flag=None):
        self.disconnect_flag = disconnect_flag
        self.incoming = queue.Queue()
        self.writes = []
        self.closed = False

    @property
    def in_waiting(self):
        return 0

    def read(self, _size):
        if self.disconnect_flag is not None and self.disconnect_flag.is_set():
            raise bridge.serial.SerialException("USB unplugged")
        try:
            return self.incoming.get(timeout=0.02)
        except queue.Empty:
            return b""

    def write(self, data):
        self.writes.append(bytes(data))
        if b"k " in data:
            self.incoming.put(b"GROUP TX OK\n")
        return len(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def close(self):
        self.closed = True


class FakeWintun:
    def __init__(self, *_args):
        self.index = 1

    def receive(self):
        return None

    def close(self):
        pass


class ReconnectTest(unittest.TestCase):
    def test_native_chat_survives_usb_disconnect_and_restores_group_mode(self):
        import threading
        unplug = threading.Event()
        allow_reconnect = threading.Event()
        first = FakePort(unplug)
        second = FakePort()
        second.incoming.put(b"BOOT DIAG reset_reason=1 name=POWERON uptime_ms=8\n")
        opens = []

        def open_port(*_args, **_kwargs):
            opens.append(1)
            if len(opens) == 1:
                return first
            if not allow_reconnect.is_set():
                raise bridge.serial.SerialException("COM6 not present")
            return second

        def wait_for(predicate, label):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if predicate():
                    return
                time.sleep(0.02)
            self.fail(f"timed out waiting for {label}")

        def fake_ui(chat, stop):
            chat.set_mode("group")
            wait_for(lambda: b"group on\n" in b"".join(first.writes), "initial group mode")
            unplug.set()
            wait_for(lambda: "再接続中" in chat.status, "disconnect status")
            allow_reconnect.set()
            wait_for(lambda: "接続済み" in chat.status, "reconnect status")
            self.assertIn(b"group on\n", b"".join(second.writes))
            chat.send("hello")
            wait_for(lambda: b"k " in b"".join(second.writes), "group send after reconnect")
            wait_for(lambda: second.incoming.empty(), "completion read")
            time.sleep(0.05)
            stop.set()

        args = types.SimpleNamespace(port="COM6", adapter="test", local_ip="10.77.0.1",
                                     remote_ip="10.77.0.2", queue_size=8, chat_http_port=0,
                                     stats_interval=0, chat_native=True, udp_port=7000,
                                     pass_all=False, turnaround=0)
        output = io.StringIO()
        with patch.object(bridge, "elevated", return_value=True), \
             patch.object(bridge, "Wintun", FakeWintun), \
             patch.object(bridge, "configure"), \
             patch.object(bridge, "capture_usb_snapshot") as snapshot, \
             patch.object(bridge.serial, "Serial", side_effect=open_port), \
             patch.object(bridge, "start_native_chat", side_effect=fake_ui), \
             contextlib.redirect_stdout(output):
            bridge.run(args)

        log = output.getvalue()
        self.assertIn("SERIAL DISCONNECTED", log)
        self.assertIn("SERIAL RECONNECTED", log)
        self.assertIn("GROUP TX OK", log)
        self.assertIn("SERIAL BOOT", log)
        self.assertIn("name=POWERON", log)
        self.assertEqual([call.args[1] for call in snapshot.call_args_list],
                         ["disconnect", "reconnect"])
        self.assertTrue(first.closed)
        self.assertTrue(second.closed)


if __name__ == "__main__":
    unittest.main()
