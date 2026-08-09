/* Verifies the engine embedded in index.html still matches the Python
   reference. Catches the failure mode where someone edits the app's inline
   copy and forgets the reference, or vice versa. */
const fs = require("fs"), path = require("path");
const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const m = html.match(/const TAX_2026=[\s\S]*?function guardrails\(p,cfg\)\{[\s\S]*?return w;\}/);
if (!m) { console.error("FAIL: could not locate engine block in index.html"); process.exit(1); }

const tmp = path.join(require("os").tmpdir(), "canpath_shipped.js");
fs.writeFileSync(tmp, m[0] + "\nmodule.exports={TAX_2026,netPosition,effectiveMarginalRate,valueOfContribution,optimize};");
const E = require(tmp);
const fx = JSON.parse(fs.readFileSync(path.join(root, "fixtures.json"), "utf8"));

let pass = 0, fail = 0;
const chk = (n, a, b, t = 0.01) => { const ok = Math.abs(a - b) <= t; ok ? pass++ : fail++; if (!ok) console.error(`  FAIL ${n}: shipped=${a} reference=${b}`); };

for (const c of fx.marginal_cases) {
  const h = { province: "BC", child_ages: c.child_ages, partner_income: c.partner_income };
  const np = E.netPosition(c.income, h, E.TAX_2026);
  const r = E.effectiveMarginalRate(c.income, h, E.TAX_2026);
  const v = E.valueOfContribution(c.income, 10000, h, E.TAX_2026);
  const t = `${c.income}/${c.partner_income}/${c.child_ages.length}kids`;
  chk(t + " afni", np.afni, c.afni);
  chk(t + " tax", np.tax, c.tax);
  chk(t + " ccb", np.benefits, c.ccb);
  chk(t + " effective", r.effective_rate, c.effective_rate, 1e-6);
  chk(t + " clawback", r.clawback_rate, c.clawback_rate, 1e-6);
  chk(t + " refund", v.tax_refund, c.value_10k_tax_refund);
  chk(t + " benefit", v.benefit_restored, c.value_10k_benefit);
}
for (const c of fx.allocation_cases) {
  const r = E.optimize({ income: c.income, household: { province: "BC", child_ages: c.child_ages, partner_income: 0 },
    savings_capacity: c.capacity, expected_retirement_rate: c.retirement_rate, fhsa_eligible: c.fhsa_eligible,
    employer_match_rate: c.match_rate, employer_match_cap: c.match_cap }, E.TAX_2026);
  for (const [k, v] of Object.entries(c.allocation)) chk(`alloc@${c.income} ${k}`, r.allocation[k] || 0, v);
  chk(`alloc@${c.income} refund`, r.tax_refund, c.tax_refund);
  chk(`alloc@${c.income} benefit`, r.benefit_restored, c.benefit_restored);
}
console.log(`shipped index.html vs Python reference: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
