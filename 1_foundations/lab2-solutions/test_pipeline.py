"""
Dry-run test: validates pipeline structure, prompt construction, and
evaluator loop logic without making real API calls.
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, "/home/claude")

import resilience_pipeline as rp


# ── Mock LLM responses ──────────────────────────────────────────────

MOCK_CONTEXT = json.dumps({
    "city_profile": {
        "population": 500000,
        "floodplain_pct": 30,
        "budget_operating": 1_500_000_000,
        "budget_capital": 200_000_000,
    },
    "climate_risk": {
        "sea_level_median_2050": "0.6m",
        "sea_level_worst_case": "1.2m",
        "recent_storm_damage": 1_800_000_000,
    },
    "social_context": {
        "housing_crisis": True,
        "aging_infrastructure": True,
        "equity_concerns": "Recent storm disproportionately harmed low-income areas",
    },
    "critical_assumptions": [
        "3% discount rate",
        "0.8% annual population growth",
        "40% insurance penetration in floodplain",
        "Stable political support over 30 years",
        "Federal disaster aid continues at current levels",
        "Construction cost inflation at 4%/yr",
        "No major hurricane in next 5 years",
        "Property values in floodplain decline 15% over 10yr",
    ],
    "key_uncertainties": [
        {"factor": "Sea level rise by 2050", "range": "0.3m - 1.2m"},
        {"factor": "Storm frequency increase", "range": "20-80% more Category 3+"},
        {"factor": "Federal funding availability", "range": "$0 - $500M over 30yr"},
        {"factor": "Population migration", "range": "-5% to +15%"},
        {"factor": "Insurance market retreat", "range": "10-60% coverage loss"},
    ],
})

MOCK_PRIORITY_PLAN = """## Interventions
1. **Early warning system upgrade** — $15M, deploy by 2027
2. **Evacuation route hardening** — $45M over 5 years
3. **Community resilience hubs** — $30M, 12 hubs by 2030

## Equity: Low-income neighborhoods in Zones A/B get priority hub placement.
## Metrics: Evacuation time < 4hrs for 95% of residents by 2029.
"""

MOCK_SYNTHESIS = """# Unified 30-Year Plan
## Budget: $180M/yr average, phased across priorities
## Alternatives considered:
1. Full seawall strategy ($4B, rejected: fiscal infeasibility)
2. Accelerated retreat (rejected: political non-starter in first decade)
## 5 Leading indicators:
1. Sea level gauge > 0.4m above 2020 baseline before 2035
2. Annual flood damage > $500M for 2 consecutive years
3. Floodplain property values decline > 30%
4. Federal flood insurance participation drops below 30%
5. Population in floodplain decreases > 10% in 5 years
## Datasets needed: LIDAR elevation data, parcel-level flood claims, etc.
## Assumptions: Listed in context parsing phase.
"""

# Evaluator: first call returns 5/8, second returns 8/8
MOCK_EVAL_FAIL = json.dumps({
    "checks": {
        "BUDGET_FEASIBILITY": {"pass": True, "reason": "Totals ~$180M/yr, within cap"},
        "EQUITY_SPECIFICITY": {"pass": False, "reason": "Mentions 'low-income' but no specific neighborhoods"},
        "COST_CONCRETENESS": {"pass": True, "reason": "Dollar amounts are specific"},
        "TIMELINE_CONCRETENESS": {"pass": True, "reason": "Years specified"},
        "ALTERNATIVES_PRESENT": {"pass": True, "reason": "Two alternatives with rejection rationale"},
        "LEADING_INDICATORS": {"pass": True, "reason": "5 indicators with thresholds"},
        "DATASETS_LISTED": {"pass": False, "reason": "Datasets mentioned but no explanation of how they'd change recs"},
        "ASSUMPTIONS_EXPLICIT": {"pass": False, "reason": "Assumptions listed but uncertainties not quantified inline"},
    },
    "total_passed": 5,
    "feedback": "Fix equity specificity (name neighborhoods), expand dataset explanations, quantify uncertainties.",
})

MOCK_EVAL_PASS = json.dumps({
    "checks": {k: {"pass": True, "reason": "Addressed"} for k in [
        "BUDGET_FEASIBILITY", "EQUITY_SPECIFICITY", "COST_CONCRETENESS",
        "TIMELINE_CONCRETENESS", "ALTERNATIVES_PRESENT", "LEADING_INDICATORS",
        "DATASETS_LISTED", "ASSUMPTIONS_EXPLICIT",
    ]},
    "total_passed": 8,
    "feedback": "All checks pass.",
})


# ── Mock dispatch ────────────────────────────────────────────────────

call_log: list[dict] = []
eval_call_count = 0


async def mock_call_llm(client, role, system, user):
    """Replace real API calls with deterministic mocks."""
    global eval_call_count

    call_log.append({"role": role, "system_len": len(system), "user_len": len(user)})
    config = rp.MODELS[role]
    print(f"  🔶 [MOCK] [{role}] → {config.display_name} ({config.provider.value})")

    if role == "parse":
        return MOCK_CONTEXT
    elif role in ("emergency", "adaptation", "retreat", "fiscal"):
        return MOCK_PRIORITY_PLAN
    elif role == "synthesize":
        return MOCK_SYNTHESIS
    elif role == "evaluator":
        eval_call_count += 1
        if eval_call_count == 1:
            return MOCK_EVAL_FAIL
        return MOCK_EVAL_PASS

    return "UNEXPECTED ROLE"


# ── Run test ─────────────────────────────────────────────────────────

async def test_pipeline():
    # Monkey-patch the call_llm function
    original_call = rp.call_llm
    rp.call_llm = mock_call_llm

    try:
        result = await rp.run_pipeline()
        rp.print_summary(result)

        # Assertions
        assert result.context_json == MOCK_CONTEXT, "Phase 1 context mismatch"
        assert len(result.priority_plans) == 4, f"Expected 4 plans, got {len(result.priority_plans)}"
        assert result.iterations_used == 2, f"Expected 2 eval iterations, got {result.iterations_used}"
        assert len(result.eval_history) == 2, f"Expected 2 eval entries, got {len(result.eval_history)}"
        assert result.eval_history[0]["total_passed"] == 5, "First eval should be 5/8"
        assert result.eval_history[1]["total_passed"] == 8, "Second eval should be 8/8"

        # Verify call ordering
        roles_called = [c["role"] for c in call_log]
        assert roles_called[0] == "parse", "Phase 1 should run first"
        # Phase 2 is parallel — order varies, but all 4 should appear
        phase2 = set(roles_called[1:5])
        assert phase2 == {"emergency", "adaptation", "retreat", "fiscal"}, f"Phase 2 missing: {phase2}"
        assert roles_called[5] == "synthesize", "Phase 3 synthesize"
        assert roles_called[6] == "evaluator", "Phase 4 first eval"
        assert roles_called[7] == "synthesize", "Phase 4 refinement"
        assert roles_called[8] == "evaluator", "Phase 4 second eval"

        # Verify outputs save
        plan_path = rp.save_outputs(result)
        assert os.path.exists(plan_path), f"Plan not saved to {plan_path}"
        assert os.path.exists("/home/claude/output/eval_history.json")
        assert os.path.exists("/home/claude/output/parsed_context.json")

        print("=" * 64)
        print("✅ ALL ASSERTIONS PASSED — Pipeline logic verified")
        print(f"   Total mock LLM calls: {len(call_log)}")
        print(f"   Call sequence: {' → '.join(roles_called)}")
        print("=" * 64)

    finally:
        rp.call_llm = original_call


if __name__ == "__main__":
    asyncio.run(test_pipeline())
