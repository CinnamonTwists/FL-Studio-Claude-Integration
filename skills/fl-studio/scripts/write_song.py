"""Write a whole song spec into FL in one go (tempo, markers, every part).

usage: python write_song.py <song.json> [--no-arm] [--no-markers] [--only part1,part2]
       (--no-markers when re-writing parts of a song whose markers already exist;
        markers are additive, so a rerun would duplicate them)

song.json:
{
  "tempo": 92,
  "markers": [[1, "Intro"], [9, "Verse"]],          # bar numbers, 1-based
  "parts": [
    {"name": "kick", "channel": 0,
     "notes": [{"pitch": 60, "time_bars": 0, "length_bars": 0.0625, "velocity": 0.9}, ...]},
    ...
  ]
}
Pitches are MIDI numbers (60 = middle C, which FL labels C5). Times/lengths are
in bars from the pattern start. Each part REPLACES that channel's notes in the
current pattern. Generating the spec in code (see assets/examples/) keeps big
note lists out of the conversation.
"""
import asyncio, json, os, sys
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_call import server_exe  # noqa: E402


async def call(c, name, args):
    r = await c.call_tool(name, args, raise_on_error=False)
    data = r.structured_content if r.structured_content is not None else [getattr(x, "text", str(x)) for x in r.content]
    ok = isinstance(data, dict) and data.get("ok", True) is not False
    print(f"{'ok ' if ok else 'ERR'} {name}: {json.dumps(data)[:180]}")
    return data


async def main(spec, arm, only, markers=True):
    t = StdioTransport(command=server_exe(), args=[], env={**os.environ, "FLSTUDIO_MCP_TRANSPORT": "tcp"})
    async with Client(t, timeout=600) as c:
        ping = await call(c, "fl_ping", {})
        if not (isinstance(ping, dict) and ping.get("alive")):
            sys.exit("FL is not reachable -- run scripts/preflight.ps1 first")
        if spec.get("tempo"):
            await call(c, "fl_set_tempo", {"bpm": spec["tempo"]})
        for bar, name in (spec.get("markers", []) if markers else []):
            await call(c, "fl_arrange_add_marker", {"bar": bar, "name": name})
        if arm:
            await call(c, "fl_arm_note_bridge", {})
        for part in spec["parts"]:
            if only and part["name"] not in only:
                continue
            await call(c, "fl_arrange_select_channel", {"channel": part["channel"]})
            await asyncio.sleep(0.8)
            res = await call(c, "fl_write_piano_roll_notes", {"notes": part["notes"], "mode": "replace"})
            if isinstance(res, dict) and not res.get("triggered", True):
                print("   ^ hotkey not sent:", res.get("error") or res.get("hint"))
            await asyncio.sleep(2.0 + len(part["notes"]) / 400)   # let FL apply big parts


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    asyncio.run(main(json.load(open(sys.argv[1], encoding="utf-8-sig")), "--no-arm" not in sys.argv, only,
                     markers="--no-markers" not in sys.argv))
