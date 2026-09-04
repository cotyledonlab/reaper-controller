"""WAV verdict tests — synthetic signals, no DAW needed."""

import math
import struct
import wave

import pytest

from reaper_connector import audio as A


def _write_wav(path, samples, rate=44100):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{len(samples)}h", *[max(-32768, min(32767, int(s * 32768))) for s in samples]))


def test_sine_is_ok(tmp_path):
    wav = tmp_path / "sine.wav"
    _write_wav(wav, [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(44100)])
    v = A.analyze_wav(wav)
    assert v["ok"] is True, v
    assert v["duration_s"] == 1.0
    assert v["peak"] == pytest.approx(0.5, abs=0.001)


def test_silence_fails(tmp_path):
    wav = tmp_path / "sil.wav"
    _write_wav(wav, [0.0] * 4410)
    v = A.analyze_wav(wav)
    assert v["ok"] is False
    assert "silent" in v["reasons"]


def test_full_scale_square_fails_clip(tmp_path):
    wav = tmp_path / "sq.wav"
    _write_wav(wav, [1.0 if i % 2 else -1.0 for i in range(4410)])
    v = A.analyze_wav(wav)
    assert v["ok"] is False
    assert "clipped" in v["reasons"]


def test_missing_file_raises(tmp_path):
    with pytest.raises(OSError):
        A.analyze_wav(tmp_path / "nope.wav")
