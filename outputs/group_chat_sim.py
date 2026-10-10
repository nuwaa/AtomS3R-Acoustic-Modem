"""Deterministic multi-node acoustic-chat prototype; no hardware is opened.

The 22-byte envelope matches GroupChatProtocol.h. One simulated time slot
holds one complete AX.25 transmission. Simultaneous transmissions collide.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import heapq
import json
import random
import struct
from collections import deque

HEADER = struct.Struct("<2sBBI6s6sH")
MAX_TEXT = 198
DATA, NACK, SUMMARY = 1, 2, 3


def _name(value: str) -> bytes:
    if not 1 <= len(value) <= 6 or not value.isascii() or not value.isalnum():
        raise ValueError("node and group names must be 1..6 ASCII letters/digits")
    return value.encode("ascii").ljust(6, b" ")


@dataclass(frozen=True)
class Frame:
    kind: int
    message_id: int
    source: str
    group: str
    payload: bytes

    def encode(self) -> bytes:
        if not 0 <= self.message_id <= 0xFFFFFFFF:
            raise ValueError("message ID out of range")
        if self.kind == DATA and not 1 <= len(self.payload) <= MAX_TEXT:
            raise ValueError("DATA must carry 1..198 bytes")
        if self.kind == NACK and (len(self.payload) != 6 or not self.payload.rstrip(b" ").isalnum()):
            raise ValueError("NACK must identify the missing source in six bytes")
        if self.kind == SUMMARY and (len(self.payload) != 4 or
                                     struct.unpack("<I", self.payload)[0] > self.message_id):
            raise ValueError("SUMMARY must carry the first retained message ID")
        if self.kind not in (DATA, NACK, SUMMARY):
            raise ValueError("unknown frame type")
        return HEADER.pack(b"GC", 1, self.kind, self.message_id,
                           _name(self.source), _name(self.group), len(self.payload)) + self.payload

    @classmethod
    def decode(cls, wire: bytes) -> Frame:
        if len(wire) < HEADER.size:
            raise ValueError("short frame")
        magic, version, kind, mid, source, group, size = HEADER.unpack_from(wire)
        if magic != b"GC" or version != 1 or len(wire) != HEADER.size + size:
            raise ValueError("invalid envelope")
        frame = cls(kind, mid, source.rstrip(b" ").decode("ascii"),
                    group.rstrip(b" ").decode("ascii"), wire[HEADER.size:])
        frame.encode()  # Validate type, length and names before delivery.
        return frame

    @property
    def missing_source(self) -> str:
        if self.kind != NACK:
            raise ValueError("not a NACK")
        return self.payload.rstrip(b" ").decode("ascii")

    @property
    def first_retained_id(self) -> int:
        if self.kind != SUMMARY:
            raise ValueError("not a SUMMARY")
        return struct.unpack("<I", self.payload)[0]


@dataclass
class Attempt:
    node: Node
    frame: Frame
    retry: int = 0
    token: object | None = None
    retransmission: bool = False

    def active(self) -> bool:
        if self.frame.kind != NACK:
            return True
        key = (self.frame.missing_source, self.frame.message_id)
        return self.node.pending_nacks.get(key) is self.token


class Medium:
    def __init__(self, seed: int = 1):
        self.rng = random.Random(seed)
        self.nodes: dict[str, Node] = {}
        self.now = 0
        self.events: list[tuple[int, int, Attempt]] = []
        self.serial = 0
        self.drop_once: set[tuple[str, str, int, int]] = set()
        self.log: list[tuple] = []

    def add(self, name: str, group: str = "CHAT", first_id: int = 100) -> Node:
        node = Node(name, group, first_id, self)
        self.nodes[name] = node
        return node

    def schedule(self, delay: int, attempt: Attempt) -> None:
        self.serial += 1
        heapq.heappush(self.events, (self.now + delay, self.serial, attempt))

    def run(self, max_slot: int = 500) -> None:
        while self.events:
            slot = self.events[0][0]
            if slot > max_slot:
                raise TimeoutError("simulation did not quiesce")
            self.now = slot
            ready = []
            while self.events and self.events[0][0] == slot:
                attempt = heapq.heappop(self.events)[2]
                if attempt.active():
                    ready.append(attempt)
            if len(ready) > 1:
                self.log.append((slot, "COLLISION", tuple(a.node.name for a in ready)))
                for attempt in ready:
                    if attempt.retry < 4:
                        attempt.retry += 1
                        self.schedule(self.rng.randint(1, 2 ** (attempt.retry + 2)), attempt)
                continue
            if not ready:
                continue
            attempt = ready[0]
            frame = Frame.decode(attempt.frame.encode())
            self.log.append((slot, "TX", attempt.node.name, frame.kind, frame.message_id))
            attempt.node.after_transmit(attempt)
            for receiver in self.nodes.values():
                if receiver is attempt.node:
                    continue
                drop_key = (attempt.node.name, receiver.name, frame.kind, frame.message_id)
                if drop_key in self.drop_once:
                    self.drop_once.remove(drop_key)
                    self.log.append((slot, "DROP", receiver.name, frame.message_id))
                    continue
                receiver.receive(frame)


@dataclass
class Node:
    name: str
    group: str
    next_id: int
    medium: Medium
    expected: dict[str, int] = field(default_factory=dict)
    buffered: dict[str, dict[int, bytes]] = field(default_factory=dict)
    delivered: list[tuple[str, int, str]] = field(default_factory=list)
    delivered_ids: dict[str, set[int]] = field(default_factory=dict)
    early_missing: set[tuple[str, int]] = field(default_factory=set)
    history: dict[int, Frame] = field(default_factory=dict)
    history_order: deque[int] = field(default_factory=deque)
    pending_nacks: dict[tuple[str, int], object] = field(default_factory=dict)
    nack_retries: dict[tuple[str, int], int] = field(default_factory=dict)
    retrans_pending: set[int] = field(default_factory=set)

    def send(self, text: str, delay: int = 1) -> int:
        payload = text.encode("utf-8")
        mid = self.next_id
        self.next_id = (mid + 1) & 0xFFFFFFFF or 1
        frame = Frame(DATA, mid, self.name, self.group, payload)
        frame.encode()
        self.history[mid] = frame
        self.history_order.append(mid)
        if len(self.history_order) > 32:
            self.history.pop(self.history_order.popleft(), None)
        self.medium.schedule(delay, Attempt(self, frame))
        summary = Frame(SUMMARY, mid, self.name, self.group,
                        struct.pack("<I", self.history_order[0]))
        self.medium.schedule(delay + 8, Attempt(self, summary))
        self.medium.schedule(delay + 28, Attempt(self, summary))
        return mid

    def receive(self, frame: Frame) -> None:
        if frame.group != self.group or frame.source == self.name:
            return
        if frame.kind == NACK:
            self._receive_nack(frame)
        elif frame.kind == SUMMARY:
            self._receive_summary(frame)
        else:
            self._receive_data(frame)

    def _receive_summary(self, frame: Frame) -> None:
        source, first, latest = frame.source, frame.first_retained_id, frame.message_id
        if source not in self.expected:
            self.expected[source] = first
        expected = self.expected[source]
        # A later DATA may have arrived before the first SUMMARY. Recover
        # earlier IDs even though that DATA was already displayed.
        if first < expected:
            seen = self.delivered_ids.get(source, set())
            for missing in range(first, min(expected, first + 32)):
                if missing not in seen and missing not in self.buffered.get(source, {}):
                    self.early_missing.add((source, missing))
                    self._arm_nack((source, missing))
        if expected < first:
            # Sender no longer has older DATA in its bounded retransmit cache.
            self.expected[source] = first
            expected = first
        if latest < expected:
            return
        buffer = self.buffered.get(source, {})
        for missing in range(expected, min(latest + 1, expected + 8)):
            if missing not in buffer:
                self._arm_nack((source, missing))

    def _receive_data(self, frame: Frame) -> None:
        source, mid = frame.source, frame.message_id
        if source not in self.expected:
            self.expected[source] = mid
        expected = self.expected[source]
        if (source, mid) in self.early_missing:
            self.early_missing.remove((source, mid))
            self.pending_nacks.pop((source, mid), None)
            self.nack_retries.pop((source, mid), None)
            self.delivered_ids.setdefault(source, set()).add(mid)
            self.delivered.append((source, mid, frame.payload.decode("utf-8")))
            return
        if mid < expected or mid in self.buffered.get(source, {}):
            return
        if mid > expected + 8:
            # A reboot or a large gap cannot be repaired from the short cache.
            self.expected[source] = mid
            expected = mid
        self.buffered.setdefault(source, {})[mid] = frame.payload
        if mid > expected:
            for missing in range(expected, mid):
                if missing not in self.buffered[source]:
                    self._arm_nack((source, missing))
        self._drain(source)

    def _drain(self, source: str) -> None:
        buffer = self.buffered[source]
        while self.expected[source] in buffer:
            mid = self.expected[source]
            payload = buffer.pop(mid)
            self.pending_nacks.pop((source, mid), None)
            self.nack_retries.pop((source, mid), None)
            self.delivered.append((source, mid, payload.decode("utf-8")))
            self.delivered_ids.setdefault(source, set()).add(mid)
            self.expected[source] = (mid + 1) & 0xFFFFFFFF or 1

    def _arm_nack(self, key: tuple[str, int], base_delay: int = 1) -> None:
        if key in self.pending_nacks or self.nack_retries.get(key, 0) >= 3:
            return
        token = object()
        self.pending_nacks[key] = token
        frame = Frame(NACK, key[1], self.name, self.group, _name(key[0]))
        self.medium.schedule(base_delay + self.medium.rng.randrange(4), Attempt(self, frame, token=token))

    def _receive_nack(self, frame: Frame) -> None:
        key = (frame.missing_source, frame.message_id)
        if key in self.pending_nacks:
            self.pending_nacks.pop(key)  # Another receiver already requested it.
            self.medium.log.append((self.medium.now, "NACK_SUPPRESSED", self.name, key))
            self._arm_nack(key, base_delay=8)  # Retry only if the rebroadcast never arrives.
        if frame.missing_source == self.name and frame.message_id in self.history:
            if frame.message_id not in self.retrans_pending:
                self.retrans_pending.add(frame.message_id)
                self.medium.schedule(1 + self.medium.rng.randrange(3),
                                     Attempt(self, self.history[frame.message_id], retransmission=True))

    def after_transmit(self, attempt: Attempt) -> None:
        if attempt.retransmission:
            self.retrans_pending.discard(attempt.frame.message_id)
        if attempt.frame.kind == NACK:
            key = (attempt.frame.missing_source, attempt.frame.message_id)
            self.pending_nacks.pop(key, None)
            self.nack_retries[key] = self.nack_retries.get(key, 0) + 1
            if self.nack_retries[key] < 3:
                self._arm_nack(key, base_delay=8)


def demonstration() -> list[tuple]:
    medium = Medium(seed=7)
    a, b, c = (medium.add(name) for name in ("ATOMA", "ATOMB", "ATOMC"))
    a.send("横浜市")
    missing = a.send("繁體中文", delay=3)
    medium.drop_once.add(("ATOMA", "ATOMC", DATA, missing))
    a.send("三台目", delay=5)
    medium.run()
    assert [text for _, _, text in c.delivered] == ["横浜市", "繁體中文", "三台目"]
    assert len(b.delivered) == 3
    return medium.log


def stress(seeds: int = 100) -> dict:
    results = {}
    for count in (3, 4, 6, 8):
        failures = []
        collisions = 0
        for scenario in ("middle_data_lost", "first_data_and_first_summary_lost"):
            for seed in range(seeds):
                medium = Medium(seed)
                nodes = [medium.add(f"N{i}") for i in range(count)]
                sender = nodes[0]
                if scenario == "middle_data_lost":
                    sender.send("start")
                    missing = sender.send("lost", delay=3)
                    sender.send("last", delay=5)
                    expected = ["start", "lost", "last"]
                    recipients = nodes[2:]
                else:
                    missing = sender.send("only")
                    expected = ["only"]
                    recipients = nodes[1:]
                for receiver in recipients:
                    medium.drop_once.add((sender.name, receiver.name, DATA, missing))
                    if scenario == "first_data_and_first_summary_lost":
                        medium.drop_once.add((sender.name, receiver.name, SUMMARY, missing))
                try:
                    medium.run()
                except TimeoutError:
                    failures.append({"scenario": scenario, "seed": seed, "reason": "timeout"})
                    continue
                collisions += sum(event[1] == "COLLISION" for event in medium.log)
                if any([text for _, _, text in node.delivered] != expected for node in nodes[1:]):
                    failures.append({"scenario": scenario, "seed": seed, "reason": "missing_or_reordered"})
        results[str(count)] = {"seeds_per_scenario": seeds, "scenarios": 2, "failures": failures,
                               "collision_events": collisions}
    return {"model": "one AX.25 transmission per slot, shared channel, two SUMMARY announcements per DATA",
            "node_counts": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress", type=int, metavar="SEEDS")
    parser.add_argument("--json", type=str)
    args = parser.parse_args()
    if args.stress is not None:
        report = stress(args.stress)
        output = json.dumps(report, ensure_ascii=False, indent=2)
        if args.json:
            from pathlib import Path
            Path(args.json).write_text(output + "\n", encoding="utf-8")
        print(output)
    else:
        for event in demonstration():
            print(*event)
        print("PASS: 3-node recovery and ordered UTF-8 delivery")
