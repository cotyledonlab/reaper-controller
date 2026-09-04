/**
 * reaper-connector for pi.
 *
 * First-class REAPER tools for the agent: studio engineer (tracks, FX,
 * routing, mix) + session player (parts, play-in, takes) over background
 * protocols — bridge/OSC/MIDI/files, never computer-use.
 *
 * This extension shells out to the `reaper-connector` CLI, so it needs no
 * npm dependencies and no Python bridge. Provide the CLI via either:
 *   - `pip install -e "<repo>[dev]"`  (puts `reaper-connector` on PATH), or
 *   - `export REAPER_CONNECTOR_BIN=/path/to/reaper-connector`
 *
 * Install: copy this file to `~/.pi/agent/extensions/reaper-connector.ts`
 * (global) or `.pi/extensions/` (project-local), then `/reload`.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { execFileSync } from "node:child_process";
import { Type } from "typebox";

const BIN = process.env.REAPER_CONNECTOR_BIN ?? "reaper-connector";
const MAX_OUT = 6000;

function run(args: string[]): string {
	try {
		const out = execFileSync(BIN, args, {
			encoding: "utf-8",
			timeout: 180_000,
			maxBuffer: 4 * 1024 * 1024,
		}).trim();
		return out.length > MAX_OUT ? `${out.slice(0, MAX_OUT)}\n…(truncated)` : out;
	} catch (err: unknown) {
		const e = err as { stderr?: string; message?: string };
		const detail = (e.stderr ?? e.message ?? String(err)).trim().slice(0, 1000);
		throw new Error(`reaper-connector ${args[0]} failed: ${detail}`);
	}
}

function text(result: string) {
	return { content: [{ type: "text" as const, text: result }], details: {} };
}

export default function reaperConnector(pi: ExtensionAPI) {
	pi.registerTool({
		name: "reaper_doctor",
		label: "REAPER pre-flight check",
		description:
			"Readiness probe: binary, version, resource paths, OSC files, render flags, " +
			"ports, OSC device, bridge state. Run first in a fresh session. " +
			"fix=true creates the AgentBridge/queue dirs (its only mutation).",
		parameters: Type.Object({
			fix: Type.Optional(Type.Boolean({ description: "Create bridge/queue dirs" })),
			json: Type.Optional(Type.Boolean({ description: "Machine-readable output" })),
		}),
		async execute(_id, p) {
			const args = ["doctor"];
			if (p.fix) args.push("--fix");
			if (p.json) args.push("--json");
			return text(run(args));
		},
	});

	pi.registerTool({
		name: "reaper_status",
		label: "REAPER status",
		description: "REAPER + bridge daemon + midi-serve detection snapshot.",
		parameters: Type.Object({}),
		async execute() {
			return text(run(["status"]));
		},
	});

	pi.registerTool({
		name: "reaper_bridge_send",
		label: "Send bridge op to REAPER",
		description:
			"One file-drop RPC op through the in-REAPER Lua daemon, e.g. ping, hello, " +
			"engineer.get_mix, engineer.add_fx, player.insert_midi. Replies carry " +
			"observed-back evidence. Bridge tracks are 0-based.",
		parameters: Type.Object({
			op: Type.String({ description: "Op name, e.g. engineer.get_mix" }),
			params: Type.Optional(Type.String({ description: "JSON params object" })),
			timeout: Type.Optional(Type.Number({ description: "Seconds (default 10)" })),
		}),
		async execute(_id, p) {
			const args = ["bridge-send", p.op];
			if (p.params) args.push("--params", p.params);
			args.push("--timeout", String(p.timeout ?? 10));
			return text(run(args));
		},
	});

	pi.registerTool({
		name: "reaper_templates",
		label: "REAPER templates",
		description: "List song templates and their defaults.",
		parameters: Type.Object({}),
		async execute() {
			return text(run(["templates"]));
		},
	});

	pi.registerTool({
		name: "reaper_create",
		label: "Create REAPER project",
		description:
			"Generate a .RPP song file from a template (REAPER-verbatim skeleton + params: " +
			"name, tempo, notes, length_sec). Render paths resolve absolute.",
		parameters: Type.Object({
			path: Type.String({ description: "Output .RPP path" }),
			template: Type.Optional(Type.String({ description: "Template (default song)" })),
			params: Type.Optional(Type.String({ description: "JSON overrides, e.g. {\"tempo\": 100}" })),
		}),
		async execute(_id, p) {
			const args = ["create", p.path, "--template", p.template ?? "song"];
			if (p.params) args.push("--params", p.params);
			return text(run(args));
		},
	});

	pi.registerTool({
		name: "reaper_read",
		label: "Read REAPER project",
		description:
			"Parse an RPP: tempo, tracks (mix, fx, items, take lanes, notes), sends, " +
			"markers, selection. Warnings flag the unknown.",
		parameters: Type.Object({
			path: Type.String({ description: "Project file path (.RPP)" }),
		}),
		async execute(_id, p) {
			return text(run(["read", p.path]));
		},
	});

	pi.registerTool({
		name: "reaper_render",
		label: "Render REAPER project",
		description:
			"Headless -renderproject bounce (open GUI untouched). With wav, renders a " +
			"patched copy — the source RPP is never modified. Loop points never " +
			"truncate renders (bounds rule).",
		parameters: Type.Object({
			path: Type.String({ description: "Project file path (.RPP)" }),
			wav: Type.Optional(Type.String({ description: "Override output wav" })),
			timeout: Type.Optional(Type.Number({ description: "Seconds (default 180)" })),
		}),
		async execute(_id, p) {
			const args = ["render", p.path];
			if (p.wav) args.push("--wav", p.wav);
			args.push("--timeout", String(p.timeout ?? 180));
			return text(run(args));
		},
	});

	pi.registerTool({
		name: "reaper_analyze",
		label: "Analyze wav",
		description: "WAV verdict: ok=true means audible, unclipped, no DC offset.",
		parameters: Type.Object({
			path: Type.String({ description: "Wav file path" }),
		}),
		async execute(_id, p) {
			return text(run(["analyze", p.path]));
		},
	});

	pi.registerTool({
		name: "reaper_osc_send",
		label: "Send OSC to REAPER",
		description:
			"One live OSC message, e.g. /play, /track/1/volume 0.5. Tracks are 1-based " +
			"(OSC convention); /tempo is normalized 40+256v; bridge is 0-based — don't mix them.",
		parameters: Type.Object({
			address: Type.String({ description: "OSC address, e.g. /track/1/volume" }),
			values: Type.Optional(Type.Array(Type.String(), { description: "Args as JSON strings" })),
			host: Type.Optional(Type.String({ description: "Host (default 127.0.0.1)" })),
			port: Type.Optional(Type.Number({ description: "Default 8000" })),
		}),
		async execute(_id, p) {
			const args = ["osc-send", p.address, ...(p.values ?? []),
				"--host", p.host ?? "127.0.0.1", "--port", String(p.port ?? 8000)];
			return text(run(args));
		},
	});

	pi.registerTool({
		name: "reaper_telemetry",
		label: "Read REAPER telemetry",
		description:
			"Listen for OSC feedback (timecode, VU, echoes) and return it as JSON. " +
			"Capture DURING sends — echoes are immediate and change-only.",
		parameters: Type.Object({
			secs: Type.Optional(Type.Number({ description: "Capture window (default 3)" })),
			port: Type.Optional(Type.Number({ description: "Listen port (default 9000)" })),
			filter: Type.Optional(Type.String({ description: "Comma-separated addresses" })),
		}),
		async execute(_id, p) {
			const args = ["telemetry", "--secs", String(p.secs ?? 3),
				"--port", String(p.port ?? 9000)];
			if (p.filter) args.push("--filter", p.filter);
			return text(run(args));
		},
	});

	pi.registerTool({
		name: "reaper_compose",
		label: "Compose MIDI part",
		description:
			"Deterministic part builder: chord|progression|strum|bass specs to notes JSON " +
			"(bridge/RPP shape). Pipe into create/insert. Artistic judgment stays with you.",
		parameters: Type.Object({
			spec: Type.String({ description: "Part spec, e.g. {\"shape\":\"progression\",\"key\":\"C4\"}" }),
		}),
		async execute(_id, p) {
			return text(run(["compose", "--spec", p.spec]));
		},
	});

	pi.registerTool({
		name: "reaper_midi_send",
		label: "Play phrase into REAPER",
		description:
			"Play notes live into the armed track via the midi-serve daemon queue " +
			"(persistent port identity). Needs midi-serve running + track input mapped. " +
			"Never punch on beat 0 — count in 1-2 beats.",
		parameters: Type.Object({
			kind: Type.String({ description: "note | phrase" }),
			spec: Type.Optional(Type.String({ description: "Phrase notes list or compose-spec JSON" })),
			note: Type.Optional(Type.Number({ description: "MIDI pitch for kind=note" })),
			vel: Type.Optional(Type.Number({ description: "Velocity (default 96)" })),
			dur: Type.Optional(Type.Number({ description: "Seconds for kind=note (default 0.5)" })),
			tempo: Type.Optional(Type.Number({ description: "Beats per minute (default 120)" })),
		}),
		async execute(_id, p) {
			const args = ["midi-send", p.kind];
			if (p.spec) args.push("--spec", p.spec);
			if (p.note !== undefined) args.push("--note", String(p.note));
			args.push("--vel", String(p.vel ?? 96));
			if (p.dur !== undefined) args.push("--dur", String(p.dur));
			args.push("--tempo", String(p.tempo ?? 120));
			return text(run(args));
		},
	});

	pi.registerTool({
		name: "reaper_midi_ports",
		label: "List MIDI ports",
		description: "CoreMIDI ins/outs visible from here (is the virtual port up?).",
		parameters: Type.Object({}),
		async execute() {
			return text(run(["midi-ports"]));
		},
	});

	pi.registerTool({
		name: "reaper_midi_serve",
		label: "Start phrase player",
		description:
			"Start the persistent midi-serve daemon (one virtual-port identity forever). " +
			"detach=true backgrounds it and returns immediately.",
		parameters: Type.Object({
			detach: Type.Optional(Type.Boolean({ description: "Background (default true)" })),
		}),
		async execute(_id, p) {
			const args = ["midi-serve"];
			if (p.detach ?? true) args.push("--detach");
			return text(run(args));
		},
	});
}
