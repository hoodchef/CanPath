import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.tax import load_year
from engine.benefits import Household
from engine.marginal import effective_marginal_rate, value_of_contribution
from engine.accounts import Profile, optimize

cfg = load_year(2026)

def hdr(t): print(f"\n{'='*74}\n  {t}\n{'='*74}")

hdr("SCENARIO A — Surrey BC, $95,000, three kids (3, 6, 9)")
h = Household("BC", [3, 6, 9])
r = effective_marginal_rate(95000, h, cfg)
print(f"  Posted combined bracket rate ........ {r['statutory_rate']:>7.2%}")
print(f"  Hidden CCB clawback ................. {r['clawback_rate']:>7.2%}")
print(f"  TRUE effective marginal rate ........ {r['effective_rate']:>7.2%}")
v = value_of_contribution(95000, 10000, h, cfg)
print(f"\n  $10,000 RRSP contribution:")
print(f"    Tax refund ........................ ${v['tax_refund']:>10,.0f}")
print(f"    CCB restored ...................... ${v['benefit_restored']:>10,.0f}")
print(f"    Total value ....................... ${v['total_value']:>10,.0f}  ({v['blended_rate']:.1%})")
print(f"    Refund is only {v['refund_share']:.0%} of the true benefit.")

hdr("SCENARIO B — same income, no children")
h2 = Household("BC", [])
v2 = value_of_contribution(95000, 10000, h2, cfg)
print(f"  Same $10,000 RRSP is worth ......... ${v2['total_value']:>10,.0f}  ({v2['blended_rate']:.1%})")
print(f"  Difference from Scenario A ......... ${v['total_value']-v2['total_value']:>10,.0f}")

hdr("SCENARIO C — the threshold cliff: $88,000, two kids (2, 4)")
h3 = Household("BC", [2, 4])
for c in (0, 5000, 10000, 15000):
    vc = value_of_contribution(88000, c, h3, cfg) if c else None
    emr = effective_marginal_rate(88000 - c, h3, cfg)
    line = f"  after ${c:>6,} contributed -> income ${88000-c:>7,}   EMR {emr['effective_rate']:>6.2%}"
    if vc: line += f"   cumulative value ${vc['total_value']:>8,.0f}"
    print(line)

hdr("SCENARIO D — allocation solver, $20,000 to invest")
p = Profile(income=95000, household=Household("BC", [3, 6, 9]),
            savings_capacity=20000, expected_retirement_rate=0.25,
            fhsa_eligible=True, employer_match_rate=0.50, employer_match_cap=4000)
res = optimize(p, cfg)
print("  Recommended funding order:")
for k, amt in res["allocation"].items():
    print(f"    {k:<18} ${amt:>9,.0f}")
print(f"\n    Employer match earned ........... ${res['employer_match_earned']:>9,.0f}")
print(f"    Tax refund ...................... ${res['tax_refund']:>9,.0f}")
print(f"    CCB restored .................... ${res['benefit_restored']:>9,.0f}")
total = res['employer_match_earned'] + res['tax_refund'] + res['benefit_restored']
print(f"    FIRST-YEAR RETURN ............... ${total:>9,.0f}  ({total/20000:.1%} on $20,000)")

hdr("SCENARIO E — guardrail: $38,000 income, one child")
p2 = Profile(income=38000, household=Household("BC", [4]),
             savings_capacity=5000, expected_retirement_rate=0.45)
res2 = optimize(p2, cfg)
print("  Recommended:", {k: f"${v:,.0f}" for k, v in res2["allocation"].items()})
for w in res2["warnings"]:
    print(f"    [!] {w}")
