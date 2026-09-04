"""Deterministic musical builders for the session-player persona. Pure functions,
no DAW: every builder returns notes in the bridge/RPP shape
`{pitch, start_beats, dur_beats, vel, chan?}`. Artistic judgment stays with
the caller; this module only spells correctly. Middle C = C4 = 60."""

from __future__ import annotations

_SEMI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

_QUALITIES = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "dom7": [0, 4, 7, 10],
    "dim7": [0, 3, 6, 9],
    "sus4": [0, 5, 7],
    "sus2": [0, 2, 7],
    "add9": [0, 4, 7, 14],
    "6": [0, 4, 7, 9],
}

_MAJOR_DEG = [0, 2, 4, 5, 7, 9, 11]
_MINOR_DEG = [0, 2, 3, 5, 7, 8, 10]
_MAJOR_QUAL = ["maj", "min", "min", "maj", "maj", "min", "dim"]
_MINOR_QUAL = ["min", "dim", "maj", "min", "min", "maj", "maj"]
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


def parse_note(name: str) -> int:
    """'C4' → 60. Sharps (#/s), flats (b/f), any reasonable octave."""
    import re

    m = re.fullmatch(r"\s*([A-Ga-g])([#sb]?)(-?\d+)\s*", name)
    if not m:
        raise ValueError(f"bad note name: {name!r}")
    letter, acc, octv = m.group(1).upper(), m.group(2), int(m.group(3))
    semi = _SEMI[letter]
    if acc in ("#", "s"):
        semi += 1
    elif acc in ("b", "f"):
        semi -= 1
    midi = (octv + 1) * 12 + semi
    if not 0 <= midi <= 127:
        raise ValueError(f"note out of range: {name!r}")
    return midi


def chord_pitches(root: int | str, quality: str = "maj", inversion: int = 0) -> list[int]:
    """Pitch set for a chord. root midi or name; inversion rotates up."""
    if isinstance(root, str):
        root = parse_note(root)
    if quality not in _QUALITIES:
        raise ValueError(f"unknown quality {quality!r} (have: {sorted(_QUALITIES)})")
    tones = [root + iv for iv in _QUALITIES[quality]]
    n = len(tones)
    inv = inversion % n
    tones = tones[inv:] + [t + 12 for t in tones[:inv]]
    for p in tones:
        if not 0 <= p <= 127:
            raise ValueError("inversion pushes pitch out of range")
    return tones


def chord(
    root: int | str,
    quality: str = "maj",
    inversion: int = 0,
    start_beats: float = 0,
    dur_beats: float = 4,
    vel: int = 90,
    chan: int = 0,
) -> list[dict]:
    """Block chord → notes."""
    return [
        {"pitch": p, "start_beats": start_beats, "dur_beats": dur_beats, "vel": vel, "chan": chan}
        for p in chord_pitches(root, quality, inversion)
    ]


def _parse_numeral(numeral: str) -> int:
    n = numeral.strip().upper()
    if n not in _ROMAN:
        raise ValueError(f"bad numeral {numeral!r} (want I..VII)")
    return _ROMAN[n]


def progression(
    key: int | str = "C4",
    numerals: list[str] | None = None,
    mode: str = "major",
    beats_each: float = 4,
    vel: int = 88,
    chan: int = 0,
) -> list[dict]:
    """Diatonic loop: vi–IV–I–V in C by default. Returns block-chord notes."""
    if isinstance(key, str):
        # key may be bare ("C") or with octave ("C4"); bare = octave 3 root.
        try:
            key = parse_note(key)
        except ValueError:
            key = parse_note(key.strip() + "3")
    numerals = ["vi", "IV", "I", "V"] if numerals is None else numerals
    if mode == "major":
        deg, qual = _MAJOR_DEG, _MAJOR_QUAL
    elif mode == "minor":
        deg, qual = _MINOR_DEG, _MINOR_QUAL
    else:
        raise ValueError(f"mode must be major/minor, got {mode!r}")
    notes: list[dict] = []
    for i, num in enumerate(numerals):
        d = _parse_numeral(num) - 1
        root = key - 12 + deg[d]  # voice a fourth below key center
        notes.extend(
            chord(root, qual[d], start_beats=i * beats_each, dur_beats=beats_each, vel=vel, chan=chan)
        )
    return notes


def strum(
    pitches: list[int],
    start_beats: float = 0,
    dur_beats: float = 4,
    direction: str = "down",
    stagger_beats: float = 0.06,
    vel_top: int = 100,
    vel_slope: int = 3,
    chan: int = 0,
) -> list[dict]:
    """Guitar-style stagger across a pitch set (low→high = down)."""
    if direction not in ("down", "up"):
        raise ValueError("direction must be down/up")
    ordered = sorted(pitches) if direction == "down" else sorted(pitches, reverse=True)
    notes = []
    for i, p in enumerate(ordered):
        notes.append(
            {
                "pitch": p,
                "start_beats": round(start_beats + i * stagger_beats, 6),
                "dur_beats": dur_beats,
                "vel": max(1, vel_top - i * vel_slope),
                "chan": chan,
            }
        )
    return notes


def bassline(
    root: int | str = "C2",
    bars: int = 4,
    beats_per_bar: int = 4,
    pattern: str = "roots-fifths",
    vel: int = 96,
    chan: int = 0,
) -> list[dict]:
    """Per-bar low-end. patterns: roots-fifths | roots | fifths-up."""
    if isinstance(root, str):
        root = parse_note(root)
    if pattern == "roots-fifths":
        steps = [(0, 0), (1, 7), (2, 0), (3, 7)]
    elif pattern == "roots":
        steps = [(b, 0) for b in range(beats_per_bar)]
    elif pattern == "fifths-up":
        steps = [(0, 0), (1, 0), (2, 7), (3, 12)]
    else:
        raise ValueError(f"unknown bass pattern {pattern!r}")
    notes = []
    for bar in range(bars):
        for beat, iv in steps:
            if beat >= beats_per_bar:
                continue
            notes.append(
                {
                    "pitch": root + iv,
                    "start_beats": bar * beats_per_bar + beat,
                    "dur_beats": 0.9,
                    "vel": vel if beat == 0 else vel - 4,
                    "chan": chan,
                }
            )
    return notes


def compose_part(spec: dict) -> list[dict]:
    """Dispatcher over {shape: chord|progression|strum|bass, ...shape args}."""
    shape = spec.get("shape", "chord")
    args = {k: v for k, v in spec.items() if k != "shape"}
    if shape == "chord":
        return chord(**args)
    if shape == "progression":
        return progression(**args)
    if shape == "strum":
        if "pitches" not in args and "root" in args:
            args["pitches"] = chord_pitches(args.pop("root"), args.pop("quality", "maj"))
        return strum(**args)
    if shape == "bass":
        return bassline(**args)
    raise ValueError(f"unknown part shape {shape!r}")
