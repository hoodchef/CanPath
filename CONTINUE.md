# Continuing this project

Written for whoever picks CanPath up next, human or model. The README covers
what the project *is*. This covers what a fresh reader cannot recover from the
code, the tests or the git history: which numbers are trustworthy, which are
not, what is blocked and on what, and the failure modes this codebase has
already produced twice.

Current head at time of writing: `3fb9335`. Remote: `github.com/hoodchef/CanPath`.

---

## 1. The one rule

**Never invent a Canadian tax parameter.** Not a bracket, not a threshold, not
a phase-out rate, not a benefit maximum.

Every figure in `data/taxyear_2026.json` came from the project owner and is
recorded in `source_notes` with its provenance. If a figure is needed and not
present, the correct move is to say so and stop — not to supply a plausible
one. A fabricated rate would pass every test in the repo, because
`fixtures.json` is generated *from* whatever the data file says, and would then
produce confidently wrong advice.

This has been tested in practice: several times during development the honest
answer was "blocked on data", and saying so was right each time.

---

## 2. Working discipline

Any change to a number follows this order. Skipping a step has produced a bug
every time it has been skipped.

1. **Python reference first** — `engine/*.py`. This is the source of truth.
2. **Both JS ports** — `engine.part` (shipped, compact) and `web/engine.js`
   (readable). `web/projection.js` is the shipped projection engine.
3. **Regenerate fixtures** — `python3 tools/gen_fixtures.py`. Fixtures are
   generated from the reference; hand-editing them defeats the whole chain.
4. **Rebuild** — `python3 build.py`. `index.html`, `allocate.html` and
   `learn.html` are generated. Never edit them.
5. **Run all seven suites** (see README).
6. **Mutation-test the change.** Copy the repo to `/tmp`, inject a plausible
   bug, rebuild, and confirm a suite fails. See §4.
7. **Verify in a browser.** The suites verify the engine, not the interface.
   See §5.

For anything with more than one province or account, the JS blocks should be
**generated from the JSON** rather than transcribed. `provinces` and
`provincial_child_benefits` already are — see the splice scripts in the git
history for `6202afa` and `3fb9335`.

---

## 3. Figures that are NOT independently verified

All of these work correctly as implemented. The question is whether the inputs
are right. Every one is also recorded in `data/taxyear_2026.json` under
`source_notes`.

| Item | Status |
|---|---|
| **Nova Scotia child benefit, 50%** | **Contradicts its own source.** The supplied table said "full below $26,000, partial $26,000–$34,000", which forces **19.06%** for one child. At 50% one child reaches zero at **$29,050**, not $34,000. The explicit rate was preferred over the inferred one. It drives an NS peak effective marginal rate of **79.0%** — the highest in the model. **Re-check this first.** |
| **Alberta, ~11% and ~15%** | Supplied as approximate. The only inexact figures in the file. Its working component is modelled as available in full above the $2,760 employment floor because no phase-in rate was given. |
| **BC Family Benefit** | User-supplied, unverified. Two submissions conflicted on the bottom rate (5.60% vs 5.06%) and the tax reduction (690 vs 575). Resolved in favour of 5.60%/690 by explicit decision — the later block matched BC's pre-2026 figures. |
| **CGEB (renamed GST/HST credit)** | User-supplied, unverified. An earlier 2% rate did not reconcile; 5% does exactly ($679 ÷ 5% + $46,432 = $60,012, the stated zero point). |
| **All nine provincial bracket tables** | User-supplied, unverified. |
| **Ontario** | Ships with **no low-income reduction and no surtax** — the supplied block left them null. Understates ON tax at higher incomes. |
| **Newfoundland** | Uses `base_amount` 842 only. The per-dependant 563 cannot apply because `provincial_tax` takes no household, and the supplied `phaseout_end` of 30,491 reconciles with neither 842 (zero at 29,454) nor 842+563 (32,972) at 16%. |
| **PEI child benefit** | A literal two-tier step, so it produces **real cliffs** at $45,000 and $80,000. Differencing across the $80,000 step reports 630% for two children; a $1 delta would report 63,000%. The app names the cliff instead of printing the number. |

---

## 4. Test-integrity traps this repo has already fallen into

Three times a suite passed against a bug. The pattern is always the same and is
worth checking for explicitly.

**A fixture set that never reaches the binding constraint.** Every occurrence:

- Widening CCB's `age < 18` to `age < 19` passed everything, because every
  fixture used either all-eligible children or a lone 18-year-old — and a lone
  18-year-old is rejected by the `n == 0` early return, never by `ccb_max`'s
  own age bands. Only a *mixed* household reaches that boundary.
- Making the BCFB single-parent supplement unconditional passed everything,
  because every partnered fixture sat above the point where the benefit floor
  binds, and above it both cases collapse to the same number.
- Dropping the OAS recovery from `retirement_readiness` passed everything,
  because all four readiness fixtures had targets below the $95,323 threshold.
- Deleting the RESP CESG lifetime cap passed everything, because every fixture
  leaves the $7,200 untouched so only the annual $2,500 ever binds.

