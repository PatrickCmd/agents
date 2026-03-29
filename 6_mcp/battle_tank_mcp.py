#!/usr/bin/env python3
"""
Battle Tank Arena — MCP Server Explorer & Client (v2)
=====================================================
Tries Streamable HTTP transport first (newer), then SSE (legacy).

Prerequisites:
    pip install mcp httpx httpx-sse

Usage:
    python battle_tank_mcp.py              # discover tools
    python battle_tank_mcp.py --interact   # interactive REPL
    python battle_tank_mcp.py --probe      # raw HTTP debug
"""

import asyncio
import json
import sys
from mcp import ClientSession

MCP_URL = "https://battle-tank-arena.vercel.app/api/mcp"
CONNECT_TIMEOUT = 15  # seconds


# ─────────────────── Transport Helpers ───────────────────────

async def connect_streamable_http():
    """Try the newer Streamable HTTP transport."""
    from mcp.client.streamable_http import streamablehttp_client
    print("  Trying Streamable HTTP transport...")
    return streamablehttp_client(MCP_URL)


async def connect_sse():
    """Try the legacy SSE transport."""
    from mcp.client.sse import sse_client
    print("  Trying SSE transport...")
    return sse_client(MCP_URL)


# ─────────────────────── Discovery ───────────────────────────

async def discover_tools():
    """Connect and list all available tools."""
    print(f"🔗 Connecting to: {MCP_URL}\n")

    transports = [connect_streamable_http, connect_sse]

    for transport_fn in transports:
        try:
            transport_ctx = await asyncio.wait_for(transport_fn(), timeout=CONNECT_TIMEOUT)

            async with transport_ctx as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await asyncio.wait_for(session.initialize(), timeout=CONNECT_TIMEOUT)
                    print("✅ Connected!\n")

                    tools_result = await session.list_tools()
                    tools = tools_result.tools
                    print(f"📦 Found {len(tools)} tool(s):\n")
                    print("=" * 70)

                    for tool in tools:
                        print(f"\n🔧  {tool.name}")
                        print(f"    {tool.description or '(no description)'}")
                        schema = tool.inputSchema or {}
                        props = schema.get("properties", {})
                        required = schema.get("required", [])
                        if props:
                            print("    Parameters:")
                            for name, details in props.items():
                                req = "required" if name in required else "optional"
                                ptype = details.get("type", "any")
                                desc = details.get("description", "")
                                enum = details.get("enum")
                                line = f"      • {name} ({ptype}, {req})"
                                if desc:
                                    line += f" — {desc}"
                                if enum:
                                    line += f"  [choices: {', '.join(str(e) for e in enum)}]"
                                print(line)
                        print("-" * 70)

                    return tools

        except asyncio.TimeoutError:
            print(f"  ⏱ Timed out after {CONNECT_TIMEOUT}s\n")
        except Exception as e:
            print(f"  ❌ Failed: {type(e).__name__}: {e}\n")

    print("❌ Could not connect with any transport.")
    return []


# ─────────────────── Tool Caller ─────────────────────────────

async def call_tool(session: ClientSession, tool_name: str, arguments: dict):
    """Call a single MCP tool and pretty-print the result."""
    print(f"\n▶ Calling: {tool_name}({json.dumps(arguments)})")
    result = await session.call_tool(tool_name, arguments=arguments)
    print("◀ Response:")
    for block in result.content:
        if hasattr(block, "text"):
            try:
                parsed = json.loads(block.text)
                print(json.dumps(parsed, indent=2))
            except (json.JSONDecodeError, TypeError):
                print(block.text)
        else:
            print(block)
    return result


# ─────────────────── Interactive REPL ────────────────────────

