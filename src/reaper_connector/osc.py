"""Minimal OSC 1.0 over UDP — stdlib only (no python-osc dependency).

Covers what the Agent surface needs: send int/float/str args, receive
messages + bundles with i/f/s/d/h/T/F/N/I/b args. Anything exotic raises
a clean ValueError instead of misparsing.
"""

from __future__ import annotations

import socket
import struct
import time


def _pack_str(s: str) -> bytes:
    raw = s.encode("utf-8") + b"\x00"
    return raw + b"\x00" * ((4 - len(raw) % 4) % 4)


def _read_str(buf: bytes, off: int) -> tuple[str, int]:
    end = buf.index(b"\x00", off)
    s = buf[off:end].decode("utf-8")
    # cstring runs to the NUL; the field pads up to a 4-byte boundary.
    return s, ((end + 4) // 4) * 4


def pack_message(address: str, args: list) -> bytes:
    if not address.startswith("/"):
        raise ValueError(f"OSC address must start with /: {address!r}")
    tags, body = [","], []
    for a in args:
        if isinstance(a, bool):
            tags.append("T" if a else "F")
        elif isinstance(a, int):
            tags.append("i")
            body.append(struct.pack(">i", a))
        elif isinstance(a, float):
            tags.append("f")
            body.append(struct.pack(">f", a))
        elif isinstance(a, str):
            tags.append("s")
            body.append(_pack_str(a))
        elif a is None:
            tags.append("N")
        else:
            raise ValueError(f"unsupported OSC arg type: {type(a).__name__}")
    return _pack_str(address) + _pack_str("".join(tags)) + b"".join(body)


def _parse_message(buf: bytes, off: int, end: int) -> tuple[str, list, int]:
    address, off = _read_str(buf, off)
    if not address.startswith("/"):
        raise ValueError(f"bad OSC address: {address!r}")
    tags, off = _read_str(buf, off)
    if not tags.startswith(","):
        raise ValueError("missing OSC typetags")
    args: list = []
    for tag in tags[1:]:
        if tag == "i":
            args.append(struct.unpack(">i", buf[off : off + 4])[0])
            off += 4
        elif tag == "f":
            args.append(struct.unpack(">f", buf[off : off + 4])[0])
            off += 4
        elif tag == "d":
            args.append(struct.unpack(">d", buf[off : off + 8])[0])
            off += 8
        elif tag == "h":
            args.append(struct.unpack(">h", buf[off : off + 8])[0])
            off += 8
        elif tag == "s":
            s, off = _read_str(buf, off)
            args.append(s)
        elif tag == "b":
            n = struct.unpack(">i", buf[off : off + 4])[0]
            off += 4 + ((n + 3) // 4) * 4
            args.append(f"<blob {n}B>")
        elif tag == "T":
            args.append(True)
        elif tag == "F":
            args.append(False)
        elif tag in "NI":
            args.append(None)
        else:
            raise ValueError(f"unsupported OSC typetag: {tag!r}")
    return address, args, off


def parse_packet(buf: bytes) -> list[tuple[str, list]]:
    """One UDP datagram → [(address, args)]. Handles messages + #bundle."""
    out: list[tuple[str, list]] = []
    if buf.startswith(b"#bundle\x00"):
        off = 16  # header + 8-byte timetag
        while off < len(buf):
            size = struct.unpack(">i", buf[off : off + 4])[0]
            off += 4
            addr, args, _ = _parse_message(buf, off, off + size)
            out.append((addr, args))
            off += size
    else:
        addr, args, _ = _parse_message(buf, 0, len(buf))
        out.append((addr, args))
    return out


class OscClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host, self.port = host, port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, address: str, args: list | None = None) -> dict:
        data = pack_message(address, args or [])
        self._sock.sendto(data, (self.host, self.port))
        return {"address": address, "args": args or [], "bytes": len(data)}


def capture(
    port: int = 9000, secs: float = 3.0, host: str = "127.0.0.1", addresses: list[str] | None = None
) -> list[dict]:
    """Listen for OSC feedback for `secs`, return [{t, address, args}]."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((host, port))
    except OSError as e:
        raise RuntimeError(f"cannot bind OSC listen {host}:{port}: {e}") from e
    sock.settimeout(0.05)
    t0 = time.time()
    events: list[dict] = []
    while (now := time.time()) - t0 < secs:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            continue
        try:
            msgs = parse_packet(data)
        except ValueError:
            continue
        t = round(now - t0, 3)
        for addr, args in msgs:
            if addresses and addr not in addresses:
                continue
            events.append({"t": t, "address": addr, "args": args})
    sock.close()
    return events
