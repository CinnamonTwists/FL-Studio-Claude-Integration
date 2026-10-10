# Lessons learned

Everything below broke at least once while building this, usually silently. Each item lists the
symptom, the cause and what the code or skill now does about it.

## FL Studio

- **The FL user-data folder isn't always `Documents\Image-Line`.** It can be anywhere (here a custom
  `C:\FL\`), and Documents may be OneDrive-redirected with a stale copy. The controller script
  installed into the wrong folder simply never showed up in FL's controller list.
  → Paths are resolved from `HKCU\Software\Image-Line\Shared\Paths` ("Shared data").
- **FL scans controller scripts only at startup**, and "reload script" proved unreliable.
  → Restart FL after controller edits (then re-arm the note bridge).
- **FL auto-pairs a same-named MIDI output with a scripted input after a restart.** The
  `FLStudioMCP RX` *output* landed on the controller's port, so heartbeats went out on RX and
  `fl_ping` saw nothing. loopMIDI's throughput column gave it away.
  → Park the RX output on another port; preflight's error message says so.
- **An open piano roll ignores channel selection.** Every part was written into the same
  instrument, each replacing the last.
  → Selecting a channel closes the piano roll so the next write re-opens it on that channel.
- **FLEX renames its channel to the loaded preset, about 0.5 s late.** That's the only way to read
  the current preset, and immediate reads were off by one.
  → Preset tools wait before reading and verify by name.
- **FLEX pack switching has no API,** and each FLEX window opens cascaded 32 px from the last.
  → Template-match the Library tab; packs below the fold are reached by scrolling to the end.
- **Letters typed into FL's main window are shortcuts.** A file path typed before the export
  dialog opened toggled Song mode (`L`), armed recording (`R`) and loaded an Edison recorder on the
  Master that captured 104 MB before anyone noticed.
  → Render waits for the dialog; save/render refuse while FL popups are open.
- **A master fader once dropped to −17 dB during GUI testing** and couldn't be reproduced.
  → The mixer guard reverts unexpected fader/pan changes around every GUI action.

## Windows

- **SetForegroundWindow fails silently** when the caller isn't in the foreground, and keystrokes go
  to whatever app the user is in (it nearly typed into a chat client).
  → Verify the foreground window's process after focusing; tap Alt / AttachThreadInput to satisfy
  the foreground lock; refuse otherwise.
- **The Microsoft Store Claude Desktop** keeps its config under
  `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\`, and sandboxes MCP servers.
  → Daemon architecture; use the full path to `fl-studio-mcp.exe`.
- **The Store `python.exe` alias** can shadow a real Python install in new terminals.
- **Windows PowerShell 5.1** strips inner quotes from JSON arguments to native programs, writes a
  BOM with `Set-Content -Encoding utf8`, and `>` writes UTF-16.
  → Scripts read JSON with `utf-8-sig`, accept `@file.json`, and write files themselves (`--out`).
- **pip can't replace a running `fl-studio-mcp-daemon.exe`** and then leaves the package
  half-uninstalled. → The installer stops the daemon first.

## Audio analysis

- **Anonymous YouTube downloads return HTTP 403** (proof-of-origin tokens).
  → bgutil PO-token provider (auto-started) + `--js-runtimes node`.
- **Tempo estimates come in half/double pairs**, and key estimation confuses relative and dominant
  keys (it called an E-major song "B major").
  → The analysis reports candidates; decide from the chord loop and bass roots.
- **Stem separation changes everything**: chords from the "other" stem and roots from the "bass"
  stem are far cleaner than from the full mix. Demucs on a 4070-class GPU: ~6 s per song.
- **A sandboxed reference tool can't hear FL's output.**
  → Render to WAV and compare the files (LUFS, crest, width, centroid, band balance).
