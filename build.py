#!/usr/bin/env python3
"""Assemble index.html and learn.html from the .part sources.

Both files are GENERATED. Edit the .part files, never the output.

The tax engine lives in engine.part and the projection engine in
web/projection.js. Previously the tax engine was re-extracted from
index.html -- the build read its own output, so the shipped engine had no
source file and editing web/engine.js changed nothing.

Every figure quoted in the Learn page prose is substituted from
data/taxyear_<year>.json at build time. Typing "$8,000" into the copy would
mean next year's data edit silently leaves the explanation wrong, which is
the one failure the rest of this project is built to prevent.
"""
import json
import re
import sys

from engine.projection import future_value

YEAR = 2026
CFG = json.load(open(f"data/taxyear_{YEAR}.json"))


def _walk(path):
    node = CFG
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            raise KeyError(f"no such tax-data path: {path}")
        node = node[key]
    return node


def _money(v):
    return "${:,.0f}".format(v) if float(v) == int(v) else "${:,.2f}".format(v)


def _pct(v):
    s = f"{float(v) * 100:.4f}".rstrip("0").rstrip(".")
    return s + "%"


def render(text, page_vars):
    """Replace {{$path}} with money, {{%path}} with a percentage, {{NAME}}
    with a page variable."""
    def sub(m):
        token = m.group(1)
        if token in page_vars:
            return page_vars[token]
        if token.startswith("$"):
            return _money(_walk(token[1:]))
        if token.startswith("%"):
            return _pct(_walk(token[1:]))
        raise KeyError(f"unresolved template token: {{{{{token}}}}}")
    return re.sub(r"\{\{([^}]+)\}\}", sub, text)


HEAD = open("head.part").read()
BODY = open("body.part").read()
APP = open("app.part").read()
THEME = open("theme.part").read()
LEARN = open("learn.part").read()

engine = open("engine.part").read()
proj = open("web/projection.js").read()
# strip the node export line from the projection port
proj = proj[:proj.index('if(typeof module!=="undefined"')]


def write(path, head_vars, body, scripts):
    # Sentinel markers, not regexes over the code itself: tests/shipped_parity.js
    # lifts these blocks back out to re-run them against the Python fixtures.
    # The previous approach pattern-matched on a function signature, so renaming
    # an argument silently broke the test that proves the shipped app is correct.
    out = render(HEAD, head_vars) + render(body, head_vars) + scripts
    out += "\n</body>\n</html>\n"
    if "{{" in out:
        stray = re.findall(r"\{\{[^}]*\}\}", out)[:3]
        sys.exit(f"FAIL: unresolved template tokens in {path}: {stray}")
    open(path, "w").write(out)
    print(f"built {path}: {len(out)} chars")


# The fee example is computed with the same verified compounding the
# calculator uses, not typed. A number this persuasive has to be reproducible.
FEE_MONTHLY, FEE_YEARS, FEE_GROSS = 500, 30, 0.07
MER_LOW, MER_HIGH = 0.002, 0.02
_fee_lo = future_value(0, FEE_MONTHLY, FEE_GROSS - MER_LOW, FEE_YEARS)
_fee_hi = future_value(0, FEE_MONTHLY, FEE_GROSS - MER_HIGH, FEE_YEARS)

PAGE_COMMON = {
    "PAGE_YEAR": str(YEAR),
    "PAGE_RRSP_CUSHION": "$2,000",
    "PAGE_CGEB_AGE": str(CFG["benefits"]["cgeb"]["child_age_limit"]),
    "FEE_MONTHLY": _money(FEE_MONTHLY),
    "FEE_YEARS": str(FEE_YEARS),
    "FEE_GROSS": _pct(FEE_GROSS),
    "MER_LOW": _pct(MER_LOW),
    "MER_HIGH": _pct(MER_HIGH),
    "FEE_LOW": _money(round(_fee_lo)),
    "FEE_HIGH": _money(round(_fee_hi)),
    "FEE_GAP": _money(round(_fee_lo - _fee_hi)),
    "FEE_CONTRIB": _money(FEE_MONTHLY * 12 * FEE_YEARS),
}


def page(extra):
    v = dict(PAGE_COMMON)
    v.update(extra)
    return v


write("index.html",
      page({"PAGE_TITLE": "CanPath — what your money could become",
            "PAGE_DESC": "See what your savings could become, and how much the "
                         "Canadian government will help you get there.",
            "NAV_HREF": "learn.html", "NAV_TEXT": "Learn"}),
      BODY,
      "\n<script>\n/* ENGINE — ported from Python reference, parity-verified in CI */\n"
      + "/* @engine:start */\n" + engine + "/* @engine:end */\n"
      + "\n/* @projection:start */\n" + proj + "/* @projection:end */\n"
      + "\n" + APP + "\n" + THEME + "\n</script>\n")

write("learn.html",
      page({"PAGE_TITLE": "Learn — CanPath",
            "PAGE_DESC": "Plain-English explanations of Canadian registered accounts, "
                         "tax credits, budgeting, emergency funds and debt.",
            "NAV_HREF": "index.html", "NAV_TEXT": "← Calculator"}),
      LEARN,
      "\n<script>\n" + THEME + "\n</script>\n")
