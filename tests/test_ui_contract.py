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
allocapp = open(os.path.join(ROOT, "alloc-app.part")).read()
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
for tab in ("proj", "marg", "sched"):
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
# The funding order must be reachable without a click: it belongs to the
# default Projection panel, not to a tab the reader has to find.
_proj = html.split('id="tab-proj"', 1)[-1].split("</section>", 1)[0]
check("funding order is on the home screen", 'id="homeAlloc"' in _proj)
check("its guardrails are too", 'id="homeWarnings"' in _proj)
alloc = open(os.path.join(ROOT, "allocate.html")).read()
for i in ("income", "save", "alloc", "totalVal", "breakdown", "warnings",
          "roomTable", "allocNote", "retrate", "kBack", "kRoi"):
    check(f"allocate.html has #{i}", f'id="{i}"' in alloc)
check("allocate.html carries the engine", "@engine:start" in alloc)
check("allocate.html is reachable from the calculator", 'href="allocate.html"' in html)
check("allocate.html links back", 'href="index.html"' in alloc)
check("the Allocation tab is gone from the calculator", 'id="tab-alloc"' not in html)
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

print("\n--- every button with an id is actually wired to something ---")
# The reverse of the check below, and the one that was missing: an id can
# exist in the markup while the handler that gives it behaviour was never
# inserted. A .replace() against an anchor that does not exist is a silent
# no-op, which has shipped a dead control more than once.
_theme = open(os.path.join(ROOT, "theme.part")).read()
_src = app + _theme          # theme.part owns the toggle, app.part the rest


def _wired(bid):
    if f'"{bid}"' in _src:
        return True
    # Ids built by concatenation, e.g. $("tabbtn-"+t): accept the stem.
    return "-" in bid and f'"{bid.rsplit("-", 1)[0]}-"' in _src


_btns = set(re.findall(r'<button[^>]*id="([\w-]+)"', html))
_unwired = sorted(b for b in _btns if not _wired(b))
check("no button id is missing a handler", not _unwired, f"dead controls: {_unwired}")

print("\n--- allocate.html: every id its script reads exists in the page ---")
# This block used to sit BELOW sys.exit() and had never once executed. The
# allocate page's id contract was unguarded the entire time it existed.
_alloc_html = open(os.path.join(ROOT, "allocate.html")).read()
_missing = sorted({m for m in re.findall(r'\$\("([\w-]+)"\)', allocapp)
                   if f'id="{m}"' not in _alloc_html})
check("no id read by alloc-app.part is missing from the page", not _missing,
      f"missing: {_missing}")

print(f"\n{'=' * 72}\n  {PASS} passed, {FAIL} failed\n{'=' * 72}")
sys.exit(1 if FAIL else 0)

