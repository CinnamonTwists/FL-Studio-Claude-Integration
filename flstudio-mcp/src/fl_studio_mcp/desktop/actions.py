"""Daemon-side actions: GUI workflows FL's API can't do, plus local heavy jobs.

GUI geometry is measured in physical pixels at FL's default UI scale and found
by template matching (templates/), so it tolerates windows opening anywhere.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from .. import flex, protocol
from .._paths import fl_user_data_dir, flex_pack_dirs
from . import screen
from .screen import DesktopError

ACTIONS: dict = {}

WID_CHANNEL_RACK, WID_PIANO_ROLL = 1, 3     # midi.widChannelRack / widPianoRoll

# FLEX library list geometry relative to the LIBRARY tab template's top-left.
FLEX_ROW_DX, FLEX_ROW0_DY, FLEX_ROW_H = 70, 43, 26.0
FLEX_VISIBLE_ROWS = 20          # rows fully visible above the pack artwork
FLEX_LAST_ROW_DY = 549          # y of the last row once the list is scrolled to the end
FLEX_LIST_DY = 300              # a point inside the list, for wheel scrolling

# Piano roll: menu arrow relative to the toolbar template; menu item offsets from the arrow.
PR_ARROW = (10, 11)
PR_TOOLS = (34, 72)


def action(fn):
    ACTIONS[fn.__name__] = fn
    return fn


def _fail_shot(tag: str) -> str:
    p = Path(os.environ.get("TEMP", ".")) / ("fl_mcp_%s_%d.png" % (tag, int(time.time())))
    try:
        return screen.save_screenshot(str(p))
    except Exception:
        return ""


# -- FLEX ------------------------------------------------------------------------

@action
def flex_list_packs(bridge) -> dict:
    names = {p.stem for d in flex_pack_dirs() for p in d.glob("*.flexpack")}
    packs = sorted(names, key=str.casefold)
    return {"ok": True, "packs": packs, "count": len(packs), "dirs": [str(d) for d in flex_pack_dirs()]}


@action
def flex_select_pack(bridge, channel: int, pack: str, keep_open: bool = False) -> dict:
    channel = int(channel)
    flex.require_flex(bridge, channel)
    packs = flex_list_packs(bridge)["packs"]
    match = next((p for p in packs if p.casefold() == pack.casefold()), None)
    if match is None:
        raise DesktopError("unknown pack %r; available: %s" % (pack, packs))
    idx, n = packs.index(match), len(packs)
    before = flex.preset_names(bridge, channel)

    # Only one FLEX window may be open, or the template match could hit the wrong one.
    for ch in range(flex.api(bridge, "channels", "channelCount")):
        if ch != channel and flex.plugin_name(bridge, ch) == "FLEX":
            flex.api(bridge, "channels", "showEditor", ch, 0)
    flex.api(bridge, "channels", "showEditor", channel, 1)
    time.sleep(1.2)
    screen.ensure_fl_foreground()
    loc = screen.locate("flex_library_tab.png")
    if not loc:
        raise DesktopError("FLEX window not found on screen (screenshot: %s)" % _fail_shot("flex"))
    x, y, score = loc
    list_pt = (x + FLEX_ROW_DX, y + FLEX_LIST_DY)
    if idx < FLEX_VISIBLE_ROWS:
        screen.wheel(*list_pt, notches=+15)                 # back to the top
        row_y = y + FLEX_ROW0_DY + idx * FLEX_ROW_H
    else:
        screen.wheel(*list_pt, notches=-15)                 # to the end; rows bottom-aligned
        row_y = y + FLEX_LAST_ROW_DY - (n - 1 - idx) * FLEX_ROW_H
    time.sleep(0.4)
    screen.click(x + FLEX_ROW_DX, row_y)
    time.sleep(1.5)
    names = flex.preset_names(bridge, channel)
    if not keep_open:
        flex.api(bridge, "channels", "showEditor", channel, 0)
    changed = names != before
    return {"ok": changed or not before, "channel": channel, "pack": match, "match_score": score,
            "preset_count": len(names), "presets": names,
            "note": None if changed else "preset list unchanged -- the pack may already have been selected"}


# -- channels ----------------------------------------------------------------------

@action
def clone_channel(bridge, channel: int, count: int = 1) -> dict:
    channel, count = int(channel), max(1, int(count))
    names_before = [flex.api(bridge, "channels", "getChannelName", i)
                    for i in range(flex.api(bridge, "channels", "channelCount"))]
    flex.api(bridge, "channels", "selectOneChannel", channel)
    flex.api(bridge, "ui", "showWindow", WID_CHANNEL_RACK)
    flex.api(bridge, "ui", "setFocused", WID_CHANNEL_RACK)
    time.sleep(0.4)
    for _ in range(count):
        screen.hotkey("alt", "c", settle=1.2)
    total = flex.api(bridge, "channels", "channelCount")
    after = [flex.api(bridge, "channels", "getChannelName", i) for i in range(total)]
    pool = list(names_before)
    new = []
    for i, nm in enumerate(after):
        if nm in pool:
            pool.remove(nm)
        else:
            new.append({"channel": i, "name": nm})
    if total - len(names_before) < count:
        raise DesktopError("expected %d new channel(s), got %d -- was the channel rack focused?"
                           % (count, total - len(names_before)))
    return {"ok": True, "new_channels": new, "channel_count": total}


# -- piano roll note bridge --------------------------------------------------------

@action
def arm_note_bridge(bridge) -> dict:
    """Run MCP_Apply once from the piano roll's Tools > Scripts menu, which arms
    'Run last script again' (Ctrl+Alt+Y) for every later note write."""
    # Running MCP_Apply re-applies whatever the script last held; neutralise it
    # first (no notes, append mode) so arming never overwrites the open pattern.
    from ..pyscript_gen import write_apply_script
    write_apply_script([], mode="append")
    bridge.call(protocol.CMD_ENSURE_PIANO_ROLL, {}, timeout=5.0)
    flex.api(bridge, "ui", "setFocused", WID_PIANO_ROLL)
    time.sleep(0.6)
    screen.ensure_fl_foreground()
    loc = screen.locate("pianoroll_toolbar.png")
    if not loc:
        raise DesktopError("piano roll toolbar not found (screenshot: %s)" % _fail_shot("pianoroll"))
    ax, ay = loc[0] + PR_ARROW[0], loc[1] + PR_ARROW[1]
    screen.click(ax, ay, settle=0.8)
    tx, ty = ax + PR_TOOLS[0], ay + PR_TOOLS[1]
    screen.move(tx, ty, settle=0.9)
    for dx in (330, 520):                 # slide right along the Tools row into the submenu
        screen.move(ax + dx, ty, settle=0.3)
    item = screen.locate("mcp_apply_item.png")
    if not item:
        screen.hotkey("esc")
        screen.hotkey("esc")
        raise DesktopError("MCP_Apply not in the piano roll Scripts menu -- is MCP_Apply.pyscript "
                           "in Settings/Piano roll scripts? (screenshot: %s)" % _fail_shot("scripts"))
    screen.click(item[0] + 36, item[1] + 9, settle=1.0)
    return {"ok": True, "armed": True, "toolbar_score": loc[2], "menu_item_score": item[2]}


# -- project save / render ---------------------------------------------------------

def _projects_dir() -> Path:
    return fl_user_data_dir() / "Projects"


def _newest_flp(since: float = 0.0) -> Path | None:
    flps = [p for p in _projects_dir().rglob("*.flp") if "Backup" not in p.parts and p.stat().st_mtime >= since]
    return max(flps, key=lambda p: p.stat().st_mtime) if flps else None


@action
def save_project(bridge, name: str | None = None) -> dict:
    pre = screen.fl_dialogs()
    if pre:
        raise DesktopError("FL has a dialog open (%s); look with fl_screenshot and close it first"
                           % ", ".join(t or c for _, t, c in pre))
    t0 = time.time() - 1
    screen.hotkey("ctrl", "s", settle=1.5)
    dialog = screen.locate("save_button.png")
    if dialog:                                   # untitled project: FL's own Save-as dialog
        if name:
            screen.hotkey("ctrl", "a")
            screen.type_text(name)
        screen.click(dialog[0] + 50, dialog[1] + 19, settle=2.0)
    for _ in range(20):
        p = _newest_flp(since=t0)
        if p:
            return {"ok": True, "project": str(p), "used_dialog": bool(dialog)}
        popups = screen.fl_dialogs()
        if popups:                               # e.g. 'Project size warning' -- needs a human decision
            raise DesktopError("saving is waiting on an FL dialog: %s (screenshot: %s). Nothing was "
                               "clicked; decide with the user, then answer it."
                               % (", ".join(t or c for _, t, c in popups), _fail_shot("save")))
        time.sleep(0.5)
    raise DesktopError("no saved .flp appeared under %s" % _projects_dir())


@action
def render_wav(bridge, path: str | None = None, timeout: float = 600) -> dict:
    """Export WAV (Ctrl+R) of whatever FL would render now (PAT mode: the current
    pattern; SONG mode: the playlist). ``path`` defaults to a fresh file next to
    the most recently saved project."""
    if not path:
        proj = _newest_flp()
        if not proj:
            raise DesktopError("save the project first (fl_save_project) or pass an explicit path")
        n = 1
        while (proj.parent / ("%s render %d.wav" % (proj.stem, n))).exists():
            n += 1
        path = str(proj.parent / ("%s render %d.wav" % (proj.stem, n)))
    out = Path(path)
    if out.exists():
        raise DesktopError("%s already exists; pass a new path" % out)
    out.parent.mkdir(parents=True, exist_ok=True)
    open_dialogs = screen.fl_dialogs()
    if open_dialogs:
        raise DesktopError("FL has a dialog open (%s); look with fl_screenshot and close it first"
                           % ", ".join(t or c for _, t, c in open_dialogs))
    screen.hotkey("ctrl", "r", settle=0.3)
    dlg = screen.wait_for_fl_dialog(timeout=15.0)  # never type until the Save dialog has focus
    if not dlg:
        raise DesktopError("FL's export Save dialog did not appear; nothing was typed")
    screen.hotkey("ctrl", "a")                   # the filename box has focus in the Save dialog
    screen.type_text(str(out))
    screen.hotkey("enter", settle=2.5)
    if dlg in [h for h, _t, _c in screen.fl_dialogs()]:
        screen.close_window(dlg)
        raise DesktopError("the Save dialog didn't accept %s (cancelled it)" % out)
    start = None
    for _ in range(10):
        start = screen.locate("render_start.png")
        if start:
            break
        time.sleep(0.5)
    if not start:
        raise DesktopError("render dialog not found (screenshot: %s)" % _fail_shot("render"))
    screen.click(start[0] + 46, start[1] + 22)
    t0, last = time.time(), -1
    while time.time() - t0 < timeout:
        time.sleep(2.0)
        size = out.stat().st_size if out.exists() else 0
        if size > 44 and size == last and not screen.locate("render_start.png"):
            break
        last = size
    else:
        raise DesktopError("render did not finish within %ds" % timeout)
    info = {}
    try:
        import soundfile as sf
        i = sf.info(str(out))
        info = {"duration_sec": round(i.duration, 2), "samplerate": i.samplerate, "channels": i.channels}
    except Exception:
        pass
    return dict(ok=True, path=str(out), seconds=round(time.time() - t0, 1), **info)


@action
def screenshot(bridge, max_width: int = 1600) -> dict:
    """PNG of the monitor FL is on (never other monitors), downscaled."""
    from PIL import ImageGrab
    rect = screen.fl_monitor_rect()
    img = ImageGrab.grab(bbox=rect, all_screens=True)
    if img.width > max_width:
        img = img.resize((max_width, int(img.height * max_width / img.width)))
    import base64
    import io
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return {"ok": True, "jpeg_b64": base64.b64encode(buf.getvalue()).decode("ascii"),
            "size": [img.width, img.height], "monitor": list(rect)}


# -- reference pipeline (heavy, local) --------------------------------------------

@action
def reference_analyze(bridge, source: str, stems: bool = True, out_dir: str | None = None,
                      bpm: float | None = None) -> dict:
    from ..music.reference import analyze_reference
    return dict(ok=True, **analyze_reference(source, stems=stems, out_dir=out_dir, bpm=bpm))


@action
def compare_mix(bridge, mix: str, reference: str, mix_range=None, ref_range=None,
                window_sec: float = 20.0) -> dict:
    from ..music.reference import compare
    return dict(ok=True, **compare(mix, reference, mix_range, ref_range, window_sec))