**When adding a constraint, add a fixture where that constraint is what binds.**

**An invariant checked against the internals it polices.** The first RRSP-room
invariant read the solver's own bookkeeping, so deleting the bookkeeping made
it pass. Invariants must be derived from the *output* — e.g.
`total_deducted == employer_match + fhsa + rrsp`, computed from the allocation.

**A mutation harness that lies.** One throwaway harness reported a caught
mutation as surviving. Re-running the mutation directly showed 17 failures.
Verify a surprising harness result before acting on it.

---

## 5. Failure modes in the UI layer

The seven suites do not execute the interface. Three bugs shipped that no suite
would have caught, all found only by driving the built page in a browser:

- `syncURL()` was called but never defined — the `.replace()` that was supposed
  to insert it targeted an anchor string that did not exist in `app.part`.
- The income slider's `min` was changed in JS but not in the markup.
- The "Use this figure" button shipped **inert**, same cause.

**A Python `.replace()` against a missing anchor is a silent no-op.** Always
`assert` the anchor exists before replacing, and assert the result afterwards.

`tests/test_ui_contract.py` now guards both directions: every id the script
reads must exist in the markup, *and* every button id in the markup must be
referenced by `app.part` or `theme.part` (allowing for ids built by
concatenation like `"tabbtn-" + t`). It also pins the funding order to the
default Projection panel, so moving it behind a tab fails the suite.

Note also: `innerText` returns `""` for content inside a closed `<details>`.
Use `textContent` when verifying collapsed sections, or the measurement lies.

---

## 6. Blocked on data

Nothing here is a code problem.

- **Territories (YT, NT, NU)** — absent entirely. Need bracket tables, BPAs and
  any territorial child benefit.
- **Quebec** — deliberately excluded. Needs its own return, QPP rather than
  CPP, and the 16.5% federal abatement, none of which the engine models. Treat
  as a separate product.
- **Ontario surtax and low-income reduction** — threshold and rate.
- **Newfoundland** — a per-dependant credit needs `provincial_tax` to accept a
  household; the signature change is small but the reconciliation above should
  be resolved first.
- **NL Early Childhood Nutrition Supplement** — up to $150/month per child
  under 5, mentioned but no threshold or rate supplied.
- **GIS** — guardrails warn about it; it is not modelled. Needs rates.
- **AB working component phase-in** — the >$2,760 floor is modelled as a step.

---

## 7. Deployment state

- Repo is live and pushed. SSH auth is configured and working; the host key was
  pinned only after checking its fingerprint against GitHub's published
  ED25519 fingerprint.
- **GitHub Pages is not yet enabled.** Settings → Pages → Deploy from a branch
  → `main` → `/ (root)`. Everything else is ready: all paths are relative, so
  the `/CanPath/` subdirectory works untouched.
- **No custom domain.** The owner has to buy one; DNS records are in the
  README's Deploy section.
- `.nojekyll` is committed deliberately — Pages runs Jekyll by default, which
  drops underscore-prefixed files, and this repo has `_a11y_repro.html`.
- **The service worker requires HTTPS.** On `github.io` or a custom domain with
  Enforce HTTPS the app installs and works offline. Over plain HTTP it runs but
  will not install.

---

## 8. Known duplication worth watching

The funding order renders from **two** code paths — `app.part` (home screen)
and `alloc-app.part` (Allocate page) — both calling the same `optimize()`. The
maths cannot diverge; that is fixture-verified. The *presentation* can, and
already did once: largest-remainder rounding was fixed in one before the other.
Extracting a shared renderer into its own `.part` is small and would close it.

`ACCOUNTS` (the row copy) is currently duplicated in both files too.

---

## 9. Process notes

- The owner has hit **monthly spend limits** twice. A nine-agent audit workflow
  died mid-flight and returned nothing usable.
- Inline work has consistently outperformed subagents on this codebase. The
  audit that found the CCB coverage hole, the contrast failure and the URL
  clamp was done inline after the workflow died. Four design agents did produce
  genuinely good specs — but only after ~13 minutes each and ~500k tokens
  total, and their best findings were verified defects that inline inspection
  also surfaces.
- Disproving a hypothesis counts. URL markup injection, `Infinity` via
  `?income=1e999`, and a performance concern were all investigated and found
  *not* to be problems — worth as much as the confirmed bugs, and worth
  recording so nobody re-litigates them. (Number inputs sanitise hostile
  strings to `""`; worst-case recompute is 3.5 ms.)

---

## 10. Highest-value next steps

1. **Re-check the Nova Scotia 50%.** It is the least trustworthy number in the
   model and it drives the highest rate in it.
2. **Enable GitHub Pages.** One switch; the app is otherwise deploy-ready.
3. **Rewrite the README headline.** It still leads with BC's 56.2¢, but Alberta
   at 66.5% and Nova Scotia at 79% are now the more striking numbers — assuming
   NS survives step 1.
4. **Extract the shared funding-order renderer** (§8).
5. **GIS**, then **territories**, then **Quebec** — in that order of value, all
   blocked on data.
