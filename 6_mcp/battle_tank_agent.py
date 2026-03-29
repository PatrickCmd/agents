#!/usr/bin/env python3
"""
Battle Tank Arena — AI Agent
=============================
An autonomous agent that plays the Battle Tank Arena game
via MCP tools using the OpenAI Agents SDK.

Prerequisites:
    pip install openai-agents
    # or: uv add openai-agents

Environment variables:
    OPENAI_API_KEY  — your OpenAI API key

Usage:
    # 1. Register your tank
    python battle_tank_agent.py --register BotCommander

    # 2. Play the game (auto-loop)
    python battle_tank_agent.py --play BotCommander

    # 3. Single turn check
    python battle_tank_agent.py --once BotCommander

    # 4. Check game state only
    python battle_tank_agent.py --state
"""

import asyncio
import sys

from agents import Agent, Runner, trace
from agents.mcp import MCPServerStreamableHttp
from dotenv import load_dotenv
import os

load_dotenv(override=True)

openai_api_key = os.getenv("OPENAI_API_KEY")

# ─────────────────── Configuration ───────────────────────────

MCP_URL = "https://battle-tank-arena.vercel.app/api/mcp"
MODEL = "gpt-4.1-mini"

# ─────────────────── Instructions ────────────────────────────

REGISTER_INSTRUCTIONS = """
You register a tank in the Battle Tank Arena game.
Use the `register` tool with the tank name provided.
Report the registration result clearly.
"""

STRATEGY_INSTRUCTIONS = """
You are an expert Battle Tank Arena commander. You play aggressively and never waste a turn.

## Game Mechanics
- Turn-based grid battle. Each turn you get TWO dice.
- 60 seconds per turn to use both dice or your turn is skipped.
- `rotate` is FREE (no die cost). `move` and `fire` each consume one die.
- Moving: advances exactly die-value cells in your facing direction.
- Firing: shot lands exactly die-value cells away in facing direction.
  - If an enemy body is on that cell → HIT (they lose 1 point, eliminated at 0).
  - If empty → MISS (die still consumed).
- Barrel tip = 1 step from tank body.

## Your Turn Protocol (follow this EXACTLY)

### Step 1 — Assess
Call `get_game_state`. If the game is not running or it's not your turn, report and stop.

### Step 2 — Plan first action
Call `get_valid_actions`. You'll see your dice, position, enemies, and for each die:
  - `validShots`: directions you can fire, and what each hits (target name = guaranteed hit, null = miss)
  - `validMoves`: directions you can move

### Step 3 — Execute first die
PRIORITY ORDER:
  a) If any die's validShots shows a target (non-null) → rotate to that direction (free) → `fire` that die
  b) If no hit possible → use the die that gives best positional move toward an enemy → `rotate` then `move`
  c) If both dice can hit enemies → fire the one with higher value first (more damage? no — same damage, so pick either)

### Step 4 — Plan second action
Call `get_valid_actions` again (state has changed after your first action).

### Step 5 — Execute second die
Same priority: fire if you can hit, otherwise move strategically.

### Step 6 — Confirm
Call `get_game_state` to verify your turn ended properly.

## Key Tactical Rules
- ALWAYS call `get_valid_actions` before EACH action — never guess.
- Rotate is free — use it liberally to line up shots or moves.
- Prefer firing over moving when a hit is possible.
- If no hits available, move toward the nearest enemy.
- NEVER skip a die — always use both.
- If your turn is skipped or game is in lobby, just report the status clearly.
"""

OBSERVER_INSTRUCTIONS = """
You observe the Battle Tank Arena game state.
Call `get_game_state` and report a clear summary:
- Game status (lobby/running/ended)
- Whose turn it is
- All tank positions, scores, and health
- Turn order
"""

# ─────────────────── Register ────────────────────────────────


async def register_tank(name: str):
    """Register a new tank."""
    print(f"📝 Registering tank: {name}\n")

    async with MCPServerStreamableHttp(
        name="battle-tank-arena",
        params={"url": MCP_URL, "timeout": 30},
        client_session_timeout_seconds=60,
    ) as server:
        agent = Agent(
            name="registrar",
            instructions=REGISTER_INSTRUCTIONS,
            model=MODEL,
            mcp_servers=[server],
        )

        with trace("register_tank"):
            result = await Runner.run(agent, f"Register a tank with the name: {name}")
            print(result.final_output)


