"""Call the fl-studio MCP server from a shell (same tools Claude Desktop gets).

usage:
  python mcp_call.py list                         tool names + one-line descriptions
  python mcp_call.py schema <tool> [<tool> ...]   input schema + full description
  python mcp_call.py call <tool> [<json>|@file]   one call; args as JSON text or @path.json
  python mcp_call.py run <calls.json>             [["tool", {args}], ["sleep", 2], ...]

Image results (fl_screenshot) are saved next to this script and the path is printed.
Pass JSON through a file (@args.json) from Windows PowerShell 5.1 -- it strips
inner double quotes from native-command arguments.
"""
import asyncio, base64, glob, json, os, shutil, sys, time
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def server_exe() -> str:
    found = shutil.which("fl-studio-mcp")
    if found:
        return found
    hits = sorted(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python3*\Scripts\fl-studio-mcp.exe")))
    if not hits:
        sys.exit("fl-studio-mcp not found; see references/setup.md")
    return hits[-1]


def show(name, r, limit=6000):
    for item in r.content:
        if getattr(item, "type", "") == "image":
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{name}_{int(time.time())}.jpg")
            open(p, "wb").write(base64.b64decode(item.data))
            print(f"[image saved] {p}")
            return
    if r.structured_content is not None:
        print(json.dumps(r.structured_content, indent=1)[:limit])
    else:
        print("\n".join(getattr(c, "text", str(c)) for c in r.content)[:limit])


def load_args(a):
    if not a:
        return {}
    if a.startswith("@"):
        return json.load(open(a[1:], encoding="utf-8-sig"))
    return json.loads(a)


async def main(argv):
    t = StdioTransport(command=server_exe(), args=[], env={**os.environ, "FLSTUDIO_MCP_TRANSPORT": "tcp"})
    async with Client(t, timeout=1900) as c:
        mode = argv[0]
        if mode == "list":
            for x in await c.list_tools():
                print(f"{x.name}: {(x.description or '').strip().splitlines()[0][:140]}")
        elif mode == "schema":
            for x in await c.list_tools():
                if x.name in argv[1:]:
                    print(x.name, json.dumps(x.inputSchema.get("properties", {}), indent=1))
                    print("DESC:", x.description, "\n")
        elif mode == "call":
            r = await c.call_tool(argv[1], load_args(argv[2] if len(argv) > 2 else ""), raise_on_error=False)
            show(argv[1], r)
        elif mode == "run":
            for name, args in json.load(open(argv[1], encoding="utf-8-sig")):
                if name == "sleep":
                    await asyncio.sleep(args)
                    continue
                print(f"=== {name} {json.dumps(args)[:160]}")
                show(name, await c.call_tool(name, args, raise_on_error=False))
        else:
            sys.exit(__doc__)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1:]))
