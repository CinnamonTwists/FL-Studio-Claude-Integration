# Architecture

```
 Claude Desktop / Claude Code
        │  MCP (stdio)
        ▼
 fl-studio-mcp server  ── 81 tools (67 upstream + 14 studio tools)
        │  newline-delimited JSON over TCP 127.0.0.1:9787
        ▼
 bridge daemon (a normal user process)
   ├─ op "call"        ──SysEx over loopMIDI "FLStudioMCP RX"──►  FL controller script
   │                   ◄──heartbeat + replies on "FLStudioMCP TX"──  (device_FLStudioMCP.py)
   ├─ op "apply_notes" → writes MCP_Apply.pyscript, focuses FL, sends Ctrl+Alt+Y
   └─ op "desktop"     → GUI automation, screenshots, render, reference pipeline
```

## Why a daemon

The Microsoft Store build of Claude Desktop launches MCP servers in a sandbox where Windows
MIDI input never arrives and desktop input/GPU jobs are unreliable. Everything that needs MIDI,
the keyboard/mouse, the screen or heavy local work runs in the daemon, which the user starts
normally (the skill's preflight does it, minimized). The server just forwards over TCP, so the
same tools work under any MCP client.

## Three layers of control

1. **FL scripting API** (controller script, via SysEx): transport, mixer, channels, plugin
   parameters, presets, markers. Upstream tools plus the generic `fl_api_call`, which exposes any
   function of FL's controller-scripting modules.
2. **Note bridge**: FL's piano-roll scripts can't read files, so the daemon *generates* a
   `.pyscript` with the notes baked in and fires "Run last script again". Arming it once per FL
   session (`fl_arm_note_bridge`) is now automated.
3. **Desktop automation** (`desktop/` package): for what the API can't reach. Switching FLEX preset
   packs, cloning channels (Alt+C), saving, Export-WAV rendering. It finds UI elements by
   template matching (normalized cross-correlation of small PNGs) on FL's monitor only, so windows
   can open anywhere.

## Studio tools and where they run

| Tool | Runs in | Mechanism |
|---|---|---|
| `fl_api_call` | server → controller | generic API call (`api_call` controller op) |
| `fl_flex_list_presets`, `fl_flex_load_preset` | server → controller | `plugins.getName(FPN_Preset)`, next/prev preset, verified via the channel name FLEX sets |
| `fl_route_channel`, `fl_set_stereo_separation` | server → controller | `channels.setTargetFxTrack`, `mixer.setTrackStereoSep` |
| `fl_flex_list_packs` | daemon | scans user + factory FLEX pack folders |
| `fl_flex_select_pack` | daemon (GUI) | opens the FLEX window, matches its Library tab, clicks the pack row (scrolls for packs below the fold) |
| `fl_clone_channel` | daemon (GUI) | focuses the channel rack, Alt+C, diffs channel names to report new channels |
| `fl_arm_note_bridge` | daemon (GUI) | empties the apply script, opens the piano roll menu > Tools > Scripts > MCP_Apply |
| `fl_save_project` | daemon (GUI) | Ctrl+S; fills FL's Save-as dialog for untitled projects |
| `fl_render_wav` | daemon (GUI) | Ctrl+R → waits for the Save dialog → path → Start → waits for the file |
| `fl_screenshot` | daemon | JPEG of FL's monitor, returned as an MCP image |
| `fl_reference_analyze` | daemon | yt-dlp (+ PO-token server) → Demucs stems → librosa analysis |
| `fl_compare_to_reference` | daemon | LUFS, peak, crest, stereo width, centroid, 6-band balance A/B |

## Safety design

GUI automation sends real input, so the failure modes are "typed into the wrong place" and
"clicked something unintended". Each was observed during development and has a guard:

- **Foreground check by process.** Input is sent only when the foreground window belongs to FL's
  process; otherwise the tool raises. The upstream hotkey trigger now follows the same rule.
- **Wait for the target before typing.** Render waits for the export Save dialog to be in front
  before typing a path; if it never appears, nothing is typed.
- **Popup awareness.** Any extra top-level FL window (Windows dialogs or FL's own popups like
  "Project size warning") blocks save/render with a clear error instead of a guess.
- **Mixer guard.** Every GUI action snapshots all mixer track volumes/pans and restores anything
  that changed unexpectedly, reporting it as `mixer_guard`.
- **Arming can't overwrite.** The apply script is emptied (append mode, no notes) before arming.
- **Screenshots never leave FL's monitor.**

## Known limits

FL's API can't load plugins or samples, place playlist clips, or insert effects. Songs are
written into one long pattern; sounds come from cloned FLEX instances; EQ/FX must be loaded by the
user (then they're controllable). GUI templates assume FL's default UI scale and theme.
