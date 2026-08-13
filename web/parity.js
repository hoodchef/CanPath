/* Proves the JS port reproduces the Python reference engine exactly. */
const fs = require("fs"), path = require("path");
const E = require("./engine.js");
const fx = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "fixtures.json"), "utf8"));
const cfg = E.TAX_2026;
let pass = 0, fail = 0;

function check(name, actual, expected, tol = 0.01) {
  const ok = Math.abs(actual - expected) <= tol;
  ok ? pass++ : fail++;
  if (!ok) console.log(`  [FAIL] ${name}  js=${actual}  py=${expected}`);
}

console.log("\nParity: JavaScript port vs Python reference\n" + "-".repeat(62));
for (const c of fx.marginal_cases) {
  const h = { province: "BC", child_ages: c.child_ages, partner_income: c.partner_income };
  const np = E.netPosition(c.income, h, cfg);
  const r = E.effectiveMarginalRate(c.income, h, cfg);
  const v = E.valueOfContribution(c.income, 10000, h, cfg);
  const tag = `${c.income}/${c.partner_income}/${c.child_ages.length}kids`;
  check(`${tag} afni`, np.afni, c.afni);
  check(`${tag} tax`, np.tax, c.tax);
  check(`${tag} benefits_total`, np.benefits, c.benefits_total);
  check(`${tag} bcfb`, E.totalBenefits(np.afni,h,cfg).bcfb, c.benefit_split.bcfb);
  check(`${tag} cgeb`, E.totalBenefits(np.afni,h,cfg).cgeb, c.benefit_split.cgeb);
  check(`${tag} ccb`, E.totalBenefits(np.afni,h,cfg).ccb, c.benefit_split.ccb);
  check(`${tag} statutory`, r.statutory_rate, c.statutory_rate, 1e-6);
  check(`${tag} clawback`, r.clawback_rate, c.clawback_rate, 1e-6);
  check(`${tag} effective`, r.effective_rate, c.effective_rate, 1e-6);
  check(`${tag} refund10k`, v.tax_refund, c.value_10k_tax_refund);
  check(`${tag} benefit10k`, v.benefit_restored, c.value_10k_benefit);
}
for (const c of fx.allocation_cases) {
  const profile = {
    income: c.income, household: { province: "BC", child_ages: c.child_ages, partner_income: 0 },
    savings_capacity: c.capacity, expected_retirement_rate: c.retirement_rate,
    fhsa_eligible: c.fhsa_eligible, employer_match_rate: c.match_rate, employer_match_cap: c.match_cap,
  };
  const r = E.optimize(profile, cfg);
  const tag = `alloc@${c.income}`;
  for (const [k, v] of Object.entries(c.allocation)) check(`${tag} ${k}`, r.allocation[k] || 0, v);
  check(`${tag} refund`, r.tax_refund, c.tax_refund);
  check(`${tag} benefit`, r.benefit_restored, c.benefit_restored);
  check(`${tag} deducted`, r.total_deducted, c.total_deducted);
  check(`${tag} resp grant`, r.resp_grant_earned, c.resp_grant_earned);
  // The invariant that matters most: an RESP contribution is not deductible,
  // so it must never appear in total_deducted. Derived from the allocation,
  // not from the solver's own accounting.
  const ded = (r.allocation.employer_match || 0) + (r.allocation.fhsa || 0) + (r.allocation.rrsp || 0);
  check(`${tag} RESP excluded from deducted`, r.total_deducted, ded);
  // Invariant, not just a fixture match: the solver may never recommend more
  // deductible contribution than the RRSP room can absorb. Derived from the
  // allocation, not from the solver's own room accounting -- checking the
  // internals against themselves would pass with the accounting deleted.
  const consumed = (r.allocation.employer_match || 0) * (1 + c.match_rate) + (r.allocation.rrsp || 0);
  check(`${tag} within RRSP room`, Math.max(0, consumed - c.rrsp_room), 0);
}
for (const c of fx.province_cases) {
  const h = { province: c.province, child_ages: [], partner_income: 0 };
  check(`{prov} ${c.province}@${c.income} tax`, E.combinedTax(c.income, c.province, cfg), c.combined_tax);
  check(`{prov} ${c.province}@${c.income} emr`, E.effectiveMarginalRate(c.income, h, cfg).effective_rate, c.effective_rate, 1e-6);
}
for (const c of fx.payroll_cases) {
  const d = E.payrollDeductions(c.income, E.TAX_2026);
  check(`payroll@${c.income} cpp`, d.cpp, c.cpp);
  check(`payroll@${c.income} cpp2`, d.cpp2, c.cpp2);
  check(`payroll@${c.income} ei`, d.ei, c.ei);
  check(`payroll@${c.income} total`, d.total, c.total);
}

console.log("-".repeat(62));
console.log(`  ${pass} assertions passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
