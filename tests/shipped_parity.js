/* Verifies the engine embedded in index.html still matches the Python
   reference. Catches the failure mode where someone edits the app's inline
   copy and forgets the reference, or vice versa. */
const fs = require("fs"), path = require("path");
const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const m = html.match(/const TAX_2026=[\s\S]*?function guardrails\(p,cfg\)\{[\s\S]*?return w;\}/);
if (!m) { console.error("FAIL: could not locate tax engine block in index.html"); process.exit(1); }
const pm = html.match(/const CPP_2026=[\s\S]*?function costOfWaiting\(p,delay=5\)\{[\s\S]*?\n\}/);
if (!pm) { console.error("FAIL: could not locate projection engine block in index.html"); process.exit(1); }

const tmp = path.join(require("os").tmpdir(), "canpath_shipped.js");
fs.writeFileSync(tmp, m[0] + "\n" + pm[0] +
  "\nmodule.exports={TAX_2026,netPosition,effectiveMarginalRate,valueOfContribution,optimize," +
  "realRate,futureValue,requiredMonthly,cppEstimate,oasEstimate,retirementReadiness,costOfWaiting};");
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
for (const c of fx.projection_cases) {
  const t = `P${c.principal}/M${c.monthly}/r${c.rate}/y${c.years}`;
  chk(t + " fv", E.futureValue(c.principal, c.monthly, c.rate, c.years), c.fv);
  chk(t + " realrate", E.realRate(c.rate, 0.02), c.real_rate, 1e-8);
  chk(t + " fv_real", E.futureValue(c.principal, c.monthly, E.realRate(c.rate, 0.02), c.years), c.fv_real);
  chk(t + " reqmonthly", E.requiredMonthly(500000, c.principal, c.rate, c.years), c.req_monthly);
}
for (const c of fx.pension_cases) {
  chk(`cpp@${c.age}`, E.cppEstimate(c.age), c.cpp);
  chk(`oas@${c.age}`, E.oasEstimate(Math.max(c.age, 65)), c.oas);
}
for (const c of fx.readiness_cases) {
  const p = { current_age: c.current_age, retirement_age: c.retirement_age,
    target_annual_income: c.target, current_savings: c.savings,
    monthly_contribution: c.monthly, annual_rate: c.rate };
  const r = E.retirementReadiness(p), w = E.costOfWaiting(p, 5);
  const t = `ready@${c.current_age}->${c.retirement_age}`;
  chk(t + " gov", r.government_annual, c.government);
  chk(t + " nest", r.nest_egg_needed, c.nest_egg);
  chk(t + " projreal", r.projected_real, c.projected_real);
  chk(t + " reqmonthly", r.required_monthly, c.required_monthly);
  chk(t + " waitcost", w.cost, c.wait_cost);
}
console.log(`shipped index.html vs Python reference: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
