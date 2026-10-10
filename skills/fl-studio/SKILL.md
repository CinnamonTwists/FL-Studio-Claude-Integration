---
name: fl-studio
description: Make music in FL Studio on Windows by driving the fl-studio MCP server (flstudio-mcp + bridge daemon + loopMIDI) - pick FLEX sounds, write parts into the piano roll, arrange, mix and master, render WAVs, and analyze a reference song or YouTube link to match its key, tempo, energy arc and tonal balance. Use this whenever the user mentions FL Studio or FL, making a beat, track, song, loop, melody, chord progression or drop, FLEX presets or the piano roll, mixing/mastering/rendering their project, using a song or YouTube link as a reference, or when the Claude-FL connection (loopMIDI, daemon, fl_ping, MCP_Apply, MIDI settings) needs setup or repair - even if they never say "MCP".
---

# FL Studio production with Claude

Claude controls FL Studio through ~80 `fl_*` MCP tools. Most go through FL's scripting
API (transport, mixer, channels, notes). A daemon process adds what the API can't do:
GUI automation (FLEX packs, cloning channels, arming the note bridge, save, render),
screenshots, and a reference-audio pipeline (download, Demucs stems, analysis, A/B).

Paths, install steps and machine quirks: `references/setup.md`. Symptom -> fix table:
`references/troubleshooting.md`. Read them only when something is off.

## 1. Preflight (start of every session)

- **With a shell (Claude Code):** `powershell -ExecutionPolicy Bypass -File <skill>/scripts/preflight.ps1`
  (add `-StartFL` to launch FL). It starts loopMIDI and the daemon if needed and ends with an
  end-to-end `fl_ping`. Call tools from the shell with `scripts/mcp_call.py`
  (`list`, `schema <tool>`, `call <tool> @args.json`, `run calls.json`).