# ─────────────────── Observe ─────────────────────────────────


async def check_state(token: str | None = None):
    """Check the current game state."""
    headers = {}
    if token:
        headers["x-player-token"] = token

    params = {"url": MCP_URL, "timeout": 30}
    if headers:
        params["headers"] = headers

    async with MCPServerStreamableHttp(
        name="battle-tank-arena",
        params=params,
        client_session_timeout_seconds=60,
    ) as server:
        agent = Agent(
            name="observer",
            instructions=OBSERVER_INSTRUCTIONS,
            model=MODEL,
            mcp_servers=[server],
        )

        with trace("check_state"):
            result = await Runner.run(agent, "What is the current game state?")
            print(result.final_output)
            return result.final_output


# ─────────────────── Play One Turn ───────────────────────────


async def play_turn(tank_name: str) -> str:
    """Play a single turn (or report if not our turn)."""

    async with MCPServerStreamableHttp(
        name="battle-tank-arena",
        params={
            "url": MCP_URL,
            "headers": {"x-player-token": tank_name},
            "timeout": 30,
        },
        client_session_timeout_seconds=60,
    ) as server:
        agent = Agent(
            name="tank_commander",
            instructions=STRATEGY_INSTRUCTIONS,
            model=MODEL,
            mcp_servers=[server],
        )

        prompt = (
            "It's time to play. Check the game state, and if it's my turn, "
            "execute the full turn protocol — use both dice optimally. "
            "Report every action you take and the outcome."
        )

        with trace("play_turn"):
            result = await Runner.run(agent, prompt)
            print(result.final_output)
            return result.final_output


# ─────────────────── Game Loop ───────────────────────────────


async def game_loop(tank_name: str):
    """Continuously play turns until the game ends."""
    print(f"🎮 Starting game loop as: {tank_name}")
    print(f"🔗 Server: {MCP_URL}")
    print(f"🤖 Model: {MODEL}\n")

    turn_count = 0

    while True:
        turn_count += 1
        print(f"\n{'='*60}")
        print(f"  🔄 Check #{turn_count}")
        print(f"{'='*60}\n")

        try:
            report = await play_turn(tank_name)

            # Detect game end
            if report and "ended" in report.lower():
                print("\n🏁 Game over!")
                break

            # Adaptive polling: short wait if it was our turn, longer if waiting
            if report and any(
                phrase in report.lower()
                for phrase in ["not your turn", "not my turn", "lobby", "waiting"]
            ):
                print("\n⏳ Not our turn — checking again in 5s...")
                await asyncio.sleep(5)
            else:
                print("\n⏳ Next check in 3s...")
                await asyncio.sleep(3)

        except KeyboardInterrupt:
            print("\n\n👋 Exiting game loop.")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("   Retrying in 5s...")
            await asyncio.sleep(5)


# ─────────────────────── Main ────────────────────────────────


def usage():
    print(
        """
Usage:
  python battle_tank_agent.py --register <TankName>    Register a new tank
  python battle_tank_agent.py --play <TankName>        Auto-play game loop
  python battle_tank_agent.py --once <TankName>        Play one turn
  python battle_tank_agent.py --state                  Check game state
  python battle_tank_agent.py --state <TankName>       Check state (authenticated)

Environment:
  OPENAI_API_KEY    Required — your OpenAI API key
"""
    )


async def main():
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        usage()
        return

    command = args[0]
    name = args[1] if len(args) > 1 else None

    if command == "--register":
        if not name:
            print("❌ Provide a tank name: --register <TankName>")
            return
        await register_tank(name)

    elif command == "--play":
        if not name:
            print("❌ Provide your tank name: --play <TankName>")
            return
        await game_loop(name)

    elif command == "--once":
        if not name:
            print("❌ Provide your tank name: --once <TankName>")
            return
        await play_turn(name)

    elif command == "--state":
        await check_state(token=name)

    else:
        print(f"❌ Unknown command: {command}")
        usage()


if __name__ == "__main__":
    asyncio.run(main())