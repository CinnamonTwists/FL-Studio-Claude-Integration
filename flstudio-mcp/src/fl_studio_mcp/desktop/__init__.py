"""Desktop-side automation that FL's scripting API can't do on its own.

Runs inside the daemon (a normal process) so it works even when the MCP server
is sandboxed (MSIX Claude Desktop). Everything here either drives FL's GUI
(screen matching + focus-verified input), touches the file system, or runs
heavy local jobs (downloads, stem separation, audio analysis).

Entry point: :func:`dispatch` -- ``{"action": str, "params": {...}}``.
"""

from __future__ import annotations

import time

# Actions that send real mouse/keyboard input to FL. A stray click or wheel
# event could nudge a fader, so these run inside a mixer guard.
GUI_ACTIONS = {"flex_select_pack", "clone_channel", "arm_note_bridge", "save_project", "render_wav"}


def _mixer_snapshot(bridge) -> dict:
    from .. import flex
    n = flex.api(bridge, "mixer", "trackCount")
    n = min(int(n or 0), 64)
    vols = flex.api_batch(bridge, "mixer", [["getTrackVolume", [i]] for i in range(n)])
    pans = flex.api_batch(bridge, "mixer", [["getTrackPan", [i]] for i in range(n)])
    return {"vol": vols, "pan": pans}


def _restore_drift(bridge, before: dict) -> list:
    from .. import flex
    time.sleep(0.5)                      # FL's reads lag writes/GUI changes slightly
    after = _mixer_snapshot(bridge)
    fixed = []
    for kind, setter in (("vol", "setTrackVolume"), ("pan", "setTrackPan")):
        for i, (a, b) in enumerate(zip(before[kind], after[kind], strict=False)):
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) > 1e-3:
                flex.api(bridge, "mixer", setter, i, a)
                fixed.append({"track": i, kind: round(b, 3), "restored_to": round(a, 3)})
    return fixed


def dispatch(bridge, action: str, params: dict | None) -> dict:
    from . import actions
    fn = actions.ACTIONS.get(action)
    if fn is None:
        return {"ok": False, "error": "unknown desktop action %r" % action,
                "available": sorted(actions.ACTIONS)}
    if action not in GUI_ACTIONS:
        return fn(bridge, **(params or {}))
    before = _mixer_snapshot(bridge)
    try:
        res = fn(bridge, **(params or {}))
    except Exception as e:
        drift = _restore_drift(bridge, before)
        if drift:
            raise type(e)("%s [mixer guard reverted unexpected changes: %s]" % (e, drift)) from e
        raise
    drift = _restore_drift(bridge, before)
    if drift:
        res = dict(res, mixer_guard={"restored": drift,
                                     "note": "unexpected mixer changes during GUI automation were reverted"})
    return res
