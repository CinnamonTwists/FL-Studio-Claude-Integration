# Upstream

This is a modified copy of [rosasynthesiz/flstudio-mcp](https://github.com/rosasynthesiz/flstudio-mcp)
(MIT, see [LICENSE](LICENSE)), based on upstream commit `ba94a6d` (2026-07-03,
"Merge pull request #4 from thunderdew-dawn/upstream-macos-support").

The full diff is in [`../docs/upstream-changes.patch`](../docs/upstream-changes.patch); it applies
cleanly to `ba94a6d` with `git apply`.

## Changes

**Fixes (good upstream candidates)**
- `_paths.py` (new): resolve FL's user-data folder from the registry ("Shared data") and the real
  Documents folder via the Known Folder API, instead of assuming `~/Documents`. Used by the note-bridge
  script location and the plugin/preset library readers.
- Controller `_h_channel_select`: close an open piano roll so it re-opens on the newly selected channel.
  Previously every note write went to whichever channel the piano roll was first opened on.
- `pyscript_trigger.py`: never send Ctrl+Alt+Y unless FL's process owns the foreground window.
- `install_windows.bat`: honour a preset `FL_SETTINGS` for non-standard user-data folders.
- Server instructions: describe the controller location as the FL user-data folder.

**New features**
- Controller `api_call` op: call any function of FL's controller-scripting modules (with batching).
- Daemon `desktop` op + `desktop/` package: focus-verified GUI automation by template matching
  (FLEX pack selection, channel cloning, note-bridge arming, save, render), FL-monitor screenshots,
  popup detection and a mixer guard.
- `flex.py`: FLEX preset listing/loading over the plugin API.
- `music/reference.py`: reference fetch (yt-dlp + PO-token server), Demucs stems, analysis
  (tempo/key candidates, chords per bar, loop, bass roots, sections, drum grid, tonal balance) and
  mix-vs-reference comparison.
- `tools/studio.py`: 14 MCP tools exposing the above.
- `pyproject.toml`: `studio` and `stems` extras.