- **In Claude Desktop:** call `fl_ping`. If it isn't alive, tell the user the specific fix from
  troubleshooting.md (usually: start the daemon, or FL's MIDI port pairing after a restart).
- **Then call `fl_arm_note_bridge` once per FL session** (again after any FL restart). Note writing
  works by generating a piano-roll script and firing FL's "run last script" hotkey; FL only knows
  which script that is after it has been run once from the menu, and this tool does that click
  (safely: it empties the script first so arming never rewrites a pattern).
- If FL just launched, a Welcome dialog may be open: `fl_screenshot` shows it. The **Default
  (Basic with limiter)** template is a good base: 808 Kick/Clap/HiHat/Snare on channels 0-3,
  one FLEX on channel 4, Emphasizer mastering on the Master (slot 9).

## 2. Reference track (when the user gives a song or link)

`fl_reference_analyze(source=<URL or file>)` downloads (yt-dlp), splits stems on the GPU and
returns: tempo candidates, key candidates, chord per bar + the most common 4-bar loop, bass
roots, an energy map of sections, the drum hit grid of the loudest 8 bars (16th steps) and
6-band tonal balance. ~30 s for a 5-minute song.

How to read it:
- Tempo: the top candidates are often half/double of each other. Choose by genre feel and the
  bar timing; rerun with `bpm=` if the grid is clearly wrong.
- Key: the key estimate confuses relative and dominant keys. Decide the tonic from the chord loop
  and bass roots (e.g. a B-heavy profile over A-B-C#m-E harmony is E major / C# minor).
- Sections: "high" runs are drops/choruses, "low" runs intros/breakdowns -> your arrangement map.
- Use the reference for **style**: key, tempo, energy arc, rhythmic feel, sound palette, tonal
  balance. Write an original progression variant and melody rather than transcribing theirs -
  it makes better, original music and avoids copying someone's song. Ignore vocals unless asked.
- Downloads are for private reference; don't redistribute the audio.

## 3. Sounds (FLEX)

The API can't load plugins, so melodic sounds come from FLEX instances:
1. Plan roles first (sub, chords, lead, pad, keys, accent) - fewer, well-chosen parts mix better.
2. `fl_clone_channel(channel=4, count=N)` -> new channel indices.
3. `fl_route_channel(channel, mixer_track, track_name)` for each, so every part gets its own insert.
4. `fl_flex_select_pack(channel, pack)` -> that pack's preset names; then
   `fl_flex_load_preset(channel, preset)` (verified by name).
`references/flex-sounds.md` maps roles to packs and presets that worked. Tell the user what you
picked and offer alternatives - sound choice is taste.

## 4. Compose

- **One long pattern holds the whole song.** The API can't place playlist clips; PAT mode plays
  and renders the current pattern, so a 48-bar pattern is a 48-bar song. Mark sections with
  `fl_arrange_add_marker` and set `fl_set_tempo`.
- Notes: `{pitch (MIDI, 60 = middle C, which FL labels C5), time_bars, length_bars, velocity 0-1}`,
  times in bars from the pattern start (0.0625 = a 16th).
- For each part: `fl_arrange_select_channel(ch)` **immediately before**
  `fl_write_piano_roll_notes(notes, mode="replace")`. The piano roll only retargets when it
  re-opens, and the select tool closes it for exactly that reason.
- **With a shell, generate notes in code**: build a song spec JSON and run
  `scripts/write_song.py song.json` (sets tempo, markers, arms, writes every part). A full song
  is 1000-2000 notes; generating them programmatically is faster, repeatable and keeps them out
  of the conversation. `assets/examples/future_bass_sketch.py` is a complete worked example
  (chord voicings, progression iteration, 16th-step drum grids, build ramps, drop stabs).
- In Desktop, write part by part with the tools; keep each call to a section or loop.
- Craft that paid off: voice-led chords in one octave band; bass on roots (MIDI 28-45);
  velocity accents (downbeats louder, ghost 16ths soft); builds with rising velocity and an
  accelerating snare roll; a half-bar of silence before the drop; vary the second half of a
  repeated phrase.
- Check your work: the channel rack previews in `fl_screenshot` show every part's shape;
  play a section with `fl_set_song_position(beats=(bar-1)*4)` + `fl_play` / `fl_stop`.

## 5. Mix and master (measure, change, re-measure)

1. Organise: `fl_set_mixer_name`, `fl_set_track_color` / `fl_set_channel_color`,
   `fl_group_tracks` (drum bus). Names matter: the mix doctor infers roles from them.
2. Play the loudest section, then `fl_diagnose_mix` and `fl_gain_stage`. Apply with
   `fl_apply_mix_fix(kind="trim_volume", track, target_db)`, using judgment: don't trim a bus
   *and* all its sources (double cut); ignore large boosts on parts that are quiet on purpose.
3. Width: `fl_set_stereo_separation(track, value)` - negative widens (measured). Widen
   chords/pads; keep sub and kick centered.
4. Loudness: drive the Master's Emphasizer input gain,
   `fl_plugin_set_param(track=0, slot=9, param=0, value)` where 0..1 = 0..+24 dB.
   Aim for roughly -7 to -9 LUFS on drops for EDM; don't chase a hyper-limited reference
   (the ILLENIUM reference measured -2.4 LUFS).
5. `fl_save_project` -> `fl_render_wav` -> `fl_compare_to_reference(mix_path, reference_path)`
   (auto-picks the loudest window of each, or pass section times). Iterate 2-4 rounds.
   Expect trade-offs: the Emphasizer holds overall level, so lifting the lows pulls the mids down.
6. When the remaining gaps are tonal (band diffs >= 2 dB that faders can't fix), say so: the API
   can't insert an EQ. Ask the user to load Fruity Parametric EQ 2 on the track, then use
   `fl_apply_eq_intent` / `fl_plugin_set_param`.

## 6. Safety - why these rules exist

- GUI tools send real mouse and keyboard input. They check that FL's process owns the foreground
  window and refuse otherwise. If you ever drive the GUI yourself from a shell, verify the
  foreground window first: once, a failed focus switch nearly sent keystrokes into a chat app.
- Never type text until the target field/dialog is confirmed in front. Letters typed into FL's
  main window are shortcuts: a file path typed too early once flipped FL to Song mode (L),
  armed recording (R) and loaded an Edison recorder on the Master. The tools now wait for the
  dialog; do the same by hand.
- FL raises its own popups (e.g. "Project size warning", delete confirmations). Save/render stop
  and name them instead of clicking; look (`fl_screenshot`), decide with the user, then answer.
- Screenshots: capture only the monitor FL is on (`fl_screenshot` does). Other monitors
  may show private windows.
- If a GUI tool's result contains `mixer_guard`, a stray click or wheel event moved a fader and the
  guard reverted it - tell the user.
- Confirm before deleting channels, files or projects; when FL shows its own confirmation, read
  it (screenshot) before answering.
- Save before restarting FL (controller-script edits only load on restart), then re-arm.

## 7. Limits to state plainly

Can't load plugins or samples (the user drags them in; clone what exists), can't place playlist clips
(one long pattern instead), can't add EQ/FX plugins (control them once loaded), can't hear the mix
(measurements aren't taste - ask the user to listen). GUI tools assume FL's default UI scale.

## 8. Finish with a short report

Project path, render path, the sounds chosen (pack/preset per part), the structure (sections by
bar), the measured comparison (LUFS, width, brightness, band gaps) and what to listen for, plus
what the user could add next (an EQ on a track, vocals, arranging patterns in the playlist).
