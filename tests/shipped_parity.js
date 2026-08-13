/* Verifies the engine embedded in index.html still matches the Python
   reference. Catches the failure mode where someone edits the app's inline
   copy and forgets the reference, or vice versa. */
const fs = require("fs"), path = require("path");
const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");

/* Extract by sentinel marker rather than by matching the code's own shape.
   The old patterns keyed off a function signature, so a renamed argument
   made this test silently unable to find the engine -- the one failure mode
   a shipped-code parity check must never have. */
function block(name) {
  const m = html.match(new RegExp(`/\\* @${name}:start \\*/([\\s\\S]*?)/\\* @${name}:end \\*/`));
  if (!m) { console.error(`FAIL: could not locate @${name} block in index.html`); process.exit(1); }
  return m[1];
}
const m = [block("engine")];
const pm = [block("projection")];

const tmp = path.join(require("os").tmpdir(), "canpath_shipped.js");
fs.writeFileSync(tmp, m[0] + "\n" + pm[0] +
  "\nmodule.exports={TAX_2026,totalBenefits,netPosition,effectiveMarginalRate,valueOfContribution,optimize," +
  "realRate,futureValue,requiredMonthly,cppEstimate,oasEstimate,retirementReadiness,costOfWaiting,depletionYears,cppBreakevenAge,payrollDeductions,oasRecoveryTax,oasFullRecoveryIncome};");
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
  chk(t + " benefits_total", np.benefits, c.benefits_total);
  chk(t + " bcfb", E.totalBenefits(np.afni,h,E.TAX_2026).bcfb, c.benefit_split.bcfb);
  chk(t + " cgeb", E.totalBenefits(np.afni,h,E.TAX_2026).cgeb, c.benefit_split.cgeb);
  chk(t + " ccb", E.totalBenefits(np.afni,h,E.TAX_2026).ccb, c.benefit_split.ccb);
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
  chk(`alloc@${c.income} deducted`, r.total_deducted, c.total_deducted);
  // The shipped app must respect contribution room too, not just the
  // reference. Derived from the allocation rather than the solver's own
  // room accounting, so deleting that accounting fails the test.
  const consumed = (r.allocation.employer_match || 0) * (1 + c.match_rate) + (r.allocation.rrsp || 0);
  chk(`alloc@${c.income} within RRSP room`, Math.max(0, consumed - c.rrsp_room), 0);
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
  chk(t + " oasgross", r.oas_gross, c.oas_gross);
  chk(t + " oasrecovery", r.oas_recovery_tax, c.oas_recovery_tax);
  chk(t + " nest", r.nest_egg_needed, c.nest_egg);
  chk(t + " projreal", r.projected_real, c.projected_real);
  chk(t + " reqmonthly", r.required_monthly, c.required_monthly);
  chk(t + " waitcost", w.cost, c.wait_cost);
}
for (const c of fx.payroll_cases) {
  const d = E.payrollDeductions(c.income, E.TAX_2026);
  chk(`payroll@${c.income} cpp`, d.cpp, c.cpp);
  chk(`payroll@${c.income} cpp2`, d.cpp2, c.cpp2);
  chk(`payroll@${c.income} ei`, d.ei, c.ei);
  chk(`payroll@${c.income} total`, d.total, c.total);
}
for (const c of fx.depletion_cases) {
  chk(`deplete ${c.balance}@${c.draw}`, E.depletionYears(c.balance, c.draw, c.rate), c.years, 0);
}
for(const c of fx.oas_recovery_cases){
  const o=E.oasEstimate(65,c.years_in_canada);
  chk(`oasgross ${c.years_in_canada}y`,o,c.oas_gross);
  chk(`oasrecovery ${c.years_in_canada}y@${c.net_income}`,E.oasRecoveryTax(o,c.net_income),c.recovery);
  chk(`oasfullrec ${c.years_in_canada}y`,E.oasFullRecoveryIncome(o),c.full_recovery_income);
}
for(const c of fx.cpp_breakeven_cases){
  chk(`cppearly ${c.early}`,E.cppEstimate(c.early),c.early_annual);
  chk(`cpplate ${c.late}`,E.cppEstimate(c.late),c.late_annual);
  chk(`cppbreakeven ${c.early}->${c.late}`,E.cppBreakevenAge(c.early,c.late),c.breakeven_age,0.05);
}
console.log(`shipped index.html vs Python reference: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
