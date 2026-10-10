# FL scripting API via `fl_api_call`

`fl_api_call(module, fn, args)` or `fl_api_call(module, batch=[[fn, [args]], ...])` calls FL's
controller-scripting API directly (modules: plugins, channels, mixer, patterns, playlist,
transport, ui, general, device, arrangement, midi). Use it when no dedicated tool exists.

## Gotchas

- **Reads lag writes** by ~0.3-0.5 s (FL updates its UI asynchronously). Wait before verifying.
- **SysEx size limit** (~1.5 KB per reply): keep batches small (<= 8 short calls) and avoid
  returning big strings.
- Indices are 0-based. Channel index != the number FL shows in the channel rack (that box shows the
  target mixer insert).
- Slot -1 means "the channel's generator" in plugin calls; mixer effects use (track, slot 0-9).

## Verified calls (FL 2025.2.5)

| Goal | Call |
|---|---|
| Channel count / name | `channels.channelCount()`, `channels.getChannelName(ch)` |
| Select channel(s) | `channels.selectOneChannel(ch)`, `channels.selectChannel(ch, 1)`, `channels.isChannelSelected(ch)` |
| Open/close a plugin window | `channels.showEditor(ch, 1 / 0)` |
| Route channel to mixer insert | `channels.setTargetFxTrack(ch, track)`, `channels.getTargetFxTrack(ch)` |
| Mixer name / volume / pan | `mixer.setTrackName(t, name)` ("" resets), `mixer.getTrackVolume(t)` (0.8 = 0 dB), `mixer.setTrackVolume(t, v)`, `mixer.getTrackPan(t)` |
| Stereo width | `mixer.setTrackStereoSep(t, v)`: **negative = wider** (measured), positive = narrower |
| Track count | `mixer.trackCount()` |
| Plugin identity | `plugins.isValid(ch, -1)`, `plugins.getPluginName(ch, -1)`; effects `(track, slot)` |
| Plugin params | `plugins.getParamCount(i, slot)`, `plugins.getParamName(p, i, slot)`, `plugins.getParamValueString(p, i, slot)`, `plugins.setParamValue(value01, p, i, slot)` (note arg order: value first) |
| Presets (FLEX etc.) | `plugins.getPresetCount(ch, -1)`, `plugins.getName(ch, -1, 6, i)` (6 = FPN_Preset), `plugins.nextPreset(ch, -1)`, `plugins.prevPreset(ch, -1)` |
| Windows / focus | `ui.showWindow(wid)`, `ui.setFocused(wid)`; wid: 0 mixer, 1 channel rack, 2 playlist, 3 piano roll, 4 browser |

## Master chain in the Default template

Master slot 9 = **Emphasizer** (FL 2025 one-knob mastering). Params: 0 Input gain (0..1 = 0..+24 dB,
linear), 1 Emphasis (%), 2 Clipping (Hard/Soft), 3 Level matching, 4 Bypass, 5 Output gain (1.0 = 0 dB).
Driving Input gain is the loudness control: +16.8 dB (0.7) took a -27 LUFS mix to about -8 LUFS.

## What the API cannot do (use the studio tools or the user)

Load plugins or samples, place playlist clips, open arbitrary menus, switch FLEX packs
(-> `fl_flex_select_pack`), clone channels (-> `fl_clone_channel`), save/render
(-> `fl_save_project`, `fl_render_wav`), run piano-roll scripts (-> note bridge).
