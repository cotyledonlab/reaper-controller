"""OSC codec + loopback tests — no DAW needed."""

import threading

import pytest

from reaper_connector import osc as O


def test_pack_parse_roundtrip_all_types():
    data = O.pack_message("/track/1/volume", [1, 0.5, "vox", True, False, None])
    (addr, args), = O.parse_packet(data)
    assert addr == "/track/1/volume"
    assert args[0] == 1
    assert args[1] == pytest.approx(0.5)
    assert args[2] == "vox"
    assert args[3] is True
    assert args[4] is False
    assert args[5] is None


def test_trigger_no_args():
    (addr, args), = O.parse_packet(O.pack_message("/play", []))
    assert (addr, args) == ("/play", [])


def test_bad_address_rejected():
    with pytest.raises(ValueError):
        O.pack_message("play", [])


def test_bad_arg_type_rejected():
    with pytest.raises(ValueError):
        O.pack_message("/x", [b"bytes"])


def test_bundle_parse():
    import struct

    m1 = O.pack_message("/a", [1])
    m2 = O.pack_message("/b", [2.5])
    bundle = b"#bundle\x00" + b"\x00" * 8
    for m in (m1, m2):
        bundle += struct.pack(">i", len(m)) + m
    msgs = O.parse_packet(bundle)
    assert [a for a, _ in msgs] == ["/a", "/b"]
    assert msgs[0][1] == [1]
    assert msgs[1][1][0] == pytest.approx(2.5)


def test_client_server_loopback():
    import socket

    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.settimeout(2.0)
    got = []

    def _recv():
        data, _ = srv.recvfrom(65535)
        got.extend(O.parse_packet(data))

    t = threading.Thread(target=_recv, daemon=True)
    t.start()
    O.OscClient(port=port).send("/track/2/pan", [0.25])
    t.join(timeout=3.0)
    srv.close()
    assert got == [("/track/2/pan", [pytest.approx(0.25)])]


def test_capture_collects_and_filters():
    import socket
    import time

    srv_port_holder = []

    def _sender(port):
        time.sleep(0.1)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(O.pack_message("/track/1/vu", [0.7]), ("127.0.0.1", port))
        s.sendto(O.pack_message("/play", []), ("127.0.0.1", port))
        s.close()

    # grab a free port first
    tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tmp.bind(("127.0.0.1", 0))
    port = tmp.getsockname()[1]
    tmp.close()
    th = threading.Thread(target=_sender, args=(port,), daemon=True)
    th.start()
    events = O.capture(port=port, secs=0.6)
    th.join()
    addrs = [e["address"] for e in events]
    assert "/track/1/vu" in addrs and "/play" in addrs
