"""Text-`.RPP` builder/reader grounded in `templates/ref_song.rpp`.

The golden template is a byte-copy of a project REAPER itself wrote
(`docs/tickets/0002`: built via bridge, saved by REAPER). `create` only
substitutes tokens; every other line is REAPER-verbatim, so generated
projects render. Unknown chunks are preserved by construction; `read`
flags anything outside the known constructs in `warnings`.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from pathlib import Path

TICKS_PER_QN = 960

_TOKENS = (
    "__EPOCH__",
    "__RENDER_FILE__",
    "__TEMPO_BPM__",
    "__TRACK_GUID__",
    "__NAME__",
    "__FXID__",
    "__ITEM_IGUID__",
    "__ITEM_GUID__",
    "__POOLED_GUID__",
    "__SRC_GUID__",
    "__MASTER_TRACKID__",
    "__EGUID_SPEED__",
    "__EGUID_TEMPO__",
    "__ITEM_LENGTH__",
    "__NOTE_LINES__",
)


def new_guid() -> str:
    h = uuid.uuid4().hex.upper()
    return f"{{{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}}}"


def golden_path() -> Path:
    override = os.environ.get("REAPER_GOLDEN")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        cand = parent / "templates" / "ref_song.rpp"
        if cand.is_file():
            return cand
        cand = parent / "reaper-controller" / "templates" / "ref_song.rpp"
        if cand.is_file():
            return cand
    raise FileNotFoundError("templates/ref_song.rpp not found")


def encode_notes(notes: list[dict], item_len_beats: float) -> list[str]:
    """notes: [{pitch, start_beats, dur_beats, vel, chan=0}] → `E …` lines.

    Beats are quarter-note offsets from item start (QN-mapped, tempo-free).
    Offs sort before ons at equal ticks; trailing all-notes-off closes the item.
    """
    events: list[tuple[int, int, int, int, int]] = []
    for n in notes:
        s = int(round(float(n["start_beats"]) * TICKS_PER_QN))
        e = s + int(round(float(n["dur_beats"]) * TICKS_PER_QN))
        ch = int(n.get("chan", 0)) & 0x0F
        events.append((s, 1, 0x90 + ch, int(n["pitch"]), int(n["vel"])))
        events.append((e, 0, 0x80 + ch, int(n["pitch"]), 0))
    events.sort(key=lambda e: (e[0], e[1]))
    lines, prev = [], 0
    for tick, _, st, d1, d2 in events:
        lines.append(f"        E {tick - prev} {st:02x} {d1:02x} {d2:02x}")
        prev = tick
    end_tick = int(round(float(item_len_beats) * TICKS_PER_QN))
    lines.append(f"        E {end_tick - prev} b0 7b 00")
    return lines


def decode_notes(lines: list[str]) -> list[dict]:
    """`E …` lines → [{pitch, start_beats, dur_beats, vel, chan}]."""
    abs_tick, open_notes, notes = 0, {}, []
    for ln in lines:
        parts = ln.split()
        if len(parts) < 5 or parts[0] != "E":
            continue
        try:
            delta, st, d1, d2 = int(parts[1]), int(parts[2], 16), int(parts[3], 16), int(parts[4], 16)
        except ValueError:
            continue
        abs_tick += delta
        kind, ch = st & 0xF0, st & 0x0F
        if kind == 0x90 and d2 != 0:
            open_notes.setdefault((ch, d1), []).append((abs_tick, d2))
        elif kind == 0x80 or (kind == 0x90 and d2 == 0):
            stack = open_notes.get((ch, d1), [])
            if stack:
                s, vel = stack.pop()
                notes.append(
                    {
                        "pitch": d1,
                        "start_beats": round(s / TICKS_PER_QN, 6),
                        "dur_beats": round((abs_tick - s) / TICKS_PER_QN, 6),
                        "vel": vel,
                        "chan": ch,
                    }
                )
    notes.sort(key=lambda n: (n["start_beats"], n["pitch"]))
    return notes


def _check_no_spaces(path_str: str, what: str) -> None:
    if " " in path_str:
        raise ValueError(
            f"{what} path contains spaces — RPP render lines are unquoted: {path_str!r}"
        )


def create(
    path: str | Path,
    *,
    name: str = "AgentSynth",
    tempo: float = 120,
    notes: list[dict] | None = None,
    length_sec: float = 8,
    render_file: str | None = None,
    item_len_beats: float | None = None,
) -> dict:
    """Emit a one-ReaSynth song RPP. Returns a summary dict."""
    from reaper_connector.templates import default_notes

    notes = default_notes() if notes is None else notes
    path = Path(path)
    # Absolute: relative RENDER_FILE resolves against the RPP's own dir (see pitfalls #1).
    render_file = render_file or str(path.resolve().with_suffix(".wav"))
    if not Path(render_file).is_absolute():
        render_file = str((Path.cwd() / render_file).resolve())
    _check_no_spaces(str(render_file), "render")
    if item_len_beats is None:
        item_len_beats = max([n["start_beats"] + n["dur_beats"] for n in notes] + [4])

    text = golden_path().read_text()
    subs = {
        "__EPOCH__": str(int(time.time())),
        "__RENDER_FILE__": render_file,
        "__TEMPO_BPM__": str(tempo).rstrip("0").rstrip(".") if isinstance(tempo, float) else str(tempo),
        "__TRACK_GUID__": new_guid(),
        "__NAME__": name,
        "__FXID__": new_guid(),
        "__ITEM_IGUID__": new_guid(),
        "__ITEM_GUID__": new_guid(),
        "__POOLED_GUID__": new_guid(),
        "__SRC_GUID__": new_guid(),
        "__MASTER_TRACKID__": new_guid(),
        "__EGUID_SPEED__": new_guid(),
        "__EGUID_TEMPO__": new_guid(),
        "__ITEM_LENGTH__": str(length_sec).rstrip("0").rstrip(".") if isinstance(length_sec, float) else str(length_sec),
        "__NOTE_LINES__": "\n".join(encode_notes(notes, item_len_beats)),
    }
    for tok, val in subs.items():
        text = text.replace(tok, val)
    leftover = [t for t in _TOKENS if t in text]
    if leftover:
        raise RuntimeError(f"unsubstituted tokens: {leftover}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return {
        "path": str(path),
        "name": name,
        "tempo": tempo,
        "notes": len(notes),
        "render_file": render_file,
    }


def _parse_vst_name(line: str) -> str | None:
    m = re.match(r'\s*<VST\s+"([^"]+)"', line)
    return m.group(1) if m else None


def read(path: str | Path) -> dict:
    """Parse an RPP into {tempo, render_file, sample_rate, tracks, warnings}."""
    lines = Path(path).read_text(errors="replace").splitlines()
    result: dict = {
        "tempo": None,
        "render_file": None,
        "sample_rate": None,
        "tracks": [],
        "markers": [],
        "selection": None,
        "loop_flag": None,
        "sends": [],
        "warnings": [],
    }
    stack: list[str] = []
    cur_track: dict | None = None
    cur_item: dict | None = None
    cur_take: dict | None = None
    take_ctx: dict | None = None
    in_midi = False
    midi_lines: list[str] = []

    for ln in lines:
        s = ln.strip()
        if s.startswith("<"):
            tag = s[1:].split()[0] if len(s) > 1 else ""
            if tag == "VST" and cur_track is not None:
                vname = _parse_vst_name(ln)
                if vname:
                    cur_track["fx"].append(vname)
            stack.append(tag)
            if tag == "TRACK":
                m = re.search(r"\{[^}]*\}", s)
                cur_track = {
                    "guid": m.group(0) if m else None,
                    "name": None,
                    "fx": [],
                    "items": [],
                    "receives": [],
                    "folder_depth": 0,
                    "folder_flag": 0,
                }
                result["tracks"].append(cur_track)
            elif tag == "ITEM":
                cur_item = {"position": 0.0, "length": 0.0, "notes": [], "takes": []}
                cur_take = None
                take_ctx = None
                if cur_track is not None:
                    cur_track["items"].append(cur_item)
                else:
                    result["warnings"].append("ITEM outside TRACK")
            elif tag == "SOURCE" and cur_item is not None:
                cur_take = {
                    "selected": take_ctx["selected"] if take_ctx else None,
                    "name": take_ctx["name"] if take_ctx else None,
                    "notes": [],
                }
                cur_item["takes"].append(cur_take)
                take_ctx = None
                in_midi = "MIDI" in s
                midi_lines = []
            continue
        if s == "TAKE" or s.startswith("TAKE "):
            # Take-lane marker preceding its SOURCE (e.g. `TAKE SEL` + NAME).
            # Excludes TAKEVOLPAN/TAKECOLOR (no space after TAKE).
            take_ctx = {"selected": "SEL" in s.split(), "name": None}
            continue
        if s == ">":
            if stack:
                closed = stack.pop()
                if closed == "SOURCE" and cur_take is not None and in_midi:
                    cur_take["notes"] = decode_notes(midi_lines)
                    cur_take = None
                    in_midi = False
            continue
        if in_midi:
            if s.startswith("E "):
                midi_lines.append(s)
            continue
        depth = len(stack)
        if depth == 1:
            if s.startswith("MARKER "):
                # MARKER <num> <pos> <name> ... (name possibly quoted).
                m = re.match(r'MARKER\s+(\S+)\s+(\S+)\s+("[^"]*"|\S+)', s)
                if m:
                    try:
                        result["markers"].append(
                            {
                                "number": int(m.group(1)),
                                "position_sec": float(m.group(2)),
                                "name": m.group(3).strip('"'),
                            }
                        )
                    except ValueError:
                        result["warnings"].append(f"unparsed MARKER: {s}")
                else:
                    result["warnings"].append(f"unparsed MARKER: {s}")
            elif s.startswith("SELECTION "):
                # Time selection; loop points mirror it in storage (t5).
                try:
                    a, b = s.split()[1:3]
                    result["selection"] = [float(a), float(b)]
                except (IndexError, ValueError):
                    result["warnings"].append(f"unparsed SELECTION: {s}")
            elif s.startswith("LOOP ") and not stack[0] == "ITEM":
                try:
                    result["loop_flag"] = int(s.split()[1])
                except (IndexError, ValueError):
                    pass
            if s.startswith("TEMPO "):
                try:
                    result["tempo"] = float(s.split()[1])
                except (IndexError, ValueError):
                    result["warnings"].append(f"unparsed TEMPO: {s}")
            elif s.startswith("RENDER_FILE "):
                result["render_file"] = s[len("RENDER_FILE "):].strip().strip('"')
            elif s.startswith("SAMPLERATE "):
                try:
                    result["sample_rate"] = float(s.split()[1])
                except (IndexError, ValueError):
                    pass
        if cur_track is not None and stack and stack[-1] == "TRACK":
            if s.startswith("NAME ") and cur_track["name"] is None:
                cur_track["name"] = s[5:].strip().strip('"')
            elif s.startswith("ISBUS "):
                # ISBUS <folderflag> <folderdepth>: depth 1 opens a folder,
                # -1 closes (last in folder), 0 normal. Observed live (t5).
                try:
                    a, b = s.split()[1:3]
                    cur_track["folder_flag"] = int(a)
                    cur_track["folder_depth"] = int(b)
                except (IndexError, ValueError):
                    result["warnings"].append(f"unparsed ISBUS: {s}")
            elif s.startswith("AUXRECV "):
                # Receives live on the DESTINATION track. Observed (t5):
                # AUXRECV <srcidx> ? <vol> ... — src index + volume parsed,
                # rest preserved raw (mute/phase fields not yet mapped).
                try:
                    f = s.split()
                    cur_track["receives"].append(
                        {"src_track": int(f[1]), "volume": float(f[3]), "raw": s}
                    )
                except (IndexError, ValueError):
                    result["warnings"].append(f"unparsed AUXRECV: {s}")
        if cur_item is not None and stack and stack[-1] == "ITEM":
            if s.startswith("NAME ") and take_ctx is not None and take_ctx.get("name") is None:
                take_ctx["name"] = s[5:].strip().strip('"')
            elif s.startswith("POSITION "):
                try:
                    cur_item["position"] = float(s.split()[1])
                except (IndexError, ValueError):
                    pass
            elif s.startswith("LENGTH "):
                try:
                    cur_item["length"] = float(s.split()[1])
                except (IndexError, ValueError):
                    pass
    if result["tempo"] is None:
        result["warnings"].append("no TEMPO found")
    if not result["tracks"]:
        result["warnings"].append("no TRACKs found")
    # Selected take plays: default to the first when nothing is marked.
    for tr in result["tracks"]:
        for it in tr["items"]:
            takes = it.get("takes", [])
            if takes and not any(t.get("selected") for t in takes):
                takes[0]["selected"] = True
            sel = next((t for t in takes if t.get("selected")), None)
            it["notes"] = sel["notes"] if sel else []
    # Sends are stored as receives on destinations — derive the send view.
    for ti, tr in enumerate(result["tracks"]):
        for rcv in tr.get("receives", []):
            result["sends"].append(
                {"from": rcv["src_track"], "to": ti, "volume": rcv["volume"]}
            )
    return result


def patch_render_file(src: str | Path, dst: str | Path, wav: str) -> Path:
    """Copy an RPP with its RENDER_FILE line swapped (unquoted, no spaces)."""
    _check_no_spaces(wav, "render")
    wav = str(Path(wav).resolve())
    text = Path(src).read_text()
    new_text, n = re.subn(r"(?m)^(\s*RENDER_FILE\s+).*$", rf"\1{wav}", text, count=1)
    if n != 1:
        raise RuntimeError("no single RENDER_FILE line to patch")
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(new_text)
    return dst
