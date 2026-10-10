# Setup / repair: Claude <-> FL Studio (Windows)

Read this when preflight fails, on a new machine, or after reinstalling anything.
Ask before installing software; back up `claude_desktop_config.json` before editing it.
Source + installer: https://github.com/CinnamonTwists/FL-Studio-Claude-Integration
(`scripts/install.ps1 -DryRun` shows what it would do).

## The chain

```
Claude (Desktop/Code) --stdio--> fl-studio-mcp server --TCP 127.0.0.1:9787--> daemon
   --loopMIDI "FLStudioMCP RX"--> FL controller script (device_FLStudioMCP.py)
   <--loopMIDI "FLStudioMCP TX"-- (heartbeat + replies)
daemon also: writes MCP_Apply.pyscript + sends Ctrl+Alt+Y (note bridge), drives the GUI,
             runs reference downloads / stem separation / analysis
```

## Where things live (and how to find them)

| Piece | How to find it |
|---|---|
| FL install folder | registry `HKCU\Software\Image-Line\Shared\Paths` -> "Install path" (e.g. `C:\Program Files\Image-Line\FL Studio 2025`) |
| FL **user data** folder | "Shared data" in the same key + `FL Studio` (Options > File settings shows it). Often `Documents\Image-Line\FL Studio`, but can be anywhere, e.g. a custom `C:\FL\`. Don't assume Documents: it may be OneDrive-redirected or stale. The server resolves this automatically. |
| Controller script | `<user data>\Settings\Hardware\FLStudioMCP\device_FLStudioMCP.py` (copy of the repo's `flstudio-mcp\fl_controller\FLStudioMCP\`) |
| Note-bridge script | `<user data>\Settings\Piano roll scripts\MCP_Apply.pyscript` (generated) |
| FLEX packs | user `<shared data>\FLEX\Packs`, factory `<install>\Data\Patches\Packs\FLEX\Packs` |
| Claude Desktop config | standard: `%APPDATA%\Claude\claude_desktop_config.json`; Microsoft Store build: `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json` |
| fl-studio-mcp executables | `<python>\Scripts\fl-studio-mcp.exe`, `fl-studio-mcp-daemon.exe` |
| YouTube PO-token server (reference downloads) | `~\Projects\bgutil-ytdlp-pot-provider` (or `FLSTUDIO_MCP_BGUTIL_HOME`); auto-started by fl_reference_analyze |
| Reference audio + analyses | `~\FL References\<title>\` (or `FLSTUDIO_MCP_REFERENCE_DIR`) |

## Fresh install (condensed)

1. Prereqs (winget): `Python.Python.3.12` (user scope, PrependPath), `TobiasErichsen.loopMIDI`,
   `Gyan.FFmpeg`, `Git.Git`, `OpenJS.NodeJS.LTS` (yt-dlp uses Node for YouTube's JS challenges).
2. loopMIDI: create ports named exactly `FLStudioMCP RX` and `FLStudioMCP TX`.
3. `python -m pip install -e "<repo>\flstudio-mcp[audio,studio]"` (add `stems` for Demucs; install CUDA
   torch first for GPU speed: `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124`).
   Stop the daemon first or pip can't replace `fl-studio-mcp-daemon.exe` (it then leaves the package
   uninstalled -- reinstall with `--no-deps -e`).
4. Copy the controller script into `<user data>\Settings\Hardware\FLStudioMCP\`.
5. FL > Options > MIDI Settings (F10):
   - Input `FLStudioMCP RX`: Enable, Controller type `FLStudioMCP`, Port `10`.
   - Output `FLStudioMCP TX`: Port `10` (same number).
   - Output `FLStudioMCP RX`: any port EXCEPT 10 (e.g. 2). FL can auto-pair a same-named output with
     a scripted input after a restart; on port 10 it steals the heartbeat.
   - FL only scans controller scripts at startup -- restart FL after adding/editing the script.
   - Port fields respond to the mouse wheel (one notch = 1).
6. Claude Desktop config `mcpServers` (merge, keep other keys), using the FULL exe path (the Microsoft
   Store `python` alias can shadow PATH):
   ```json
   "fl-studio": {"command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\fl-studio-mcp.exe",
                 "env": {"FLSTUDIO_MCP_TRANSPORT": "tcp"}}
   ```
   Restart Claude Desktop fully (tray icon > Quit). Claude Code: `claude mcp add fl-studio -e FLSTUDIO_MCP_TRANSPORT=tcp -- <exe>`.
7. Start the daemon (preflight does it, minimized). Then `fl_ping` -> alive.

## Windows quirks worth knowing

- The Microsoft Store `python.exe` alias in WindowsApps can shadow real Python in new terminals.
  Fix: Settings > Apps > Advanced app settings > App execution aliases > turn off the "python" entries.
- Windows PowerShell 5.1 strips inner quotes from JSON passed to native exes (pass JSON in files),
  writes a BOM with `Set-Content -Encoding utf8`, and `>` redirection writes UTF-16.
- High-DPI: GUI tools use physical pixels and assume FL's default UI scale.
