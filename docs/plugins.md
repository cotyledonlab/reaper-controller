# Plugin inventory (observed live, 2026-09-05, REAPER 7.79/macOS-arm64)

Every entry below was loaded with `engineer.add_fx` against the running
session and read back via the reply's observed `name`. Load strings are
exact — pass them verbatim as the `fx` param. Do **not** default to
ReaSynth when one of these fits the job.

Render verdicts are per-plugin: only Surge XT has a render pass so far
(`scratch/fx_verify_surge.wav`: peak 0.329 / −9.7 dB, rms −26.9 dB,
`analyze` clean). "Loaded" means the plugin instantiated and reported
its name back — not that it made sound (sample libraries, logins, and
downloaded content are noted where they apply).

## Instruments (VSTi)

| `fx` string | Observed as | Notes |
|---|---|---|
| `Surge XT` | `VST3i: Surge XT (Surge Synth Team) (2->6ch)` | Render-verified audible with init patch. Factory content (377 MB) in `~/Library/Application Support/Surge XT/`. User-level install, no sudo. |
| `Dexed` | `VST3i: Dexed (Digital Suburban)` | DX7 clone. Default patch loads; render untested. User-level install. |
| `BBC Symphony Orchestra` | `VST3i: BBC Symphony Orchestra (Spitfire Audio)` | User installed BBC SO Discover library. Render untested — first note may need the library path confirmed in the plugin window. |
| `Splice INSTRUMENT` | `VST3i: Splice INSTRUMENT (Splice)` | Needs Splice login + downloaded sounds (user has 1 so far). Render untested. |
| `Vital` | `VST3i: Vital (Vital Audio)` | Free tier, needs Vital account on first GUI open. Render untested. System-level install (`/Library/Audio/Plug-Ins/VST3/`). |
| `OB-Xd` | `VSTi: OB-Xd (discoDSP)` | Note: matched as **VST2** (`VSTi`, not VST3i) — the VST3 (`OB-Xd 3.vst3`) did not match the `OB-Xd` substring; try `OB-Xd 3` if you want the VST3. Render untested. System-level install. |
| `MT-PowerDrumKit` | `VST3i: MT-PowerDrumKit (MANDA AUDIO) (16 out)` | Free acoustic kit, strict General MIDI (kick 36, snare 38, closed hat 42, open 46, crash 49/57, toms 41–50). Render-verified in `midnight_driver_kit.wav`. NOTE: the `fx` string must be exact — `PowerDrumKit` alone returns `FX_NOT_FOUND`. |
| `ReaSynth` | stock | Fallback only. Thin test beep — prefer Surge XT / Vital / Dexed / OB-Xd for real parts. |
| `ReaSynDr`, `ReaSamplOmatic5000` | stock | ReaSynDr tested 2026-09-05: single pitch-tracking synth-drum voice (48-note chromatic sweep → same blip every key, 4 params), NOT a kit — but works as electro-percussion (sub-kick note 33, zaps). ReaSamplOmatic untested. |

## FX

| `fx` string | Observed as | Notes |
|---|---|---|
| `Surge XT Effects` | `VST3: Surge XT Effects (Surge Synth Team)` | Filter/delay/modulation multi-FX. User-level install. |
| `ValhallaSupermassive` | `VST3: ValhallaSupermassive (Valhalla DSP, LLC)` | Free reverb/delay. Also `ValhallaFreqEcho`, `ValhallaSpaceModulator` (scanned, load untested). User-level install. |
| `TDR Nova` | `VST: TDR Nova (Tokyo Dawn Labs)` | Dynamic EQ. Note: matched as **VST2** — prefer the VST3 with `fx: "TDR Nova.vst3"`? Untested; both scanned. User-level install. |
| `TDR Kotelnikov` | `VST: TDR Kotelnikov (Tokyo Dawn Labs)` | Bus compressor. Same VST2/VST3 note as Nova. User-level install. |
| `MEqualizer` | `VST: MEqualizer (MeldaProduction)` | Stands for the whole MFreeFXBundle (MCompressor, MSaturator, MReverb, … — full AU set confirmed via `auval`). System-level install. |

## Stock (no install, always present)

Full Cockos Rea* suite (`ReaEQ/Comp/Delay/Verb/Verbate/Pitch/Gate/Limit/Xcomp/Fir/Tune`), ~200 JSFX (`sstillwell/*`, `guitar/*`, `synthesis/*`, `loser/*`), Apple `DLSMusicDevice` + `AUSampler`. See `reaper-vstplugins_arm64.ini` for the scan record.

## How this was installed (no-sudo pattern)

Plugin `.pkg` installers that demand root can be redirected to the user
domain without a password: `brew fetch --cask <cask>`, mount the DMG,
`pkgutil --expand`, then `ditto -x -z <pkg>/Payload` into
`~/Library/Audio/Plug-Ins/{Components,VST3,VST}` (for directory pkgs) or
extract-and-rename for file pkgs (TDR style). Surge factory content goes
to `~/Library/Application Support/Surge XT/`. REAPER scans the user
domain on launch — restart (or Preferences → Plug-ins → Re-scan) picks
everything up. Verified 2026-09-04/05 with Surge XT, Dexed, Valhalla ×3,
TDR ×2.
