"""Golden tests for the compound growth and retirement engine."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.projection import (real_rate, monthly_rate, future_value, required_monthly,
                               cpp_estimate, oas_estimate, RetirementPlan,
                               retirement_readiness, cost_of_waiting, projection_series)
PASS = FAIL = 0
def check(name, actual, expected, tol=1.0):
    global PASS, FAIL
    ok = abs(actual - expected) <= tol
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<50} got {actual:>13,.4f}  exp {expected:>13,.4f}")

print("\n--- Real return (Fisher, not subtraction) ---")
check("real rate 8% nominal / 2% inflation", real_rate(0.08, 0.02), 0.0588235, tol=1e-6)
check("NOT the naive 6.00%", abs(real_rate(0.08,0.02) - 0.06) > 0.001, True, tol=0)
check("zero inflation -> unchanged", real_rate(0.08, 0.0), 0.08, tol=1e-9)

print("\n--- Monthly rate conversion ---")
check("monthly rate compounds to annual", (1+monthly_rate(0.08))**12 - 1, 0.08, tol=1e-12)
check("r/12 would overstate", (1+0.08/12)**12 - 1, 0.0829995, tol=1e-6)

print("\n--- Future value ---")
# Verified against an independent month-by-month loop (see below), not by
# hand -- my first hand-computed value here was wrong by $21k.
check("500/mo 8% 30y", future_value(0, 500, 0.08, 30), 704275.29, tol=1)
check("lump 10k 8% 30y", future_value(10000, 0, 0.08, 30), 100626.57, tol=20)
check("zero rate = sum of deposits", future_value(1000, 500, 0.0, 10), 1000 + 500*120, tol=0.01)
check("zero years = principal", future_value(5000, 500, 0.08, 0), 5000, tol=0.01)
check("negative rate does not explode", future_value(10000, 100, -0.03, 10) > 0, True, tol=0)

print("\n--- Closed form vs brute-force simulation ---")
def simulate(principal, pmt, annual, years):
    """Deliberately naive month-by-month loop. If the closed-form formula and
    this ever disagree, the formula is wrong."""
    i = (1 + annual) ** (1/12) - 1
    bal = principal
    for _ in range(int(years * 12)):
        bal = bal * (1 + i) + pmt
    return bal
for (pr, c, r, y) in [(0,500,0.08,30), (10000,0,0.08,30), (15000,600,0.0588235,30), (0,250,0.05,10)]:
    check(f"closed-form == loop  P={pr} PMT={c} r={r:.3f}",
          future_value(pr, c, r, y), simulate(pr, c, r, y), tol=0.01)

print("\n--- Required monthly is the exact inverse ---")
tgt = future_value(2000, 437.29, 0.07, 22)
check("round-trip recovers contribution", required_monthly(tgt, 2000, 0.07, 22), 437.29, tol=0.01)
check("already funded -> 0", required_monthly(1000, 50000, 0.08, 20), 0.0, tol=0.01)
check("zero rate inverse", required_monthly(61000, 1000, 0.0, 10), 500.0, tol=0.01)

print("\n--- CPP / OAS (canada.ca Jan 2026) ---")
check("CPP average at 65 annual", cpp_estimate(65), 925.35*12, tol=0.01)
check("CPP max at 65 annual", cpp_estimate(65, use_maximum=True), 1507.65*12, tol=0.01)
check("CPP at 60 = -36%", cpp_estimate(60), 925.35*12*0.64, tol=0.5)
check("CPP at 70 = +42%", cpp_estimate(70), 925.35*12*1.42, tol=0.5)
check("OAS at 65 full residency", oas_estimate(65, 40), 742.31*12, tol=0.01)
check("OAS 20y residency = half", oas_estimate(65, 20), 742.31*12*0.5, tol=0.01)

print("\n--- Retirement readiness ---")
p = RetirementPlan(current_age=35, retirement_age=65, target_annual_income=55000,
                   current_savings=15000, monthly_contribution=600, annual_rate=0.08)
r = retirement_readiness(p)
print(f"    CPP+OAS ${r['government_annual']:,.0f}/yr covers the first slice of a "
      f"${p.target_annual_income:,.0f} target")
print(f"    portfolio must cover ${r['income_gap']:,.0f}/yr -> nest egg ${r['nest_egg_needed']:,.0f}")
print(f"    projected (today's $) ${r['projected_real']:,.0f}  on track: {r['on_track']}")
check("government income counted", r["government_annual"], 925.35*12 + 742.31*12, tol=1)
check("gap = target - government", r["income_gap"], 55000 - r["government_annual"], tol=1)
check("nest egg = gap / 4%", r["nest_egg_needed"], r["income_gap"]/0.04, tol=1)
check("real projection below nominal", r["projected_real"] < r["projected_nominal"], True, tol=0)

print("\n--- Cost of waiting ---")
c = cost_of_waiting(p, 5)
print(f"    delaying 5 years costs ${c['cost']:,.0f} in today's dollars, "
      f"having skipped only ${c['contributions_skipped']:,.0f} of contributions")
check("delay costs more than skipped", c["cost"] > c["contributions_skipped"], True, tol=0)
check("zero delay costs nothing", cost_of_waiting(p, 0)["cost"], 0.0, tol=0.01)

print("\n--- Series integrity ---")
s = projection_series(1000, 400, 0.08, 30)
check("series length", len(s), 31, tol=0)
check("year 0 = principal", s[0]["nominal"], 1000, tol=0.01)
check("contributed is linear", s[10]["contributed"], 1000 + 400*12*10, tol=0.01)
check("growth = balance - contributed", s[30]["growth_nominal"],
      s[30]["nominal"] - s[30]["contributed"], tol=0.01)
crossover = next((d["year"] for d in s if d["growth_nominal"] > d["contributed"]), None)
print(f"    growth overtakes contributions in year {crossover}")
check("crossover exists and is plausible", 10 <= crossover <= 25, True, tol=0)

print(f"\n{'='*74}\n  {PASS} passed, {FAIL} failed\n{'='*74}")
sys.exit(1 if FAIL else 0)
