"""Studio tools: sound selection (FLEX), channel setup, note-bridge arming,
save/render, screenshots, generic FL API access, and the reference-track
pipeline.

GUI-driven and heavy tools run in the daemon via ``bridge.desktop(...)`` so they
work under sandboxed MCP clients. They only ever send input to FL Studio and
refuse to act if FL can't be brought to the foreground.
"""

from __future__ import annotations

import base64
from typing import Annotated, Any, List, Optional

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from pydantic import Field

from .. import flex
from ..connection import get_bridge

_GUI = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}
_READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def register(mcp: FastMCP) -> None:
    # -- generic API ---------------------------------------------------------------

    @mcp.tool(annotations={"title": "Call any FL scripting API function", "readOnlyHint": False,
                           "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
    def fl_api_call(
        module: Annotated[str, Field(description="FL scripting module: plugins, channels, mixer, patterns, playlist, transport, ui, general, device, arrangement, midi.")],
        fn: Annotated[str, Field(description="Function name, e.g. 'getChannelName', 'setTrackStereoSep'.")] = "",
        args: Annotated[Optional[List[Any]], Field(description="Positional arguments.")] = None,
        batch: Annotated[Optional[List[List[Any]]], Field(description="Instead of fn/args: [[fn, [args]], ...] on the same module, one round trip.")] = None,
    ) -> dict:
        """Escape hatch to FL Studio's Python scripting API (the same API MIDI
        controller scripts use; see FL's 'MIDI scripting' docs). Use it for
        anything the dedicated tools don't cover -- e.g. channels.setTargetFxTrack,
        mixer.setTrackStereoSep, plugins.getParamName, ui.showWindow. Results that
        aren't JSON-safe come back as repr strings. Reads can lag FL's UI by
        ~0.5 s right after a write."""
        params = {"module": module, "batch": batch} if batch else {"module": module, "fn": fn, "args": args or []}
        return get_bridge().call("api_call", params)

    # -- FLEX -------------------------------------------------------------------------

    @mcp.tool(annotations={**_READ, "title": "List FLEX preset packs"})
    def fl_flex_list_packs() -> dict:
        """Installed FLEX preset packs (user + factory), in FLEX's Library order."""
        return get_bridge().desktop("flex_list_packs")

    @mcp.tool(annotations={**_GUI, "title": "Select a FLEX pack"})
    def fl_flex_select_pack(
        channel: Annotated[int, Field(ge=0, description="Channel-rack index of a FLEX instance.")],
        pack: Annotated[str, Field(description="Pack name from fl_flex_list_packs.")],
        keep_open: Annotated[bool, Field(description="Leave the FLEX window open afterwards.")] = False,
    ) -> dict:
        """Switch a FLEX instance to another preset pack (opens its window and
        clicks the pack in the Library -- FL's API can't do this) and return the
        pack's preset names. Then load one with fl_flex_load_preset. Closes any
        other open FLEX windows first."""
        return get_bridge().desktop("flex_select_pack", {"channel": channel, "pack": pack, "keep_open": keep_open})

    @mcp.tool(annotations={**_READ, "title": "List FLEX presets"})
    def fl_flex_list_presets(channel: Annotated[int, Field(ge=0)]) -> dict:
        """Presets in the FLEX instance's currently selected pack, plus the loaded
        preset (FLEX names its channel after the loaded preset)."""
        b = get_bridge()
        flex.require_flex(b, channel)
        names = flex.preset_names(b, channel)
        return {"channel": channel, "current": flex.current_preset(b, channel, settle=0),
                "count": len(names), "presets": names}

    @mcp.tool(annotations={**_GUI, "openWorldHint": False, "title": "Load a FLEX preset"})
    def fl_flex_load_preset(
        channel: Annotated[int, Field(ge=0)],
        preset: Annotated[str, Field(description="Exact preset name from the selected pack (case-insensitive).")],
    ) -> dict:
        """Load a preset from the FLEX instance's selected pack (steps with
        next/prev preset, verified by name). Switch packs first with
        fl_flex_select_pack if needed."""
        b = get_bridge()
        flex.require_flex(b, channel)
        return flex.load_preset(b, channel, preset)

    # -- channels / mixer -------------------------------------------------------------

    @mcp.tool(annotations={**_GUI, "title": "Clone a channel"})
    def fl_clone_channel(
        channel: Annotated[int, Field(ge=0, description="Channel to clone (e.g. a FLEX instance to get more instruments).")],
        count: Annotated[int, Field(ge=1, le=16)] = 1,
    ) -> dict:
        """Clone a channel-rack channel (FL's Alt+C) -- the way to add more
        instances of an instrument that's already in the project, since the API
        can't load plugins. Returns the new channel indices. Route each clone to
        its own mixer track with fl_route_channel."""
        return get_bridge().desktop("clone_channel", {"channel": channel, "count": count})

    @mcp.tool(annotations={"title": "Route a channel to a mixer track", "readOnlyHint": False,
                           "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    def fl_route_channel(
        channel: Annotated[int, Field(ge=0)],
        mixer_track: Annotated[int, Field(ge=0, description="Mixer insert (0 = Master).")],
        track_name: Annotated[Optional[str], Field(description="Optional new name for the mixer track.")] = None,
    ) -> dict:
        """Send a channel-rack channel to a mixer insert, optionally naming it."""
        b = get_bridge()
        flex.api(b, "channels", "setTargetFxTrack", channel, mixer_track)
        if track_name:
            flex.api(b, "mixer", "setTrackName", mixer_track, track_name)
        return {"ok": True, "channel": channel, "mixer_track": mixer_track, "track_name": track_name}

    @mcp.tool(annotations={"title": "Set mixer stereo separation", "readOnlyHint": False,
                           "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    def fl_set_stereo_separation(
        track: Annotated[int, Field(ge=0)],
        value: Annotated[float, Field(ge=-1.0, le=1.0, description="NEGATIVE = wider (measured), positive = narrower/merged, 0 = neutral.")],
    ) -> dict:
        """Widen or narrow a mixer track (pads/chords wider, bass/kick mono)."""
        flex.api(get_bridge(), "mixer", "setTrackStereoSep", track, value)
        return {"ok": True, "track": track, "stereo_sep": value}

    # -- note bridge / project ---------------------------------------------------------

    @mcp.tool(annotations={**_GUI, "title": "Arm the piano-roll note bridge"})
    def fl_arm_note_bridge() -> dict:
        """Run MCP_Apply once from the piano roll's Tools > Scripts menu so that
        fl_write_piano_roll_notes can apply notes automatically. Needed once per
        FL session (after every FL restart); call it if notes don't appear."""
        return get_bridge().desktop("arm_note_bridge")

    @mcp.tool(annotations={**_GUI, "title": "Save the FL project"})
    def fl_save_project(
        name: Annotated[Optional[str], Field(description="Project name, used only if the project has never been saved.")] = None,
    ) -> dict:
        """Save (Ctrl+S). For an untitled project, fills FL's Save-as dialog with
        ``name`` (FL creates a project folder under its Projects directory)."""
        return get_bridge().desktop("save_project", {"name": name}, timeout=60)

    @mcp.tool(annotations={**_GUI, "title": "Render to WAV"})
    def fl_render_wav(
        path: Annotated[Optional[str], Field(description="Absolute .wav path. Default: '<project> render N.wav' next to the saved project.")] = None,
    ) -> dict:
        """Export WAV of what FL would play now (PAT mode = current pattern, SONG
        mode = playlist) and wait until the file is complete. Use the WAV with
        fl_compare_to_reference."""
        return get_bridge().desktop("render_wav", {"path": path}, timeout=900)

    @mcp.tool(annotations={**_READ, "openWorldHint": True, "title": "Screenshot FL Studio"})
    def fl_screenshot(max_width: Annotated[int, Field(ge=400, le=2560)] = 1600) -> Image:
        """Screenshot of the monitor FL Studio is on (other monitors are never
        captured). Use it to check what FL is showing when a GUI step fails."""
        r = get_bridge().desktop("screenshot", {"max_width": max_width}, timeout=30)
        return Image(data=base64.b64decode(r["jpeg_b64"]), format="jpeg")

    # -- reference pipeline -------------------------------------------------------------

    @mcp.tool(annotations={**_GUI, "title": "Analyze a reference track"})
    def fl_reference_analyze(
        source: Annotated[str, Field(description="Audio file path, or a URL (YouTube etc.) to download with yt-dlp.")],
        stems: Annotated[bool, Field(description="Separate stems with Demucs first (much better chords/bass/drums; GPU if available).")] = True,
        bpm: Annotated[Optional[float], Field(description="Force the beat-grid tempo if the estimate is a half/double.")] = None,
        out_dir: Annotated[Optional[str], Field(description="Where to keep audio + analysis (default ~/FL References/<title>).")] = None,
    ) -> dict:
        """Deep musical analysis of a reference: tempo candidates, key
        candidates, chord per bar + most common 4-bar loop, bass roots, energy
        sections (find drops/breakdowns), drum hit grid of the loudest section,
        tonal balance. Use it as a STYLE reference -- write original parts in the
        same key/tempo/energy rather than copying melodies. Downloads are for
        private reference only; respect the source's terms."""
        return get_bridge().desktop("reference_analyze",
                                    {"source": source, "stems": stems, "bpm": bpm, "out_dir": out_dir},
                                    timeout=1800)

    @mcp.tool(annotations={**_READ, "title": "Compare a mix to a reference"})
    def fl_compare_to_reference(
        mix_path: Annotated[str, Field(description="Rendered mix WAV (from fl_render_wav).")],
        reference_path: Annotated[str, Field(description="Reference WAV (e.g. 'wav' from fl_reference_analyze).")],
        mix_start: Annotated[Optional[float], Field(description="Section start (s) in the mix; omit both to auto-pick the loudest window.")] = None,
        mix_end: Optional[float] = None,
        ref_start: Annotated[Optional[float], Field(description="Section start (s) in the reference.")] = None,
        ref_end: Optional[float] = None,
        window_sec: Annotated[float, Field(gt=2)] = 20.0,
    ) -> dict:
        """Measured A/B of two sections (e.g. both drops): LUFS, peak, crest
        factor, stereo width, brightness and 6-band tonal balance, with
        mix-minus-reference diffs and hints. Iterate: adjust -> fl_render_wav ->
        compare again."""
        mr = [mix_start, mix_end] if mix_start is not None and mix_end is not None else None
        rr = [ref_start, ref_end] if ref_start is not None and ref_end is not None else None
        return get_bridge().desktop("compare_mix", {"mix": mix_path, "reference": reference_path,
                                                    "mix_range": mr, "ref_range": rr,
                                                    "window_sec": window_sec}, timeout=600)
