# CanPath

**What your next dollar is actually worth — in Canada.**

Your tax bracket is not your marginal rate. Once income-tested benefits start
clawing back, a BC couple with three kids earning between roughly $58,600 and
$67,500 loses **56.2¢** of the next dollar earned, while their posted bracket
advertises 28.2¢. That 28-point gap is real money and appears nowhere on a tax
return.

It comes from four programs at once: federal and BC income tax, the Canada
Child Benefit, the BC Family Benefit and the Canada Groceries and Essentials
Benefit. Each is documented on its own page; nothing adds them up for you.

CanPath surfaces it, then tells you where your savings should actually go.

Built for people who have never been told how any of this works — not for
the financially fluent.

- **A six-metric KPI strip** — balance, effective marginal rate, government
  help, target coverage, crossover year and registered room used
- **A dedicated Allocate page** — income in, funding order out: exactly how
  much belongs in each account this year, and why that order
- **Three analysis tabs** on the calculator — Projection, Marginal rate, Schedule
- **The marginal-rate curve**, income tax and benefit clawback stacked across
  the whole income range, with your own position marked
- **Growth over 5–40 years**, showing the year growth overtakes contributions
- **Are you on track** — CPP and OAS counted first, so the target isn't inflated
- **Ranked funding order** across employer match, FHSA, RRSP and TFSA, in the
  order the solver actually funded them
- **Every assumption is yours to set** — growth, expected withdrawal tax rate,
  sustainable withdrawal rate, CPP relative to average, and the reporting basis
- **Scenario A/B compare** — delta in the rail, and both saved plans drawn as
  ghost curves on the chart
- **A sensitivity band** at ±2 percentage points of growth, so the single
  deterministic line does not imply precision the model lacks
- **Target line and funded age** — the nest egg your target implies, and the
  year the plan reaches it
- **Milestones** — the age you cross $100k, $250k, $500k, $1M
- **Depletion analysis** — how long the balance funds your draw, in years and
  to an age, since a 4% coverage figure never says when the money runs out
- **Take-home breakdown** — gross to net through federal tax, BC tax, CPP and EI
- **OAS recovery tax** — the retirement-side clawback: 15¢ of every dollar of
  individual net income above $95,323, netted out of the readiness verdict
- **Linear or log scale**, because forty years of compounding hides the first ten
- **Year-by-year schedule**, CSV export, print report, and a permalink that
  encodes the whole scenario in the URL
- **The cost of waiting** — what a five-year delay actually costs
- Guardrails that refuse to recommend an RRSP when it would destroy value
- A **Learn** page covering every account, credit, clawback and pension the
  calculator touches, plus budgeting, emergency funds and debt
- Light and dark themes, following the operating system until you pick one
- Runs entirely in your browser. Nothing you type is transmitted or stored;
  the sole `localStorage` key is the theme preference.

### Two decisions that make the numbers differ from other calculators

**Nominal dollars by default.** Balances are future dollars, with no inflation
adjustment. The reporting basis is a control in the Assumptions group, so
today's dollars are one click away: the engine supports both bases — `real_rate`
implements the Fisher equation and `retirement_readiness` takes an `inflation`
argument — and the nominal default simply passes `inflation: 0`, which makes the
conversion a no-op.

Note the consequence in *Are you on track?*: CPP and OAS are quoted at today's
payment rates while the projected balance is in future dollars, so the two
sides of that comparison are on different footings. Both are indexed in
reality. The panel says so.

**Average CPP, not maximum.** The maximum ($1,507.65/mo) assumes ~39 years of
contributions at the earnings ceiling. The average new pension at 65 is
$925.35/mo. Using the maximum understates what people need to save; ignoring
government pensions entirely overstates it. Both are common, and both are wrong
for an ordinary earner.

## Run it

**Locally:** open `index.html`. No build, no server, no dependencies.
`allocate.html` and `learn.html` sit beside it, all three linked from the header.

**As an installable app:** serve the folder over HTTPS (or `localhost`) and the
service worker activates. On iOS, Safari → Share → *Add to Home Screen*. On
Android/desktop Chrome, an install prompt appears. It then launches standalone
and works fully offline.

```bash
python3 -m http.server 8000    # then visit http://localhost:8000
```

> The service worker requires HTTPS or localhost. Opened directly via `file://`
> the app still works — it just is not installable.

## Correctness

Financial math bugs destroy trust permanently, so correctness is enforced by a
three-stage chain rather than by review:

```
Python reference  →  fixtures.json  →  JavaScript port  →  shipped index.html
  150 assertions    tools/gen_fixtures.py   492 assertions   463 assertions
```

The closed-form compound-growth formulas are additionally checked against a
deliberately naive month-by-month loop. If the two ever disagree, the formula
is wrong — this caught a $21,000 error in a hand-computed test expectation.

`tests/shipped_parity.js` extracts the engine from `index.html` itself and
re-runs it against fixtures generated by the Python reference. The code you
open is *provably* identical to the verified reference, not merely similar.
CI runs all three stages on every push.

