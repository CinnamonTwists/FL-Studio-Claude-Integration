# Troubleshooting

| Symptom | Cause -> fix |
|---|---|
| `fl_ping`: "No heartbeat received" | Controller not loaded or ports mismatched. Check FL MIDI Settings (setup.md step 5). View > Script output should show `[FLStudioMCP] Ready`. If FL was just restarted, look for the RX output auto-paired onto port 10. loopMIDI's window shows which port carries traffic: heartbeat on RX instead of TX = that pairing bug. |
| `fl_ping`: "Heartbeat is Ns old" | FL restarted under a running daemon: restart the daemon (preflight). |
| "Cannot reach the fl-studio-mcp daemon" | Daemon not running: run preflight (starts it minimized). |
| Server process dies at start / "No module named fl_studio_mcp" | A pip install failed half-way (locked daemon exe). Stop daemon, `pip install --no-deps -e <repo>`. |
| Notes don't appear | Note bridge not armed this FL session -> `fl_arm_note_bridge`. Or FL wasn't foreground (result has `sent_hotkey: false`). |
| Notes land in the wrong instrument | Always `fl_arrange_select_channel` right before each write; the patched controller closes the piano roll so it re-opens on that channel. |
| `fl_flex_select_pack` "FLEX window not found" | Another window covers FLEX, FL UI scale isn't default, or the plugin isn't FLEX. Call `fl_screenshot` and look. |
| FLEX preset name lags | FLEX renames its channel ~0.5 s after a step; tools already wait. When reading with `fl_api_call`, wait first. |
| `fl_render_wav` "dialog open" / "Save dialog did not appear" | An FL dialog was already open, or FL was busy. Nothing was typed. Close dialogs (`fl_screenshot` to see), retry. |
| Render is far quieter than expected | Check the Master fader (`fl_api_call mixer.getTrackVolume 0`, 0.8 = 0 dB) and the master chain. GUI tools now run under a mixer guard that reverts stray fader moves and reports them as `mixer_guard`. |
| YouTube download 403 | PO-token server not running/installed (auto-start looks in `~\Projects\bgutil-ytdlp-pot-provider`); update yt-dlp (`pip install -U yt-dlp`). |
| Tempo estimate looks half/double | Check `tempo_candidates`; rerun `fl_reference_analyze` with `bpm=` to force the grid. |
| Key says X major but chords say otherwise | The estimator confuses relative/dominant keys; trust the chord loop + bass roots (e.g. B-heavy profile with A/B/C#m/E chords = E major, not B major). |
| `fl_save_project` "waiting on an FL dialog: Project size warning" | A plugin holds big data (e.g. an Edison recording). Screenshot it; if the plugin is an accident, tick its Remove box and click "Remove selected", otherwise "Don't remove selected". |
| Unexpected Song mode / record armed / Edison on the Master | Stray keystrokes reached FL's main window (L = pattern/song, R = record). Fix via `fl_api_call`: `transport.getLoopMode` (0 = pattern) / `setLoopMode`, `transport.isRecording` / `record`; check `fl_plugin_list(0)`; re-write parts from the song spec to purge recorded notes. |
| Controller edits don't take effect | FL only reliably reloads controller scripts on restart (save first; re-arm the note bridge afterwards). |
