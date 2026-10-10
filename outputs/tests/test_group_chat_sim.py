"""Meaningful failure cases for the proposed multi-node group chat."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from group_chat_sim import DATA, NACK, SUMMARY, Frame, Medium, demonstration


class GroupChatSimulationTests(unittest.TestCase):
    def test_wire_format_matches_reserved_22_byte_header(self):
        frame = Frame(DATA, 0x12345678, "ATOMA", "CHAT", "横浜市".encode())
        wire = frame.encode()
        self.assertEqual(len(wire), 22 + len(frame.payload))
        self.assertEqual(wire[:8], bytes.fromhex("4743010178563412"))
        self.assertEqual(Frame.decode(wire), frame)
        nack = Frame(NACK, frame.message_id, "ATOMC", "CHAT", b"ATOMA ")
        self.assertEqual(Frame.decode(nack.encode()).missing_source, "ATOMA")
        summary = Frame(SUMMARY, 101, "ATOMA", "CHAT", (100).to_bytes(4, "little"))
        self.assertEqual(Frame.decode(summary.encode()).first_retained_id, 100)
        with self.assertRaises(ValueError):
            Frame.decode(wire[:-1])

    def test_three_nodes_recover_missing_kanji_message_in_order(self):
        log = demonstration()
        self.assertTrue(any(event[1] == "DROP" for event in log))
        self.assertTrue(any(event[1] == "TX" and event[3] == NACK for event in log))
        self.assertTrue(any(event[1] == "TX" and event[2] == "ATOMA" and event[4] == 101
                            for event in log))

    def test_four_nodes_suppress_duplicate_nacks_and_duplicate_data(self):
        medium = Medium(seed=3)
        nodes = {name: medium.add(name) for name in ("ATOMA", "ATOMB", "ATOMC", "ATOMD")}
        a = nodes["ATOMA"]
        a.send("first")
        missing = a.send("missing", delay=3)
        a.send("after", delay=5)
        for recipient in ("ATOMC", "ATOMD"):
            medium.drop_once.add(("ATOMA", recipient, DATA, missing))
        medium.run()
        for name in ("ATOMB", "ATOMC", "ATOMD"):
            self.assertEqual([text for _, _, text in nodes[name].delivered],
                             ["first", "missing", "after"])
        self.assertTrue(any(event[1] == "NACK_SUPPRESSED" for event in medium.log))

    def test_simultaneous_transmissions_collide_then_back_off(self):
        medium = Medium(seed=19)
        a, b, c = (medium.add(name) for name in ("ATOMA", "ATOMB", "ATOMC"))
        a.send("A message", delay=1)
        b.send("B message", delay=1)
        medium.run()
        self.assertTrue(any(event[1] == "COLLISION" for event in medium.log))
        self.assertEqual({source for source, _, _ in c.delivered}, {"ATOMA", "ATOMB"})
        self.assertEqual(len(c.delivered), 2)

    def test_nack_names_original_sender_when_ids_overlap(self):
        medium = Medium(seed=5)
        a = medium.add("ATOMA", first_id=100)
        b = medium.add("ATOMB", first_id=100)
        c = medium.add("ATOMC")
        a.send("a100")
        b.send("b100", delay=2)
        missing = a.send("a101", delay=4)
        medium.drop_once.add(("ATOMA", "ATOMC", DATA, missing))
        a.send("a102", delay=6)
        medium.run()
        self.assertEqual([text for source, _, text in c.delivered if source == "ATOMA"],
                         ["a100", "a101", "a102"])
        self.assertEqual([text for source, _, text in c.delivered if source == "ATOMB"], ["b100"])

    def test_different_group_is_ignored(self):
        medium = Medium()
        a = medium.add("ATOMA", group="CHAT")
        b = medium.add("ATOMB", group="OTHER")
        a.send("private group")
        medium.run()
        self.assertEqual(b.delivered, [])

    def test_first_and_only_lost_message_recovers_from_summary(self):
        medium = Medium()
        a = medium.add("ATOMA")
        c = medium.add("ATOMC")
        missing = a.send("first message")
        medium.drop_once.add(("ATOMA", "ATOMC", DATA, missing))
        medium.run()
        self.assertEqual(c.delivered, [("ATOMA", missing, "first message")])
        self.assertTrue(any(event[1] == "TX" and event[3] == SUMMARY for event in medium.log))
        self.assertTrue(any(event[1] == "TX" and event[3] == NACK for event in medium.log))

    def test_second_summary_recovers_when_first_summary_is_lost(self):
        medium = Medium(seed=9)
        a = medium.add("ATOMA")
        c = medium.add("ATOMC")
        missing = a.send("横浜市")
        medium.drop_once.add(("ATOMA", "ATOMC", DATA, missing))
        medium.drop_once.add(("ATOMA", "ATOMC", SUMMARY, missing))
        medium.run()
        self.assertEqual(c.delivered, [("ATOMA", missing, "横浜市")])

    def test_summary_recovers_first_message_after_later_data_arrives(self):
        medium = Medium(seed=11)
        a = medium.add("ATOMA")
        c = medium.add("ATOMC")
        first = a.send("first")
        second = a.send("second", delay=3)
        medium.drop_once.add(("ATOMA", "ATOMC", DATA, first))
        medium.run()
        self.assertEqual({mid for _, mid, _ in c.delivered}, {first, second})
        self.assertEqual(len(c.delivered), 2)


if __name__ == "__main__":
    unittest.main()