```bash
python3 tools/gen_fixtures.py       # regenerate fixtures from the reference
python3 tests/test_engine.py        # tax reference
python3 tests/test_projection.py    # growth + retirement reference
python3 tests/test_learn_page.py    # Learn page prose vs the tax data
python3 tests/test_ui_contract.py   # every id the app reads exists in the page
node web/parity.js                  # JS tax port vs reference
node web/parity_projection.js       # JS projection port vs reference
node tests/shipped_parity.js        # shipped index.html vs reference
python3 validate.py                 # readable scenario output
```

`fixtures.json` is **generated** by `tools/gen_fixtures.py`. Change the engine
and you must regenerate it, or the two ports are being verified against the
previous engine and will pass while the shipped app is wrong. CI fails on a
stale file.

`index.html`, `allocate.html` and `learn.html` are **generated** by `build.py`.
Edit `head.part`, `body.part`, `app.part`, `allocate.part`, `alloc-app.part`,
`learn.part`, `theme.part`, `engine.part` or `web/projection.js`, then rebuild — never edit a built file directly, or the
next build discards it. CI fails if either committed page does not match its
sources.

Both pages share `head.part` (palette, styles, masthead, theme bootstrap) and
`theme.part` (the toggle). Page-specific values — title, description, header
link — are `{{TOKEN}}` substitutions filled by `build.py`.

**Every figure quoted in Learn-page prose is substituted from
`data/taxyear_<year>.json` at build time**, never typed. A hard-coded
"$8,000 a year" is invisible to the parity suites and silently becomes wrong
the year a limit moves; `tests/test_learn_page.py` asserts the built page
matches the current data file, so a data edit without a rebuild fails CI.

The shipped tax engine lives in `engine.part`. `web/engine.js` is a second,
readable port of the same reference; both are parity-checked, but only
`engine.part` reaches users. Behaviour changes go in `engine/` (the reference),
then both ports.

## Deploy

The site is static: three generated HTML files, a manifest, a service worker
and four icons. No build step runs on the server.

**GitHub Pages** — Settings → Pages → Source: *Deploy from a branch*, branch
`main`, folder `/ (root)`. It publishes at `https://<user>.github.io/CanPath/`.
Every path in the project is relative, so the subdirectory works untouched.

`.nojekyll` is committed deliberately: Pages runs Jekyll by default, which
silently drops files beginning with an underscore — this repo has
`_a11y_repro.html`.

**A custom domain** — add a `CNAME` file containing the bare hostname, then
point DNS at GitHub:

| Record | Host | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `<user>.github.io` |

Then tick *Enforce HTTPS* once the certificate issues. **The service worker
requires HTTPS**, so the app is only installable on a real domain or on
`localhost` — over plain HTTP it runs but will not install or work offline.

Any static host works equally well (Netlify, Cloudflare Pages, S3). There is
nothing GitHub-specific in the app itself.

## Data sources

| Input | Source |
|---|---|
| Federal brackets, BPA | CRA 2026, indexed 2.0%, lowest rate 14% |
| BC brackets, BPA, tax reduction | Province of B.C., indexed 2.2%, bottom rate 5.60% |
| Canada Child Benefit | 2026–27 benefit year, indexed 2.0% |
| BC Family Benefit | 2026–27, **user-supplied, unverified** |
| Canada Groceries and Essentials Benefit | July 2026 on, **user-supplied, unverified** |
| RRSP / TFSA / FHSA limits | CRA 2026 |
| CPP and OAS | Canada.ca, January 2026 (average and maximum) |

All rates live in `data/taxyear_2026.json`. **Annual updates are a data edit,
never a code change.** Bump `CACHE` in `sw.js` when you ship a new tax year, or
returning users keep running last year's brackets from cache.

> BC paused bracket indexation for 2027–2030. Do **not** auto-index forward.

## Known limits

- British Columbia only. Each province is a config block; Quebec is a separate
  product (own return, QPP, abatement, French-language obligations).
- GIS and OAS clawback are flagged by guardrails but not yet modelled, so
  retirement-age scenarios are incomplete.
- **BCFB and CGEB figures are user-supplied and NOT independently verified.**
  They are recorded as such in `data/taxyear_2026.json`. The BC Family Benefit
  and the Canada Groceries and Essentials Benefit are now modelled, but confirm
  the parameters against CRA/BC publications before relying on the output.
- The OAS recovery tax is now modelled; GIS is still flagged by guardrails
  rather than modelled, so retirement-age scenarios remain incomplete.
- The recovery tax is assessed against the **stated target income**, not a
  solved fixed point. Retirement net income depends on the portfolio, which
  depends on the gap, which depends on the clawback — the target breaks that
  circularity and is what the user intends to live on.
- The solver optimizes first-year value. The growth projection reinvests the
  government help, in two phases: while FHSA room lasts, and after it is gone.
  Within a phase the rate is held flat, without recursion.
- Investment growth is a flat assumed rate. No sequence-of-returns risk, no
  Monte Carlo — a 30-year average hides a great deal of variability.
- CPP and EI are excluded from the marginal rate **by design**: they are levied
  on gross employment income and are unaffected by an RRSP deduction.

## Not advice

This is an educational model. It is not tax, financial, or investment advice,
and it does not account for every credit, deduction, or personal circumstance.
Confirm your own contribution room in CRA My Account before contributing.

Note that "Financial Planner" and "Financial Advisor" are protected titles in
Ontario and Saskatchewan. This project deliberately describes itself as a
calculator and model.

MIT licensed.
