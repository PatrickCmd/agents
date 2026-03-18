"""
Multi-Provider Agentic Pipeline: 30-Year Coastal City Resilience Plan
=====================================================================

Combines four agentic patterns:
  Phase 1 — Prompt Chaining:    Parse scenario into structured context
  Phase 2 — Parallelization:    4 priority areas run concurrently across providers
  Phase 3 — Prompt Chaining:    Synthesize + generate alternatives/triggers
  Phase 4 — Evaluator-Optimizer: Rubric-based quality loop (different provider)

Model assignments:
  ┌──────────────────────┬────────────────────┬─────────────────────────────┐
  │ Phase                │ Model              │ Rationale                   │
  ├──────────────────────┼────────────────────┼─────────────────────────────┤
  │ 1. Parse scenario    │ Claude Sonnet 4    │ Structured extraction       │
  │ 2a. Emergency prep   │ Gemini 2.5 Pro     │ Strong structured planning  │
  │ 2b. Adaptation       │ Claude Opus 4      │ Nuanced tradeoff reasoning  │
  │ 2c. Managed retreat  │ OpenAI o3          │ Deep ethical reasoning      │
  │ 2d. Fiscal plan      │ GPT-4o             │ Cost modeling, structured   │
  │ 3. Synthesize        │ Claude Opus 4      │ Reconciling conflicting plans│
  │ 4. Evaluator         │ GPT-4o             │ Independent from synthesizer│
  └──────────────────────┴────────────────────┴─────────────────────────────┘

Usage:
  export ANTHROPIC_API_KEY="sk-ant-..."
  export OPENAI_API_KEY="sk-..."
  export GOOGLE_API_KEY="..."
  python resilience_pipeline.py
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

MAX_EVAL_ITERATIONS = 3
EVAL_PASS_THRESHOLD = 7  # out of 8 rubric checks must pass
HTTP_TIMEOUT = 120.0  # seconds per LLM call


class Provider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


@dataclass
class ModelConfig:
    provider: Provider
    model_id: str
    display_name: str
    max_tokens: int = 4096
    temperature: float = 0.4


# Model registry — single source of truth for all model assignments
MODELS = {
    "parse": ModelConfig(
        Provider.ANTHROPIC, "claude-sonnet-4-20250514", "Claude Sonnet 4"
    ),
    "emergency": ModelConfig(
        Provider.GOOGLE, "gemini-2.5-pro", "Gemini 2.5 Pro"
    ),
    "adaptation": ModelConfig(
        Provider.ANTHROPIC, "claude-opus-4-20250514", "Claude Opus 4"
    ),
    "retreat": ModelConfig(
        Provider.OPENAI, "o3", "OpenAI o3", temperature=1.0  # o3 ignores temperature but API requires valid value
    ),
    "fiscal": ModelConfig(
        Provider.OPENAI, "gpt-4o", "GPT-4o"
    ),
    "synthesize": ModelConfig(
        Provider.ANTHROPIC, "claude-opus-4-20250514", "Claude Opus 4"
    ),
    "evaluator": ModelConfig(
        Provider.OPENAI, "gpt-4o", "GPT-4o"
    ),
}

# ──────────────────────────────────────────────────────────────────────
# Scenario (the raw question)
# ──────────────────────────────────────────────────────────────────────

SCENARIO = """
You're advising the mayor of a mid-sized coastal city (population ~500,000) where
30% of developed land lies in the floodplain; median sea-level rise projections are
0.6 m by 2050 with a 1.2 m worst-case; the city faces a housing affordability crisis,
aging infrastructure, and limited fiscal capacity (annual operating budget ~$1.5B,
capital budget ~$200M/yr), and a recent storm caused $1.8B in damage that
disproportionately harmed low-income neighborhoods.
""".strip()

# ──────────────────────────────────────────────────────────────────────
# LLM Provider Clients
# ──────────────────────────────────────────────────────────────────────


class LLMClient(ABC):
    """Abstract base for provider-specific API clients."""

    @abstractmethod
    async def complete(
        self,
        client: httpx.AsyncClient,
        system: str,
        user: str,
        config: ModelConfig,
    ) -> str:
        ...


class AnthropicClient(LLMClient):
    """Anthropic Messages API (Claude models)."""

    API_URL = "https://api.anthropic.com/v1/messages"

    async def complete(
        self, client: httpx.AsyncClient, system: str, user: str, config: ModelConfig
    ) -> str:
        headers = {
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": config.model_id,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        resp = await client.post(self.API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return "".join(
            block["text"] for block in data["content"] if block["type"] == "text"
        )


class OpenAIClient(LLMClient):
    """OpenAI Chat Completions API (GPT-4o, o3)."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    async def complete(
        self, client: httpx.AsyncClient, system: str, user: str, config: ModelConfig
    ) -> str:
        headers = {
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": config.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        # o3 uses max_completion_tokens; GPT-4o uses max_tokens
        if config.model_id.startswith("o"):
            payload["max_completion_tokens"] = config.max_tokens
        else:
            payload["max_tokens"] = config.max_tokens
            payload["temperature"] = config.temperature

        resp = await client.post(self.API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class GoogleClient(LLMClient):
    """Google Gemini API."""

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    async def complete(
        self, client: httpx.AsyncClient, system: str, user: str, config: ModelConfig
    ) -> str:
        url = f"{self.API_BASE}/{config.model_id}:generateContent"
        params = {"key": os.environ["GOOGLE_API_KEY"]}
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": config.temperature,
                "maxOutputTokens": config.max_tokens,
            },
        }
        resp = await client.post(url, params=params, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


# Provider dispatch
_CLIENTS: dict[Provider, LLMClient] = {
    Provider.ANTHROPIC: AnthropicClient(),
    Provider.OPENAI: OpenAIClient(),
    Provider.GOOGLE: GoogleClient(),
}


async def call_llm(
    client: httpx.AsyncClient,
    role: str,
    system: str,
    user: str,
) -> str:
    """Dispatch an LLM call to the correct provider based on role's model config."""
    config = MODELS[role]
    llm_client = _CLIENTS[config.provider]

    print(f"  ⏳ [{role}] Calling {config.display_name}...")
    start = time.perf_counter()

    result = await llm_client.complete(client, system, user, config)

    elapsed = time.perf_counter() - start
    print(f"  ✅ [{role}] {config.display_name} responded ({elapsed:.1f}s, {len(result)} chars)")
    return result


# ──────────────────────────────────────────────────────────────────────
# Pipeline Prompts
# ──────────────────────────────────────────────────────────────────────


PHASE1_SYSTEM = """You are a senior urban resilience analyst. Parse the provided
city scenario into a structured JSON context object. Extract:
- city_profile: population, floodplain_pct, budget_operating, budget_capital
- climate_risk: sea_level_median_2050, sea_level_worst_case, recent_storm_damage
- social_context: housing_crisis (bool), aging_infrastructure (bool),
  equity_concerns (description)
- critical_assumptions: list of 8-12 assumptions you are making that aren't
  stated in the scenario (e.g., discount rate, population growth, insurance
  penetration, political environment)
- key_uncertainties: list of 5-8 quantified uncertainties with ranges

Return ONLY valid JSON, no markdown fences, no commentary."""

PHASE1_USER = f"Scenario:\n{SCENARIO}"


def make_priority_prompt(priority: str, description: str, context_json: str) -> tuple[str, str]:
    """Build system + user prompts for a single priority area."""
    system = f"""You are a specialist in {description}. You are contributing one
section of a 30-year coastal city resilience plan.

Given the parsed city context below, produce a detailed plan for the
"{priority}" priority area. Include:
1. Concrete interventions (3-5) with order-of-magnitude cost estimates
2. Realistic timelines (immediate / 5yr / 10yr / 30yr)
3. Funding and financing mechanisms specific to this area
4. Governance and community engagement structures
5. Measurable success metrics (quantitative where possible)
6. Main social/ethical tradeoffs for this priority area

IMPORTANT CONSTRAINTS:
- Total capital costs across ALL four priority areas must stay within ~$200M/yr
  Assume your area gets roughly 25-35% of that unless you argue otherwise.
- All interventions must address equity — explain how low-income neighborhoods
  benefit specifically.
- Be concrete: "$50M" not "significant investment"; "2027" not "near-term".

Respond in well-structured markdown."""

    user = f"City context:\n{context_json}"
    return system, user


SYNTHESIS_SYSTEM = """You are the lead advisor synthesizing four priority-area plans
into a single coherent 30-year resilience strategy. You will receive the parsed city
context and four specialist plans.

Your tasks:
1. RESOLVE BUDGET CONFLICTS: The four plans likely exceed the $200M/yr cap.
   Prioritize, phase, and cut until totals are feasible. Show your math.
2. IDENTIFY CROSS-CUTTING SYNERGIES: Where do investments serve multiple priorities?
3. PRODUCE A UNIFIED TIMELINE: Merge into a single phased roadmap.
4. GENERATE ALTERNATIVES: Describe at least 2 credible alternative strategies
   you considered and why you rejected them.
5. DEFINE 5 LEADING INDICATORS that would trigger switching to an alternative.
6. LIST LOCAL DATASETS you'd request to reduce key uncertainties, and how each
   would likely change your recommendations.

Format as a comprehensive markdown report with clear section headers."""

EVALUATOR_SYSTEM = """You are a rigorous quality evaluator for urban resilience plans.
Score the plan against this rubric. For each check, respond PASS or FAIL with a
one-sentence explanation.

RUBRIC:
1. BUDGET_FEASIBILITY: Do total capital costs stay within ~$200M/yr across all phases?
2. EQUITY_SPECIFICITY: Are equity impacts specific (named neighborhoods, income
   thresholds, % of affected residents) rather than vague platitudes?
3. COST_CONCRETENESS: Are cost estimates order-of-magnitude numbers ($XM) rather
   than vague ("significant investment")?
4. TIMELINE_CONCRETENESS: Are timelines specific years (2027, 2035) not vague
   ("near-term", "medium-term")?
5. ALTERNATIVES_PRESENT: Are at least 2 genuinely different alternative strategies
   described with reasons for rejection?
6. LEADING_INDICATORS: Are exactly 5 leading indicators defined with quantitative
   trigger thresholds?
7. DATASETS_LISTED: Are local datasets specified with explanation of how they'd
   change recommendations?
8. ASSUMPTIONS_EXPLICIT: Are critical assumptions listed and uncertainties quantified?

After scoring, provide SPECIFIC FEEDBACK for each FAIL item — what exactly is
missing and how to fix it.

Respond as JSON:
{
  "checks": {"BUDGET_FEASIBILITY": {"pass": true/false, "reason": "..."},  ...},
  "total_passed": N,
  "feedback": "Specific actionable feedback for the generator..."
}
Return ONLY valid JSON."""


# ──────────────────────────────────────────────────────────────────────
# Pipeline Execution
# ──────────────────────────────────────────────────────────────────────


@dataclass
class PipelineResult:
    """Collects outputs from every phase for inspection."""
    context_json: str = ""
    priority_plans: dict[str, str] = field(default_factory=dict)
    synthesized_plan: str = ""
    eval_history: list[dict[str, Any]] = field(default_factory=list)
    final_plan: str = ""
    total_elapsed: float = 0.0
    iterations_used: int = 0


async def run_pipeline() -> PipelineResult:
    """Execute the full 4-phase pipeline."""
    result = PipelineResult()
    pipeline_start = time.perf_counter()

    async with httpx.AsyncClient(timeout=httpx.Timeout(HTTP_TIMEOUT)) as client:

        # ── Phase 1: Parse scenario (Chaining) ──────────────────────
        print("\n" + "=" * 64)
        print("PHASE 1: Parse Scenario → Claude Sonnet 4")
        print("=" * 64)

        result.context_json = await call_llm(
            client, "parse", PHASE1_SYSTEM, PHASE1_USER
        )

        # Validate JSON parse
        try:
            context = json.loads(result.context_json)
            print(f"  📋 Parsed {len(context)} top-level keys: {list(context.keys())}")
        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON parse failed: {e}. Proceeding with raw text.")
            context = None

        # ── Phase 2: Parallel priority plans (Parallelization) ──────
        print("\n" + "=" * 64)
        print("PHASE 2: Parallel Priority Plans (4 providers)")
        print("=" * 64)

        priority_configs = {
            "emergency": ("Immediate emergency preparedness",
                          "disaster response, early warning systems, and emergency management"),
            "adaptation": ("Medium-term infrastructure adaptation",
                           "infrastructure engineering, nature-based solutions, and grey infrastructure"),
            "retreat": ("Long-term managed retreat and land-use transformation",
                        "urban planning, managed retreat policy, and environmental justice"),
            "fiscal": ("Fiscal sustainability",
                       "municipal finance, public budgeting, and infrastructure funding mechanisms"),
        }

        async def run_priority(role: str, priority: str, description: str) -> tuple[str, str]:
            system, user = make_priority_prompt(priority, description, result.context_json)
            plan = await call_llm(client, role, system, user)
            return role, plan

        # Fire all 4 concurrently
        tasks = [
            run_priority(role, priority, desc)
            for role, (priority, desc) in priority_configs.items()
        ]
        plans = await asyncio.gather(*tasks)

        for role, plan in plans:
            result.priority_plans[role] = plan
            print(f"  📄 {role}: {len(plan)} chars")

        # ── Phase 3: Synthesize + alternatives (Chaining) ───────────
        print("\n" + "=" * 64)
        print("PHASE 3: Synthesize → Claude Opus 4")
        print("=" * 64)

        synthesis_input = f"""City context:
{result.context_json}

--- EMERGENCY PREPAREDNESS PLAN ---
{result.priority_plans['emergency']}

--- INFRASTRUCTURE ADAPTATION PLAN ---
{result.priority_plans['adaptation']}

--- MANAGED RETREAT PLAN ---
{result.priority_plans['retreat']}

--- FISCAL SUSTAINABILITY PLAN ---
{result.priority_plans['fiscal']}
"""
        result.synthesized_plan = await call_llm(
            client, "synthesize", SYNTHESIS_SYSTEM, synthesis_input
        )

        # ── Phase 4: Evaluator-optimizer loop (Eval Loop) ───────────
        print("\n" + "=" * 64)
        print("PHASE 4: Evaluator Loop → GPT-4o (max {MAX_EVAL_ITERATIONS} iterations)")
        print("=" * 64)

        current_plan = result.synthesized_plan

        for iteration in range(1, MAX_EVAL_ITERATIONS + 1):
            print(f"\n  ── Iteration {iteration}/{MAX_EVAL_ITERATIONS} ──")

            # Evaluate
            eval_response = await call_llm(
                client,
                "evaluator",
                EVALUATOR_SYSTEM,
                f"Plan to evaluate:\n{current_plan}",
            )

            # Parse evaluation
            try:
                eval_data = json.loads(eval_response)
                total_passed = eval_data.get("total_passed", 0)
                feedback = eval_data.get("feedback", "")
                checks = eval_data.get("checks", {})

                # Display results
                for check_name, check_result in checks.items():
                    status = "✅" if check_result.get("pass") else "❌"
                    print(f"    {status} {check_name}: {check_result.get('reason', '')[:80]}")

                print(f"\n    Score: {total_passed}/{len(checks)}"
                      f" (threshold: {EVAL_PASS_THRESHOLD})")

            except json.JSONDecodeError:
                print("  ⚠️  Evaluator returned non-JSON. Treating as fail.")
                eval_data = {"total_passed": 0, "feedback": eval_response}
                total_passed = 0
                feedback = eval_response

            result.eval_history.append({
                "iteration": iteration,
                "total_passed": total_passed,
                "eval_data": eval_data,
            })

            # Check pass threshold
            if total_passed >= EVAL_PASS_THRESHOLD:
                print(f"\n  🎉 Plan PASSED evaluation at iteration {iteration}!")
                result.iterations_used = iteration
                break

            # If not the last iteration, refine
            if iteration < MAX_EVAL_ITERATIONS:
                print(f"\n  🔄 Refining plan with evaluator feedback...")
                refinement_prompt = f"""Your previous plan was evaluated and received
{total_passed}/8 passing checks. Here is the specific feedback:

{feedback}

Here is the plan that was evaluated:
{current_plan}

Please revise the plan to address ALL feedback points. Keep everything that passed
unchanged — focus only on fixing the failures. Return the complete revised plan."""

                current_plan = await call_llm(
                    client,
                    "synthesize",
                    SYNTHESIS_SYSTEM,
                    refinement_prompt,
                )
            else:
                print(f"\n  ⚠️  Max iterations reached. Using best available plan.")
                result.iterations_used = iteration

        result.final_plan = current_plan
        result.total_elapsed = time.perf_counter() - pipeline_start

    return result


# ──────────────────────────────────────────────────────────────────────
# Output + Summary
# ──────────────────────────────────────────────────────────────────────


def print_summary(result: PipelineResult) -> None:
    """Print a concise pipeline execution summary."""
    print("\n" + "=" * 64)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 64)

    print(f"\n  Total time:        {result.total_elapsed:.1f}s")
    print(f"  Eval iterations:   {result.iterations_used}/{MAX_EVAL_ITERATIONS}")
    print(f"  Final plan length: {len(result.final_plan):,} chars")

    print("\n  Model usage:")
    calls = {
        "Phase 1 (parse)":      MODELS["parse"],
        "Phase 2a (emergency)":  MODELS["emergency"],
        "Phase 2b (adaptation)": MODELS["adaptation"],
        "Phase 2c (retreat)":    MODELS["retreat"],
        "Phase 2d (fiscal)":     MODELS["fiscal"],
        "Phase 3 (synthesize)":  MODELS["synthesize"],
        "Phase 4 (evaluator)":   MODELS["evaluator"],
    }
    for phase, cfg in calls.items():
        print(f"    {phase:28s} → {cfg.display_name} ({cfg.provider.value})")

    # Eval progression
    if result.eval_history:
        print("\n  Evaluation progression:")
        for entry in result.eval_history:
            bar = "█" * entry["total_passed"] + "░" * (8 - entry["total_passed"])
            print(f"    Iteration {entry['iteration']}: [{bar}] {entry['total_passed']}/8")

    print()