async def interactive():
    """Interactive session: discover tools, then call them in a loop."""
    print(f"🔗 Connecting to: {MCP_URL}\n")

    transports = [connect_streamable_http, connect_sse]
    transport_ctx = None

    for transport_fn in transports:
        try:
            transport_ctx = await asyncio.wait_for(transport_fn(), timeout=CONNECT_TIMEOUT)
            break
        except asyncio.TimeoutError:
            print(f"  ⏱ Timed out\n")
            transport_ctx = None
        except Exception as e:
            print(f"  ❌ {type(e).__name__}: {e}\n")
            transport_ctx = None

    if transport_ctx is None:
        print("❌ Could not connect.")
        return

    async with transport_ctx as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=CONNECT_TIMEOUT)
            print("✅ Connected!\n")

            tools_result = await session.list_tools()
            tools = {t.name: t for t in tools_result.tools}

            print(f"Available tools: {', '.join(tools.keys())}\n")
            print("Type a tool name to call it. 'list' = show tools. 'quit' = exit.\n")

            while True:
                try:
                    choice = input("🎮 tool> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nBye!")
                    break

                if not choice:
                    continue
                if choice.lower() in ("quit", "exit", "q"):
                    print("Bye!")
                    break
                if choice.lower() == "list":
                    for t in tools.values():
                        print(f"  🔧 {t.name} — {t.description or ''}")
                    continue

                if choice not in tools:
                    print(f"  ❌ Unknown tool '{choice}'. Type 'list'.")
                    continue

                tool = tools[choice]
                schema = tool.inputSchema or {}
                props = schema.get("properties", {})
                required = schema.get("required", [])
                arguments = {}

                for pname, details in props.items():
                    req = pname in required
                    ptype = details.get("type", "string")
                    desc = details.get("description", "")
                    enum = details.get("enum")
                    prompt_str = f"  {pname}"
                    if desc:
                        prompt_str += f" ({desc})"
                    if enum:
                        prompt_str += f" [{'/'.join(str(e) for e in enum)}]"
                    if not req:
                        prompt_str += " [Enter=skip]"
                    prompt_str += ": "

                    val = input(prompt_str).strip()
                    if not val and not req:
                        continue
                    if not val and req:
                        print(f"    ⚠ {pname} is required!")
                        val = input(f"  {pname}: ").strip()

                    if ptype == "number":
                        val = float(val)
                    elif ptype == "integer":
                        val = int(val)
                    elif ptype == "boolean":
                        val = val.lower() in ("true", "1", "yes")

                    arguments[pname] = val

                try:
                    await call_tool(session, choice, arguments)
                except Exception as e:
                    print(f"  ❌ Error: {e}")


# ─────────────────── Raw Probe (debug) ───────────────────────

async def raw_probe():
    """Send raw HTTP requests to debug what the server expects."""
    import httpx

    print(f"🔍 Raw probe: {MCP_URL}\n")

    async with httpx.AsyncClient(timeout=15) as client:
        # 1. Try GET (some servers return info)
        print("── GET request ──")
        try:
            resp = await client.get(MCP_URL)
            print(f"  Status: {resp.status_code}")
            print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
            print(f"  Body: {resp.text[:1000]}\n")
        except Exception as e:
            print(f"  Error: {e}\n")

        # 2. Try POST with JSON-RPC initialize
        print("── POST JSON-RPC initialize ──")
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "0.1"},
            },
        }
        try:
            resp = await client.post(
                MCP_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            print(f"  Status: {resp.status_code}")
            print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
            print(f"  Body: {resp.text[:2000]}\n")
        except Exception as e:
            print(f"  Error: {e}\n")

        # 3. Try POST with Accept: text/event-stream only
        print("── POST with SSE Accept header ──")
        try:
            resp = await client.post(
                MCP_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
            )
            print(f"  Status: {resp.status_code}")
            print(f"  Content-Type: {resp.headers.get('content-type', 'N/A')}")
            print(f"  Body: {resp.text[:2000]}\n")
        except Exception as e:
            print(f"  Error: {e}\n")


# ─────────────────────── Main ────────────────────────────────

async def main():
    if "--probe" in sys.argv:
        await raw_probe()
    elif "--interact" in sys.argv or "-i" in sys.argv:
        await interactive()
    else:
        await discover_tools()
        print("\n💡 Tips:")
        print("   --interact (-i)  → interactive REPL to call tools")
        print("   --probe          → raw HTTP debug probe")


if __name__ == "__main__":
    asyncio.run(main())