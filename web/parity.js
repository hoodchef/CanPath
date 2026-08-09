/* Proves the JS port reproduces the Python reference engine exactly. */
const fs = require("fs");
const E = require("./engine.js");
const fx = JSON.parse(fs.readFileSync("../fixtures.json", "utf8"));
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
  check(`${tag} ccb`, np.benefits, c.ccb);
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
}
console.log("-".repeat(62));
console.log(`  ${pass} assertions passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
