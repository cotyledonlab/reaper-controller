"""Named song templates: validated param sets over the golden RPP."""

from __future__ import annotations

# The t2 reference riff (C major ascent, 8 beats) — also the golden default.
_RIFF = [
    {"pitch": 60, "start_beats": 0, "dur_beats": 1, "vel": 100},
    {"pitch": 64, "start_beats": 1, "dur_beats": 1, "vel": 96},
    {"pitch": 67, "start_beats": 2, "dur_beats": 1, "vel": 96},
    {"pitch": 72, "start_beats": 3, "dur_beats": 1.5, "vel": 104},
    {"pitch": 67, "start_beats": 4.5, "dur_beats": 0.5, "vel": 90},
    {"pitch": 69, "start_beats": 5, "dur_beats": 1, "vel": 94},
    {"pitch": 71, "start_beats": 6, "dur_beats": 1, "vel": 98},
    {"pitch": 72, "start_beats": 7, "dur_beats": 1, "vel": 104},
]

TEMPLATES = {
    "song": {
        "description": "one ReaSynth track + 8-note MIDI item, 120 BPM",
        "defaults": {"name": "AgentSynth", "tempo": 120, "length_sec": 8},
    },
}


def list_templates() -> dict:
    return {k: v["description"] for k, v in TEMPLATES.items()}


def default_notes() -> list[dict]:
    return [dict(n) for n in _RIFF]
