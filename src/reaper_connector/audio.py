"""Render orchestration + stdlib WAV verdicts (no numpy).

`render` shells to the installed REAPER binary with `-renderproject`
(headless by design — renders and exits, never touches the open GUI).
`analyze` fails silence, clipping, and DC offset: generate → render →
analyze → iterate.
"""

from __future__ import annotations

import math
import struct
import subprocess
import wave
from pathlib import Path

from reaper_connector.doctor import BIN_PATH

AUDIBLE_PEAK_FLOOR = 0.001  # -60 dBFS
CLIP_PEAK_CEIL = 0.99
DC_OFFSET_CEIL = 0.01


def render_project(
    rpp: str | Path, wav: str | None = None, timeout: float = 180.0
) -> dict:
    """Render an RPP headless. With `wav`, renders a patched copy (source untouched)."""
    from reaper_connector import rpp as _rpp

    rpp = Path(rpp)
    target = rpp
    if wav is not None:
        target = Path(str(rpp.with_name(rpp.stem + ".rendercopy.rpp")))
        _rpp.patch_render_file(rpp, target, str(wav))
    proc = subprocess.run(
        [str(BIN_PATH), "-renderproject", str(target)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out_wav = Path(wav) if wav is not None else None
    if out_wav is None:
        info = _rpp.read(rpp)
        out_wav = Path(info["render_file"]) if info.get("render_file") else None
    ok = (
        proc.returncode == 0
        and out_wav is not None
        and out_wav.is_file()
        and out_wav.stat().st_size > 0
    )
    return {
        "ok": bool(ok),
        "returncode": proc.returncode,
        "wav": str(out_wav) if out_wav else None,
        "wav_bytes": out_wav.stat().st_size if ok else 0,
        "log_tail": (proc.stdout + proc.stderr)[-2000:],
    }


def _read_mono(wav: str | Path) -> tuple[list[float], int]:
    with wave.open(str(wav), "rb") as w:
        n_ch, width, rate, n_fr = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n_fr)
    total = n_fr * n_ch
    if w.getcomptype() != "NONE":
        raise ValueError(f"compressed WAV: {w.getcomptype()}")
    if width == 1:
        vals = struct.unpack(f"<{total}B", raw)
        samples = [(v - 128) / 128.0 for v in vals]
    elif width == 2:
        vals = struct.unpack(f"<{total}h", raw)
        samples = [v / 32768.0 for v in vals]
    elif width == 3:
        samples = []
        for i in range(total):
            b = raw[i * 3 : i * 3 + 3]
            n = int.from_bytes(b, "little", signed=True)
            samples.append(n / 8388608.0)
    elif width == 4:
        vals = struct.unpack(f"<{total}i", raw)
        samples = [v / 2147483648.0 for v in vals]
    else:
        raise ValueError(f"unsupported width: {width}")
    if n_ch > 1:
        samples = [sum(samples[i * n_ch : (i + 1) * n_ch]) / n_ch for i in range(n_fr)]
    return samples, rate


def analyze_wav(wav: str | Path) -> dict:
    """Verdict: ok=true means audible, unclipped, no DC offset."""
    wav = Path(wav)
    samples, rate = _read_mono(wav)
    n = len(samples)
    if n == 0:
        return {"ok": False, "reason": "empty", "wav": str(wav)}
    peak = max(abs(s) for s in samples)
    rms = math.sqrt(sum(s * s for s in samples) / n)
    dc = sum(samples) / n
    reasons = []
    if peak < AUDIBLE_PEAK_FLOOR:
        reasons.append("silent")
    if peak > CLIP_PEAK_CEIL:
        reasons.append("clipped")
    if abs(dc) > DC_OFFSET_CEIL:
        reasons.append("dc-offset")
    db = lambda v: round(20 * math.log10(v), 1) if v > 0 else float("-inf")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "wav": str(wav),
        "duration_s": round(n / rate, 3),
        "sample_rate": rate,
        "peak": round(peak, 4),
        "peak_db": db(peak),
        "rms": round(rms, 5),
        "rms_db": db(rms),
        "dc_offset": round(dc, 5),
    }
