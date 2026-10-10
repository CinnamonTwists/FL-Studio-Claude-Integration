"""FLEX preset helpers over the controller's ``api_call`` op (needs only a bridge).

FLEX exposes the presets of its *selected pack* through FL's plugin API:
getPresetCount / getName(FPN_Preset, i) list them, nextPreset / prevPreset step
through them, and FLEX renames its channel to the loaded preset -- so the
channel name is how we read the current preset back. Switching packs has no
API; see desktop.actions.flex_select_pack.
"""

from __future__ import annotations

import time

FPN_PRESET = 6          # midi.FPN_Preset
NAME_SETTLE = 0.5       # FLEX's channel rename lands a moment after a preset step


class FLApiError(RuntimeError):
    pass


def api(bridge, module: str, fn: str, *args):
    r = bridge.call("api_call", {"module": module, "fn": fn, "args": list(args)})
    if not isinstance(r, dict) or "error" in r:
        raise FLApiError("%s.%s%r failed: %s" % (module, fn, args, (r or {}).get("error")))
    return r.get("result")


def api_batch(bridge, module: str, calls: list, chunk: int = 8) -> list:
    """Several calls on one module; chunked to stay under the SysEx size limit."""
    out = []
    for i in range(0, len(calls), chunk):
        r = bridge.call("api_call", {"module": module, "batch": calls[i:i + chunk]})
        out += [x.get("result", {"error": x.get("error")}) for x in r.get("results", [])]
    return out


def plugin_name(bridge, channel: int) -> str | None:
    try:
        if not api(bridge, "plugins", "isValid", channel, -1):
            return None
        return api(bridge, "plugins", "getPluginName", channel, -1)
    except FLApiError:
        return None


def require_flex(bridge, channel: int):
    name = plugin_name(bridge, channel)
    if name != "FLEX":
        raise FLApiError("channel %d hosts %r, not FLEX" % (channel, name))


def preset_names(bridge, channel: int) -> list[str]:
    n = api(bridge, "plugins", "getPresetCount", channel, -1) or 0
    return api_batch(bridge, "plugins", [["getName", [channel, -1, FPN_PRESET, i]] for i in range(n)])


def current_preset(bridge, channel: int, settle: float = NAME_SETTLE) -> str:
    time.sleep(settle)
    return api(bridge, "channels", "getChannelName", channel)


def load_preset(bridge, channel: int, preset: str, names: list[str] | None = None) -> dict:
    """Step the selected pack until ``preset`` is loaded; verified by channel name."""
    names = names or preset_names(bridge, channel)
    match = next((n for n in names if n.lower() == preset.lower()), None)
    if match is None:
        close = [n for n in names if preset.lower() in n.lower()]
        raise FLApiError("%r is not in the selected pack%s" %
                         (preset, (" -- did you mean %s?" % close[:5]) if close else ""))
    cur = current_preset(bridge, channel)
    if cur not in names:   # nothing from this pack loaded yet: step once for an anchor
        api(bridge, "plugins", "nextPreset", channel, -1)
        cur = current_preset(bridge, channel)
        if cur not in names:
            raise FLApiError("could not read the current preset (channel shows %r)" % cur)
    here, target = names.index(cur), names.index(match)
    steps = (target - here) % len(names)
    fn = "nextPreset"
    if steps > len(names) // 2:
        steps, fn = len(names) - steps, "prevPreset"
    for _ in range(steps):
        api(bridge, "plugins", fn, channel, -1)
    now = current_preset(bridge, channel)
    return {"ok": now == match, "channel": channel, "preset": now, "requested": match, "steps": steps}
