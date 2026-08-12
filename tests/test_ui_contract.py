"""Every element the app reaches for must exist in the shipped page.

The app is one file of vanilla DOM code: a mistyped or renamed id fails
silently at runtime -- $("kBalanace") returns null, the line throws, and
everything after it in update() stops running. No parity suite sees that,
because the engine is still perfectly correct; only the screen is broken.

This walks every id app.part looks up and asserts the built page defines it,
which turns a whole class of silent breakage into a failed build.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(ROOT, "app.part")).read()
theme = open(os.path.join(ROOT, "theme.part")).read()
html = open(os.path.join(ROOT, "index.html")).read()

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    PASS, FAIL = PASS + bool(ok), FAIL + (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'' if ok else '  ' + detail}")


defined = set(re.findall(r'id="([\w-]+)"', html))

# $("x"), el("x") and getElementById("x"), but not $(variable).
looked_up = set(re.findall(r'\$\("([\w-]+)"\)', app))
looked_up |= set(re.findall(r'getElementById\("([\w-]+)"\)', app + theme))
looked_up |= set(re.findall(r'\bel\("([\w-]+)"\)', theme))
# Ids the app creates at runtime rather than shipping in the markup.
RUNTIME = {"ghover", "ghit", "loadA", "loadB"}

print("\n--- Every id the app reads is defined in the page ---")
missing = sorted(looked_up - defined - RUNTIME)
check(f"{len(looked_up)} ids looked up, all present", not missing,
      f"missing from index.html: {missing}")

print("\n--- Structural contract ---")
for tab in ("proj", "marg", "alloc", "sched"):
    check(f"tab '{tab}' has a panel and a button",
          f'id="tab-{tab}"' in html and f'id="tabbtn-{tab}"' in html)

for kpi in ("kBalance", "kEmr", "kGov", "kCover", "kCross", "kRoom"):
    check(f"KPI {kpi} present", f'id="{kpi}"' in html)

check("both charts present", 'id="growthChart"' in html and 'id="emrChart"' in html)
check("chart view controls present", 'id="chartview"' in html and 'id="showBand"' in html)
check("milestones readout present", 'id="milestones"' in html)
check("depletion readout present", 'id="depletion"' in html)
check("OAS recovery readout present", 'id="oasClaw"' in html)
check("take-home table present", 'id="takehome"' in html)
check("schedule table body present", 'id="schedBody"' in html)
check("scenario slots present", 'id="slotA"' in html and 'id="slotB"' in html)
check("export controls present",
      'id="dlCsv"' in html and 'id="copyLink"' in html and 'id="doPrint"' in html)

print("\n--- Assumptions are user-controllable, not hardcoded ---")
for ctl in ("retrate", "wdraw", "cppshare", "growth"):
    check(f"{ctl} is an input", f'id="{ctl}"' in html)
check("reporting basis toggle present", 'id="basis"' in html)
check("no hardcoded 0.25 retirement rate left in app",
      "expected_retirement_rate:0.25" not in app.replace(" ", ""))

print("\n--- CSS classes the app sets are defined ---")
for cls in ("neg", "pos", "pill-var", "mark", "filled"):
    check(f".{cls} styled", f".{cls}" in html or f" {cls}" in html)
# The KPI modifier must not collide with the guardrail callout box.
check("KPI value modifier is not .warn", '.kpi .v.warn' not in html)

print(f"\n{'=' * 72}\n  {PASS} passed, {FAIL} failed\n{'=' * 72}")
sys.exit(1 if FAIL else 0)
