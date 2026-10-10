"""NumPy reference-model tests. Does NOT compile or execute Arduino/C++ code.
Run: python reference_test.py
"""
from pathlib import Path
import json
import numpy as np


def crc(data):
    c = 0xffff
    for byte in data:
        c ^= byte
        for _ in range(8):
            c = (c >> 1) ^ (0x8408 if c & 1 else 0)
    return c


FRAME = bytes.fromhex("82 A0 A4 A6 40 40 60 9C 60 86 82 98 98 61 03 F0")
FRAME += bytes(k if k % 3 else 255 for k in range(180))
FLAG = [(0x7e >> k) & 1 for k in range(8)]


def hdlc(corrupt=False, closing=True):
    fcs = crc(FRAME) ^ 0xffff
    p = bytearray(FRAME + fcs.to_bytes(2, "little"))
    if corrupt:
        p[16] ^= 1
    bits = FLAG * 35
    ones = 0
    for byte in p:
        for k in range(8):
            bit = (byte >> k) & 1
            bits.append(bit)
            ones = ones + 1 if bit else 0
            if ones == 5:
                bits.append(0)
                ones = 0
    return bits + (FLAG * 4 if closing else [])


def modulate(bits, baud=1200, offset=0, noise=True):
    tones, tone = [], 0
    for bit in bits:
        tone ^= bit == 0
        tones.append(tone)
    pcm = np.zeros(144000, dtype=np.int16)
    symbols = np.floor(np.arange(144000 - 7313) * baud / 48000).astype(int)
    symbols = symbols[symbols < len(tones)]
    freq = np.where(np.array(tones)[symbols], 2200, 1200) + offset
    phase = np.cumsum(2 * np.pi * freq / 48000)
    x = 9000 * np.sin(phase) + 900
    if noise:
        x += np.random.default_rng(17).uniform(-1311, 1311, len(x))
    pcm[7313:7313 + len(x)] = x.astype(np.int16)
    return pcm


def finish(raw):
    bits, ones = [], 0
    for bit in raw:
        if ones == 5:
            if bit:
                return None
            ones = 0
            continue
        ones = ones + 1 if bit else 0
        bits.append(bit)
    if ones == 5 or len(bits) % 8 or not 17 * 8 <= len(bits) <= 330 * 8:
        return None
    packet = bytes(sum(bits[i+k] << k for k in range(8)) for i in range(0, len(bits), 8))
    if crc(packet) != 0xf0b8:
        return None
    addr, end = 0, False
    while addr + 7 <= len(packet) - 3 and addr < 70:
        if any(v & 1 for v in packet[addr:addr+6]):
            return None
        end = bool(packet[addr+6] & 1)
        addr += 7
        if end:
            break
    return packet[:-2] if end and addr >= 14 else None


def decode(pcm, seen=None):
    seen = [] if seen is None else seen
    # float32 correlation and window DC removal, matching the sketch algorithm.
    windows = np.lib.stride_tricks.sliding_window_view(pcm, 40).astype(np.float32)
    windows -= windows.mean(axis=1, keepdims=True)
    energies = []
    for f in [1200, 2200]:
        phase = (2*np.pi*f*np.arange(40)/48000).astype(np.float32)
        re = np.sum(windows * np.cos(phase), axis=1)
        im = np.sum(windows * np.sin(phase), axis=1)
        energies.append(re*re+im*im)
    disc = energies[0] - energies[1]
    for offset in [0, -1, 1, -2, 2, -3, 3, -4, 4]:
        step = 48000 / (1200 + offset)
        for phase in range(0, 40, 4):
            at = np.floor(np.arange(phase, len(pcm)-40, step)+0.5).astype(int)
            tone = disc[at] >= 0
            bits = (tone[1:] == tone[:-1]).astype(int)
            shift, raw, collecting = 0, [], False
            for bit, sample in zip(bits.tolist(), at[1:].tolist()):
                shift = (shift >> 1) | (bit << 7)
                if collecting:
                    if len(raw) < 4096:
                        raw.append(bit)
                    else:
                        collecting, raw = False, []
                if shift == 0x7e:
                    packet = finish(raw[:-8]) if collecting and len(raw) >= 8 else None
                    if packet is not None and not any(abs(sample-s)<80 and p==packet for s,p in seen):
                        seen.append((sample,packet))
                    collecting, raw = True, []
                if shift == 0xff:
                    collecting, raw = False, []
    return seen


def main():
    global FRAME
    assert crc(b"123456789") ^ 0xffff == 0x906e
    results = ["CRC-16/X-25 known vector: PASS"]
    for baud in [1196.4, 1200, 1203.6]:
        pcm = modulate(hdlc(), baud, 7)
        seen = decode(pcm)
        assert len(seen) == 1 and seen[0][1] == FRAME, (baud,len(seen))
        decode(pcm, seen)
        assert len(seen) == 1
        results.append(f"AFSK baud={baud}, tone offset=+7 Hz, DC/noise/stuffing/duplicate slot: PASS")
    for label, pcm in [
        ("bad FCS", modulate(hdlc(corrupt=True))),
        ("no closing flag", modulate(hdlc(closing=False))),
        ("silence", np.zeros(144000,dtype=np.int16)),
        ("noise only", np.random.default_rng(7).integers(-5000,5000,144000,dtype=np.int16)),
    ]:
        assert not decode(pcm), label
        results.append(f"reject {label}: PASS")
    # Shorten payload for two complete identical packets in the same 3s capture.
    FRAME = FRAME[:16] + b"repeat"
    seen = decode(modulate(hdlc()+hdlc()))
    assert len(seen) == 2 and all(p == FRAME for _,p in seen)
    results.append("two identical transmissions remain two frames: PASS")
    print("\n".join(results))
    Path(__file__).with_name("reference_results.json").write_text(
        json.dumps({"scope":"Python reference model only; C++/hardware not tested", "results":results}, indent=2),
        encoding="utf-8")


if __name__ == "__main__":
    main()
