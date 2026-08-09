"""
Golden tests for the Canadian tax engine.

Every expected value here was derived independently from the published
CRA / BC bracket tables, not from the engine's own output. These same
fixtures port directly to XCTest for the Swift implementation.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.tax import load_year, bracket_tax, federal_tax, provincial_tax, federal_bpa
from engine.benefits import canada_child_benefit, Household
from engine.marginal import effective_marginal_rate, value_of_contribution

cfg = load_year(2026)
PASS = FAIL = 0

def check(name, actual, expected, tol=1.0):
    global PASS, FAIL
    ok = abs(actual - expected) <= tol
    PASS, FAIL = PASS + ok, FAIL + (not ok)
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {name:<52} got {actual:>12,.2f}  exp {expected:>12,.2f}")

print("\n--- Bracket ladder ---")
check("fed bracket tax @ 50,000", bracket_tax(50000, cfg["federal"]["brackets"]), 50000*0.14)
check("fed bracket tax @ 100,000", bracket_tax(100000, cfg["federal"]["brackets"]), 16696.01)
check("fed bracket tax @ 0", bracket_tax(0, cfg["federal"]["brackets"]), 0.0)
check("fed bracket tax @ negative", bracket_tax(-5000, cfg["federal"]["brackets"]), 0.0)

bc = cfg["provinces"]["BC"]["brackets"]
check("BC bracket tax @ 100,000", bracket_tax(100000, bc), 6642.38)

print("\n--- Basic personal amount phase-out ---")
check("fed BPA @ 100,000 (full)", federal_bpa(100000, cfg), 16452)
check("fed BPA @ 258,482 (min)", federal_bpa(258482, cfg), 14829)
check("fed BPA @ 219,961 (midpoint)", federal_bpa(219961, cfg), 14829 + 1623/2, tol=2)

print("\n--- Edge cases that break naive implementations ---")
check("federal tax @ 16,452 (BPA = zero tax)", federal_tax(16452, cfg), 0.0, tol=1.0)
check("federal tax never negative @ 5,000", federal_tax(5000, cfg), 0.0)
check("BC tax @ 24,000 (reduction credit)", provincial_tax(24000, "BC", cfg), 0.0, tol=1.0)

print("\n--- CCB two-zone phase-out ---")
check("CCB 1 child u6 @ 35,000 AFNI", canada_child_benefit(35000, [3], cfg), 8157)
check("CCB 1 child u6 @ 50,000 AFNI", canada_child_benefit(50000, [3], cfg), 7333.59)
check("CCB 2 children @ 90,000 AFNI (zone 2)", canada_child_benefit(90000, [3, 8], cfg), 8609.93)
check("CCB no children", canada_child_benefit(50000, [], cfg), 0.0)
check("CCB fully clawed back @ 300,000", canada_child_benefit(300000, [10], cfg), 0.0)
check("CCB child aged 18 excluded", canada_child_benefit(35000, [18], cfg), 0.0)

print("\n--- Effective marginal rate: the whole point ---")
single = Household(province="BC", child_ages=[])
family3 = Household(province="BC", child_ages=[3, 6, 9])

r_single = effective_marginal_rate(95000, single, cfg)
r_family = effective_marginal_rate(95000, family3, cfg)
print(f"  single  @95k: statutory {r_single['statutory_rate']:.2%}  "
      f"clawback {r_single['clawback_rate']:.2%}  EFFECTIVE {r_single['effective_rate']:.2%}")
print(f"  3 kids  @95k: statutory {r_family['statutory_rate']:.2%}  "
      f"clawback {r_family['clawback_rate']:.2%}  EFFECTIVE {r_family['effective_rate']:.2%}")
check("single @95k has no clawback", r_single["clawback_rate"], 0.0, tol=0.001)
check("3-child family @95k clawback = 8%", r_family["clawback_rate"], 0.08, tol=0.001)

print("\n--- Contribution valuation ---")
v = value_of_contribution(95000, 10000, family3, cfg)
print(f"  $10,000 RRSP @ $95k income, 3 kids:")
print(f"    tax refund       ${v['tax_refund']:>9,.2f}")
print(f"    CCB restored     ${v['benefit_restored']:>9,.2f}")
print(f"    TOTAL VALUE      ${v['total_value']:>9,.2f}   ({v['blended_rate']:.1%})")
check("benefit component is material", v["benefit_restored"], 800, tol=200)

print(f"\n{'='*72}\n  {PASS} passed, {FAIL} failed\n{'='*72}")
sys.exit(1 if FAIL else 0)
