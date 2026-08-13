const fs=require("fs"),path=require("path");
const P=require("./projection.js");
const fx=JSON.parse(fs.readFileSync(path.join(__dirname,"..","fixtures.json"),"utf8"));
let pass=0,fail=0;
const chk=(n,a,b,t=0.01)=>{const ok=Math.abs(a-b)<=t;ok?pass++:fail++;if(!ok)console.error(`  FAIL ${n}: js=${a} py=${b}`);};
for(const c of fx.projection_cases){
  const t=`P${c.principal}/M${c.monthly}/r${c.rate}/y${c.years}`;
  chk(t+" fv",P.futureValue(c.principal,c.monthly,c.rate,c.years),c.fv);
  chk(t+" realrate",P.realRate(c.rate,0.02),c.real_rate,1e-8);
  chk(t+" fv_real",P.futureValue(c.principal,c.monthly,P.realRate(c.rate,0.02),c.years),c.fv_real);
  chk(t+" reqmonthly",P.requiredMonthly(500000,c.principal,c.rate,c.years),c.req_monthly);
}
for(const c of fx.pension_cases){
  chk(`cpp@${c.age}`,P.cppEstimate(c.age),c.cpp);
  chk(`oas@${c.age}`,P.oasEstimate(Math.max(c.age,65)),c.oas);
}
for(const c of fx.readiness_cases){
  const p={current_age:c.current_age,retirement_age:c.retirement_age,
    target_annual_income:c.target,current_savings:c.savings,
    monthly_contribution:c.monthly,annual_rate:c.rate};
  const r=P.retirementReadiness(p),w=P.costOfWaiting(p,5);
  const t=`ready@${c.current_age}->${c.retirement_age}`;
  chk(t+" gov",r.government_annual,c.government);
  chk(t+" oasgross",r.oas_gross,c.oas_gross);
  chk(t+" oasrecovery",r.oas_recovery_tax,c.oas_recovery_tax);
  chk(t+" nest",r.nest_egg_needed,c.nest_egg);
  chk(t+" projreal",r.projected_real,c.projected_real);
  chk(t+" reqmonthly",r.required_monthly,c.required_monthly);
  chk(t+" coverage",r.coverage,c.coverage,1e-6);
  chk(t+" waitcost",w.cost,c.wait_cost);
}
for(const c of fx.depletion_cases){
  chk(`deplete ${c.balance}@${c.draw}/${c.rate}`,
      P.depletionYears(c.balance,c.draw,c.rate),c.years,0);
}
for(const c of fx.oas_recovery_cases){
  const o=P.oasEstimate(65,c.years_in_canada);
  chk(`oasgross ${c.years_in_canada}y`,o,c.oas_gross);
  chk(`oasrecovery ${c.years_in_canada}y@${c.net_income}`,P.oasRecoveryTax(o,c.net_income),c.recovery);
  chk(`oasfullrec ${c.years_in_canada}y`,P.oasFullRecoveryIncome(o),c.full_recovery_income);
}
for(const c of fx.cpp_breakeven_cases){
  chk(`cppearly ${c.early}`,P.cppEstimate(c.early),c.early_annual);
  chk(`cpplate ${c.late}`,P.cppEstimate(c.late),c.late_annual);
  chk(`cppbreakeven ${c.early}->${c.late}`,P.cppBreakevenAge(c.early,c.late),c.breakeven_age,0.05);
}
console.log(`projection JS port vs Python reference: ${pass} passed, ${fail} failed`);
process.exit(fail?1:0);
