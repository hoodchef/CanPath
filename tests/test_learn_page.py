"""The Learn page must not drift from the tax data.

Prose is where stale numbers hide. An engine change is caught by three
parity suites, but "$8,000 a year" typed into an explanation is caught by
nothing -- it just quietly becomes wrong the year the limit moves. Every
figure on the Learn page is substituted from data/taxyear_<year>.json at
build time; this asserts the built page actually reflects the current file,
so a data edit with no rebuild fails CI.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.tax import load_year                                     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = load_year(2026)
html = open(os.path.join(ROOT, "learn.html")).read()

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS, FAIL = PASS + bool(ok), FAIL + (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'' if ok else '  ' + detail}")


def money(v):
    return "${:,.0f}".format(v) if float(v) == int(v) else "${:,.2f}".format(v)


def pct(v):
    return f"{float(v) * 100:.4f}".rstrip("0").rstrip(".") + "%"


print("\n--- Learn page renders the shipped tax data ---")

MONEY_FACTS = [
    ("TFSA annual limit", cfg["accounts"]["tfsa"]["annual_limit"]),
    ("TFSA cumulative room", cfg["accounts"]["tfsa"]["cumulative_since_2009"]),
    ("RRSP dollar limit", cfg["accounts"]["rrsp"]["dollar_limit"]),
    ("FHSA annual limit", cfg["accounts"]["fhsa"]["annual_limit"]),
    ("FHSA lifetime limit", cfg["accounts"]["fhsa"]["lifetime_limit"]),
    ("FHSA single-year max", cfg["accounts"]["fhsa"]["max_single_year_with_carryforward"]),
    ("RESP lifetime contribution", cfg["accounts"]["resp"]["lifetime_contribution"]),
    ("CESG annual max", cfg["accounts"]["resp"]["cesg_annual_max"]),
    ("CESG lifetime max", cfg["accounts"]["resp"]["cesg_lifetime_max"]),
    ("HBP withdrawal limit", cfg["accounts"]["hbp_withdrawal_limit"]),
    ("CCB max under 6", cfg["benefits"]["ccb"]["max_under_6"]),
    ("CCB max 6-17", cfg["benefits"]["ccb"]["max_6_to_17"]),
    ("CCB threshold 1", cfg["benefits"]["ccb"]["threshold_1"]),
    ("CCB threshold 2", cfg["benefits"]["ccb"]["threshold_2"]),
    ("Federal BPA base", cfg["federal"]["bpa"]["base"]),
    ("BC BPA", cfg["provinces"]["BC"]["bpa"]),
    ("BC tax reduction max", cfg["provinces"]["BC"]["tax_reduction"]["max_credit"]),
    ("CPP YMPE", cfg["payroll"]["cpp"]["ympe"]),
    ("EI max insurable", cfg["payroll"]["ei"]["max_insurable"]),
]
for name, value in MONEY_FACTS:
    check(name, money(value) in html, f"expected {money(value)}")

PCT_FACTS = [
    ("RRSP earned-income rate", cfg["accounts"]["rrsp"]["earned_income_rate"]),
    ("CESG match rate", cfg["accounts"]["resp"]["cesg_match_rate"]),
    ("Federal credit rate", cfg["federal"]["credit_rate"]),
    ("BC credit rate", cfg["provinces"]["BC"]["credit_rate"]),
    ("BC reduction phase-out", cfg["provinces"]["BC"]["tax_reduction"]["phaseout_rate"]),
    ("CPP rate", cfg["payroll"]["cpp"]["rate"]),
    ("EI rate", cfg["payroll"]["ei"]["rate"]),
]
for name, value in PCT_FACTS:
    check(name, pct(value) in html, f"expected {pct(value)}")

for n in ("1", "2", "3", "4"):
    r1 = cfg["benefits"]["ccb"]["phase1_rates"][n]
    r2 = cfg["benefits"]["ccb"]["phase2_rates"][n]
    check(f"CCB phase-1 rate, {n} child(ren)", pct(r1) in html, f"expected {pct(r1)}")
    check(f"CCB phase-2 rate, {n} child(ren)", pct(r2) in html, f"expected {pct(r2)}")

print("\n--- Fee example is computed, not asserted by hand ---")
# The most persuasive figure on the page is a compounding result. Recompute it
# from the same engine the calculator uses; a typed number that drifted from
# the formula would undermine exactly the claim it is making.
from engine.projection import future_value                            # noqa: E402

FEE_MONTHLY, FEE_YEARS, FEE_GROSS = 500, 30, 0.07
lo = future_value(0, FEE_MONTHLY, FEE_GROSS - 0.002, FEE_YEARS)
hi = future_value(0, FEE_MONTHLY, FEE_GROSS - 0.02, FEE_YEARS)
check("low-fee balance", money(round(lo)) in html, f"expected {money(round(lo))}")
check("high-fee balance", money(round(hi)) in html, f"expected {money(round(hi))}")
check("fee gap", money(round(lo - hi)) in html, f"expected {money(round(lo - hi))}")
check("contributions shown", money(FEE_MONTHLY * 12 * FEE_YEARS) in html)
check("gap really does exceed a third of contributions",
      (lo - hi) > FEE_MONTHLY * 12 * FEE_YEARS / 3,
      "the page claims it does")

print("\n--- Investing coverage ---")
for topic in ("index fund", "ETF", "MER", "diversif", "volatility",
              "Company-specific risk", "Leverage", "employer's stock",
              "National Registration Search"):
    check(f"covers {topic}", topic.lower() in html.lower())

print("\n--- Page integrity ---")
check("no unresolved template tokens", "{{" not in html,
      str(re.findall(r"\{\{[^}]*\}\}", html)[:3]))
check("links back to the calculator", 'href="index.html"' in html)
check("carries the not-advice disclaimer", "not tax, financial, or investment advice" in html)
check("declares the unmodelled benefits", "BC Family Benefit" in html)

index = open(os.path.join(ROOT, "index.html")).read()
check("calculator links to the Learn page", 'href="learn.html"' in index)

anchors = set(re.findall(r'<a href="#([\w-]+)"', html))
ids = set(re.findall(r'id="([\w-]+)"', html))
missing = sorted(anchors - ids)
check("every table-of-contents link resolves", not missing, f"dangling: {missing}")

print(f"\n{'=' * 72}\n  {PASS} passed, {FAIL} failed\n{'=' * 72}")
sys.exit(1 if FAIL else 0)
