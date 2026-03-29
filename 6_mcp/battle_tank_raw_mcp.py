#!/usr/bin/env python3
"""
Battle Tank Arena — Raw MCP Client (v3)
=======================================
Speaks JSON-RPC 2.0 directly over HTTP with SSE response parsing.
No dependency on MCP SDK transports — just httpx.

Prerequisites:
    pip install httpx

Usage:
    python battle_tank_mcp.py              # discover tools
    python battle_tank_mcp.py --interact   # interactive REPL

{
  "id": "tank_c8426608",
  "name": "CMD",
  "message": "Registered as \"CMD\". Reconnect to this MCP endpoint with header \"x-player-token: CMD\" to play."
}
"""

import asyncio
import json
import sys
import httpx

MCP_URL = "https://battle-tank-arena.vercel.app/api/mcp"
TIMEOUT = 30

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


# ─────────────────── JSON-RPC / SSE Helpers ──────────────────

def parse_sse_data(raw_text: str) -> list[dict]:
    """Extract JSON objects from SSE event stream text."""
    results = []
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                results.append(json.loads(payload))
            except json.JSONDecodeError:
                pass
    return results


async def rpc_call(client: httpx.AsyncClient, method: str, params: dict | None = None, req_id: int = 1) -> dict:
    """Send a JSON-RPC request and return the parsed result."""
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
    }
    if params is not None:
        payload["params"] = params

    resp = await client.post(MCP_URL, json=payload, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")

    if "text/event-stream" in content_type:
        events = parse_sse_data(resp.text)
        for event in events:
            if "result" in event:
                return event["result"]
            if "error" in event:
                raise RuntimeError(f"Server error: {event['error']}")
        raise RuntimeError(f"No result in SSE response: {resp.text[:500]}")
    else:
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Server error: {data['error']}")
        return data.get("result", data)


# ─────────────────── MCP Protocol Flow ───────────────────────

async def initialize(client: httpx.AsyncClient) -> dict:
    """MCP initialize handshake."""
    result = await rpc_call(client, "initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "battle-tank-client", "version": "1.0"},
    }, req_id=1)

    # Send initialized notification (no id = notification)
    notify_payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    await client.post(MCP_URL, json=notify_payload, headers=HEADERS, timeout=TIMEOUT)

    return result


async def list_tools(client: httpx.AsyncClient) -> list[dict]:
    """Fetch all available tools from the server."""
    result = await rpc_call(client, "tools/list", {}, req_id=2)
    return result.get("tools", [])


async def call_tool(client: httpx.AsyncClient, tool_name: str, arguments: dict, req_id: int = 3) -> dict:
    """Call a specific tool with arguments."""
    result = await rpc_call(client, "tools/call", {
        "name": tool_name,
        "arguments": arguments,
    }, req_id=req_id)
    return result


# ─────────────────── Display Helpers ─────────────────────────

def print_tools(tools: list[dict]):
    """Pretty-print tool list."""
    print(f"📦 Found {len(tools)} tool(s):\n")
    print("=" * 70)
    for tool in tools:
        print(f"\n🔧  {tool['name']}")
        print(f"    {tool.get('description', '(no description)')}")
        schema = tool.get("inputSchema", {})
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


def print_tool_result(result: dict):
    """Pretty-print a tool call result."""
    print("◀ Response:")
    content = result.get("content", [])
    if isinstance(content, list):
        for block in content:
            text = block.get("text", "")
            try:
                parsed = json.loads(text)
                print(json.dumps(parsed, indent=2))
            except (json.JSONDecodeError, TypeError):
                print(text)
    else:
        print(json.dumps(result, indent=2))


# ─────────────────────── Discovery ───────────────────────────

async def discover():
    """Connect and list all tools."""
    print(f"🔗 Connecting to: {MCP_URL}\n")

    async with httpx.AsyncClient() as client:
        server_info = await initialize(client)
        print(f"✅ Connected! Server: {server_info.get('serverInfo', {}).get('name', 'unknown')}\n")

        tools = await list_tools(client)
        print_tools(tools)
        return tools


# ─────────────────── Interactive REPL ────────────────────────

async def interactive():
    """Interactive session to call tools."""
    print(f"🔗 Connecting to: {MCP_URL}\n")

    async with httpx.AsyncClient() as client:
        server_info = await initialize(client)
        print(f"✅ Connected! Server: {server_info.get('serverInfo', {}).get('name', 'unknown')}\n")

        tools_list = await list_tools(client)
        tools = {t["name"]: t for t in tools_list}

        print(f"Available tools: {', '.join(tools.keys())}\n")
        print("Type a tool name to call it. 'list' = show tools. 'quit' = exit.\n")

        call_id = 10
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
                    print(f"  🔧 {t['name']} — {t.get('description', '')}")
                continue

            if choice not in tools:
                print(f"  ❌ Unknown tool '{choice}'. Type 'list'.")
                continue

            tool = tools[choice]
            schema = tool.get("inputSchema", {})
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

                # Type coercion
                if ptype == "number":
                    val = float(val)
                elif ptype == "integer":
                    val = int(val)
                elif ptype == "boolean":
                    val = val.lower() in ("true", "1", "yes")

                arguments[pname] = val

            try:
                print(f"\n▶ Calling: {choice}({json.dumps(arguments)})")
                call_id += 1
                result = await call_tool(client, choice, arguments, req_id=call_id)
                print_tool_result(result)
            except Exception as e:
                print(f"  ❌ Error: {e}")
            print()


# ─────────────────────── Main ────────────────────────────────

async def main():
    if "--interact" in sys.argv or "-i" in sys.argv:
        await interactive()
    else:
        await discover()
        print("\n💡 Run with --interact (-i) to call tools interactively.")


if __name__ == "__main__":
    asyncio.run(main())