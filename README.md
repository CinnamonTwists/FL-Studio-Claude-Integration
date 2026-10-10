# FL Studio × Claude

*For creative geniuses who want to offload that creativity to the machine god.*

Let Claude drive **FL Studio** on Windows: pick sounds, write every part into the piano roll, mix
and master, render WAVs, and use any song or YouTube link as a **reference** that it analyzes and
measures your mix against.

🎧 **Demo:** [`demo/claude-future-bass-sketch.mp3`](demo/claude-future-bass-sketch.mp3): an original
48-bar future-bass sketch Claude built from a single YouTube link, end to end.
Walkthrough: [docs/demo.md](docs/demo.md).

## What's in here

| Path | What it is |
|---|---|
| [`flstudio-mcp/`](flstudio-mcp/) | The MCP server: [rosasynthesiz/flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp) (MIT) extended with 14 studio tools, Windows fixes and safety guards. Changes vs upstream: [docs/upstream-changes.patch](docs/upstream-changes.patch). |
| [`skills/fl-studio/`](skills/fl-studio/) | A Claude skill that teaches the whole workflow: preflight, reference, sounds, composition, a measured mix loop, rendering, safety rules. Includes `preflight.ps1`, `write_song.py`, `mcp_call.py` and a complete example song generator. |
| [`scripts/install.ps1`](scripts/install.ps1) | One-shot installer (`-DryRun` to preview). |
| [`demo/`](demo/) | The demo project (`.flp`, stock FL content only), its render and its notes as JSON. |
| [`docs/`](docs/) | [Setup](docs/setup-windows.md) · [Architecture](docs/architecture.md) · [Lessons learned](docs/lessons-learned.md) · [Demo](docs/demo.md) |

## What Claude can do with it

- **Analyze a reference** from a file or URL: tempo, key, chords per bar, the main chord loop, bass
  roots, an energy map of sections (find the drops), the drop's drum grid, tonal balance. Uses
  GPU stem separation (Demucs) when available, ~30 s per song.
- **Pick sounds**: clone FLEX instances, switch FLEX preset packs (26 packs), load presets by name.
- **Compose**: write full arrangements into the piano roll, part by part, with markers and tempo.
- **Mix & master**: name/color/bus tracks, diagnose the mix, gain-stage, widen, drive the master.
- **Render and compare**: export WAV and A/B it against the reference (LUFS, crest factor, stereo
  width, brightness, 6-band balance) with concrete suggestions. Iterate.
- **See FL**: screenshots of FL's monitor come back as images, so Claude can check its work.
- **Anything else** the FL scripting API offers, through `fl_api_call`.

Try prompts like:
> "Make a 2-minute lo-fi track in F minor at 82 BPM with Rhodes, soft drums and a sub."
>
> "Use https://youtube.com/watch?v=… as a reference. Match its key, tempo and energy, but write something original."
>
> "Compare my render to the reference drop and fix the biggest problem."

## How it works

```
Claude ──MCP──► fl-studio-mcp server ──TCP──► bridge daemon ──loopMIDI──► FL controller script
                                                  │
                                                  └─ GUI automation, note bridge, render, audio analysis
```

FL's scripting API covers transport, mixer, channels, plugin parameters and presets. A small
daemon handles what the API can't: writing notes via generated piano-roll scripts, switching FLEX
packs, cloning channels, saving and rendering (by template-matching FL's UI), plus downloads,
stem separation and analysis. Details: [docs/architecture.md](docs/architecture.md).

## Quick start (Windows 10/11, FL Studio 2025)

```powershell
git clone https://github.com/CinnamonTwists/FL-Studio-Claude-Integration
cd FL-Studio-Claude-Integration
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -DryRun     # preview
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -ConfigureClaudeDesktop
```

Then, once:
1. **loopMIDI**: create ports named exactly `FLStudioMCP RX` and `FLStudioMCP TX`.
2. **FL Studio** (restart it first) > Options > MIDI Settings: input `FLStudioMCP RX` → Enable,
   Controller type `FLStudioMCP`, Port 10; output `FLStudioMCP TX` → Port 10; keep output
   `FLStudioMCP RX` off port 10.
3. Restart Claude Desktop.

Each session: `powershell -ExecutionPolicy Bypass -File "$HOME\.claude\skills\fl-studio\scripts\preflight.ps1" -StartFL`,
then ask Claude to make music. Optional extras: `-Stems` for Demucs (install CUDA PyTorch first for GPU
speed) and the [bgutil PO-token provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) cloned to
`~\Projects\` if YouTube downloads return 403. Full guide: [docs/setup-windows.md](docs/setup-windows.md).

## The 14 studio tools

| Tool | Does |
|---|---|
| `fl_api_call` | Call any FL scripting-API function (batched) |
| `fl_flex_list_packs` / `fl_flex_select_pack` | List / switch FLEX preset packs |
| `fl_flex_list_presets` / `fl_flex_load_preset` | List / load presets (verified by name) |
| `fl_clone_channel` | More instances of an existing instrument (the API can't load plugins) |
| `fl_route_channel` | Channel → mixer insert (+ name) |
| `fl_set_stereo_separation` | Widen/narrow a mixer track (negative = wider) |
| `fl_arm_note_bridge` | Arms automatic note writing (once per FL session) |
| `fl_save_project` / `fl_render_wav` | Save; export WAV and wait for completion |
| `fl_screenshot` | Image of FL's monitor |
| `fl_reference_analyze` | Reference analysis from file or URL |
| `fl_compare_to_reference` | Measured A/B of your render vs the reference |

Plus the 67 upstream tools (transport, mixer, channels, piano-roll notes, plugin parameters,
mix doctor, gain staging, routing, colors, markers, MIDI export, …).

## Limits

FL's API can't load plugins or samples, place playlist clips or insert effects. So songs live in
one long pattern, sounds come from cloned FLEX instances, and EQ/FX must be loaded by you (then
Claude can control them). GUI automation assumes FL's default UI scale. Claude can't hear: the
metrics are measurements, not taste.

## Safety

The GUI tools send real mouse/keyboard input, so they only act when FL is the foreground app,
wait for dialogs before typing, stop at FL popups instead of guessing, revert unexpected mixer
changes, and never screenshot other monitors. Why each guard exists: [docs/lessons-learned.md](docs/lessons-learned.md).

Reference downloads are for private analysis only; respect the source's terms and don't
redistribute audio. The skill writes original music *in the style of* a reference rather than copying it.

## Credits & license

- MCP server foundation: [rosasynthesiz/flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp) (MIT). Its
  license is kept in [`flstudio-mcp/LICENSE`](flstudio-mcp/LICENSE).
- Built with [Claude Code](https://claude.com/claude-code).
- Not affiliated with Image-Line (FL Studio, FLEX) or Anthropic.

This repository's additions are released under the [MIT License](LICENSE).
