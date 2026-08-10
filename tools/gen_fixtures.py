#!/usr/bin/env python3
"""Regenerate fixtures.json from the Python reference engine.

The README describes the correctness chain as

    Python reference  ->  fixtures.json  ->  JavaScript port  ->  index.html

but nothing produced the middle link: fixtures.json had to be hand-edited,
which is exactly the step the chain exists to make impossible. Any engine
change now regenerates the fixtures here, and the three parity suites
re-verify the ports against them.

    python3 tools/gen_fixtures.py

Case inputs are declared below and are deliberately stable -- add cases,
never quietly retune the existing ones to make a failing port pass.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.tax import load_year, payroll_deductions                # noqa: E402
from engine.benefits import Household                               # noqa: E402
from engine.marginal import (effective_marginal_rate, net_position,  # noqa: E402
                             value_of_contribution)
from engine.accounts import Profile, optimize                       # noqa: E402
from engine.projection import (RetirementPlan, cost_of_waiting,     # noqa: E402
                               cpp_estimate, depletion_years, future_value,
                               oas_estimate, real_rate, required_monthly,
                               retirement_readiness)

# (income, partner_income, child_ages)
MARGINAL = [
    (50000, 0, []), (50000, 40000, [3, 6]), (95000, 0, [3, 6, 9]),
    (95000, 45000, [3, 6, 9]), (70000, 0, [2]), (38000, 0, [4]),
    (125000, 0, []), (200000, 0, [5, 10]), (25000, 0, []),
    (82847, 0, [1, 3]), (58523, 0, [1, 3, 5, 7]), (300000, 0, [8]),
]

# (income, capacity, child_ages, fhsa_eligible, match_rate, match_cap, retirement_rate)
ALLOCATION = [
    (95000, 20000, [3, 6, 9], True, 0.5, 4000, 0.25),
    (38000, 5000, [4], False, 0.0, 0, 0.45),
    (150000, 30000, [], True, 0.0, 0, 0.30),
    # Regression: employer match must draw on the same RRSP room as the
    # RRSP itself. Before the fix this returned $52,000 of deductible
    # contributions against $27,000 of room.
    (150000, 60000, [], False, 0.5, 25000, 0.25),
    # Regression: FHSA is capped by the $40,000 lifetime limit, not just
    # the annual one.
    (150000, 30000, [], True, 0.0, 0, 0.25),
    # Regression: TFSA full, RRSP scores negative on first-year value, RRSP
    # room still open. Money must go to the RRSP, not to a taxable account --
    # the shelter on 30 years of growth outlives the rate difference.
    (55000, 24000, [], False, 0.0, 0, 0.30),
]

# (principal, monthly, rate, years)
PROJECTION = [
    (0, 500, 0.08, 30), (10000, 0, 0.08, 30), (15000, 600, 0.08, 25),
    (0, 250, 0.05, 10), (5000, 300, 0.0, 15), (2000, 1000, 0.12, 40),
    (50000, 0, 0.06, 20), (0, 100, 0.08, 5),
]

PENSION_AGES = [60, 62, 65, 67, 70]

# Gross employment income for the take-home breakdown.
PAYROLL_INCOMES = [0, 3500, 30000, 68000, 74600, 80000, 85000, 150000]

# (balance, annual_draw, rate)
DEPLETION = [
    (1000000, 0, 0.04), (1000000, 40000, 0.04), (1000000, 60000, 0.04),
    (1000000, 100000, 0.04), (500000, 45000, 0.05), (250000, 30000, 0.03),
    (100000, 120000, 0.05),
]

# (current_age, retirement_age, target, savings, monthly, rate)
READINESS = [
    (35, 65, 55000, 15000, 600, 0.08),
    (25, 60, 45000, 0, 300, 0.07),
    (45, 65, 70000, 80000, 1200, 0.08),
    (30, 65, 40000, 5000, 200, 0.06),
]


def r(v, places=4):
    return round(v, places)


def build(cfg):
    marginal = []
    for income, partner, kids in MARGINAL:
        h = Household("BC", kids, partner)
        np_ = net_position(income, h, cfg)
        emr = effective_marginal_rate(income, h, cfg)
        val = value_of_contribution(income, 10000, h, cfg)
        marginal.append({
            "income": income, "partner_income": partner, "child_ages": kids,
            "afni": r(np_["afni"], 2), "tax": r(np_["tax"], 2),
            "ccb": r(np_["benefits"], 2),
            "statutory_rate": r(emr["statutory_rate"], 6),
            "clawback_rate": r(emr["clawback_rate"], 6),
            "effective_rate": r(emr["effective_rate"], 6),
            "value_10k_tax_refund": r(val["tax_refund"], 2),
            "value_10k_benefit": r(val["benefit_restored"], 2),
        })

    allocation = []
    for income, cap, kids, fhsa, mrate, mcap, retrate in ALLOCATION:
        p = Profile(income=income, household=Household("BC", kids, 0.0),
                    savings_capacity=cap, expected_retirement_rate=retrate,
                    fhsa_eligible=fhsa, employer_match_rate=mrate,
                    employer_match_cap=mcap)
        res = optimize(p, cfg)
        allocation.append({
            "income": income, "capacity": cap, "child_ages": kids,
            "fhsa_eligible": fhsa, "match_rate": mrate, "match_cap": mcap,
            "retirement_rate": retrate,
            "allocation": {k: r(v, 2) for k, v in res["allocation"].items()},
            "total_deducted": r(res["total_deducted"], 2),
            "rrsp_room": r(p.rrsp_room, 2),
            "tax_refund": r(res["tax_refund"], 2),
            "benefit_restored": r(res["benefit_restored"], 2),
        })

    projection = []
    for principal, monthly, rate, years in PROJECTION:
        projection.append({
            "principal": principal, "monthly": monthly, "rate": rate,
            "years": years,
            "fv": r(future_value(principal, monthly, rate, years)),
            "real_rate": r(real_rate(rate, 0.02), 8),
            "fv_real": r(future_value(principal, monthly,
                                      real_rate(rate, 0.02), years)),
            "req_monthly": r(required_monthly(500000, principal, rate, years)),
        })

    payroll = []
    for inc in PAYROLL_INCOMES:
        d = payroll_deductions(inc, cfg)
        payroll.append({"income": inc, "cpp": r(d["cpp"], 2), "cpp2": r(d["cpp2"], 2),
                        "ei": r(d["ei"], 2), "total": r(d["total"], 2)})

    depletion = [{"balance": b, "draw": d, "rate": rt,
                  "years": depletion_years(b, d, rt)} for b, d, rt in DEPLETION]

    pension = [{"age": a, "cpp": r(cpp_estimate(a)),
                "oas": r(oas_estimate(max(a, 65)))} for a in PENSION_AGES]

    readiness = []
    for age, retage, target, savings, monthly, rate in READINESS:
        plan = RetirementPlan(current_age=age, retirement_age=retage,
                              target_annual_income=target,
                              current_savings=savings,
                              monthly_contribution=monthly, annual_rate=rate)
        ready = retirement_readiness(plan)
        wait = cost_of_waiting(plan, 5)
        readiness.append({
            "current_age": age, "retirement_age": retage, "target": target,
            "savings": savings, "monthly": monthly, "rate": rate,
            "government": r(ready["government_annual"]),
            "nest_egg": r(ready["nest_egg_needed"]),
            "projected_real": r(ready["projected_real"]),
            "required_monthly": r(ready["required_monthly"]),
            "coverage": r(ready["coverage"], 6),
            "wait_cost": r(wait["cost"]),
        })

    return {
        "tax_year": cfg["tax_year"],
        "generated_by": "python reference engine via tools/gen_fixtures.py",
        "marginal_cases": marginal,
        "allocation_cases": allocation,
        "projection_cases": projection,
        "payroll_cases": payroll,
        "depletion_cases": depletion,
        "pension_cases": pension,
        "readiness_cases": readiness,
    }


if __name__ == "__main__":
    cfg = load_year(2026)
    out = build(cfg)
    path = ROOT / "fixtures.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    counts = {k: len(v) for k, v in out.items() if isinstance(v, list)}
    print(f"wrote {path.name}: {counts}")