def save_outputs(result: PipelineResult, output_dir: str = "/home/claude/output") -> str:
    """Save all pipeline artifacts to disk."""
    os.makedirs(output_dir, exist_ok=True)

    # Save the final plan
    plan_path = os.path.join(output_dir, "final_resilience_plan.md")
    with open(plan_path, "w") as f:
        f.write("# 30-Year Coastal City Resilience & Equity Plan\n\n")
        f.write(f"*Generated by multi-provider agentic pipeline*\n")
        f.write(f"*Evaluation iterations: {result.iterations_used}*\n\n")
        f.write("---\n\n")
        f.write(result.final_plan)

    # Save parsed context
    ctx_path = os.path.join(output_dir, "parsed_context.json")
    with open(ctx_path, "w") as f:
        try:
            formatted = json.dumps(json.loads(result.context_json), indent=2)
            f.write(formatted)
        except json.JSONDecodeError:
            f.write(result.context_json)

    # Save individual priority plans
    for role, plan in result.priority_plans.items():
        path = os.path.join(output_dir, f"priority_{role}.md")
        with open(path, "w") as f:
            f.write(f"# Priority Plan: {role.title()}\n\n")
            f.write(plan)

    # Save eval history
    eval_path = os.path.join(output_dir, "eval_history.json")
    with open(eval_path, "w") as f:
        json.dump(result.eval_history, f, indent=2, default=str)

    return plan_path


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────


async def main() -> None:
    # Validate API keys
    required_keys = {
        "ANTHROPIC_API_KEY": "Anthropic (Claude Sonnet 4, Opus 4)",
        "OPENAI_API_KEY": "OpenAI (GPT-4o, o3)",
        "GOOGLE_API_KEY": "Google (Gemini 2.5 Pro)",
    }
    missing = [f"  {k} — needed for {v}" for k, v in required_keys.items() if not os.environ.get(k)]
    if missing:
        print("❌ Missing API keys:\n" + "\n".join(missing))
        print("\nSet them with: export KEY_NAME='your-key-here'")
        return

    print("🏗️  Multi-Provider Agentic Pipeline: Coastal City Resilience Plan")
    print("─" * 64)
    print("Patterns: Chaining → Parallelization → Chaining → Evaluator Loop")
    print(f"Providers: Anthropic, OpenAI, Google  |  Max eval iters: {MAX_EVAL_ITERATIONS}")
    print("─" * 64)

    result = await run_pipeline()
    print_summary(result)

    plan_path = save_outputs(result)
    print(f"📁 Outputs saved to /home/claude/output/")
    print(f"   Final plan: {plan_path}")


if __name__ == "__main__":
    asyncio.run(main())
