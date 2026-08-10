/* Compound growth + retirement engine — port of engine/projection.py.
   Verified against Python-generated fixtures. Real (today's dollars) is the
   default reporting basis throughout; nominal figures flatter and mislead. */
const CPP_2026={average_monthly_at_65:925.35,maximum_monthly_at_65:1507.65,
  early_reduction_per_month:.006,late_increase_per_month:.007};
const OAS_2026={maximum_monthly_at_65:742.31,late_increase_per_month:.006};
const DEFAULT_INFLATION=.02, DEFAULT_WITHDRAWAL=.04;

/* Fisher equation, not nominal minus inflation. */
const realRate=(nom,inf=DEFAULT_INFLATION)=>(1+nom)/(1+inf)-1;
/* (1+r)^(1/12)-1 so twelve months reproduces exactly the annual rate typed. */
const monthlyRate=r=>Math.pow(1+r,1/12)-1;

function futureValue(principal,monthly,annualRate,years,atStart=false){
  const n=Math.round(years*12), i=monthlyRate(annualRate);
  if(Math.abs(i)<1e-12) return principal+monthly*n;      // 0% would divide by zero
  const g=Math.pow(1+i,n);
  let ann=monthly*((g-1)/i);
  if(atStart) ann*=(1+i);
  return principal*g+ann;
}
function requiredMonthly(target,principal,annualRate,years){
  const n=Math.round(years*12); if(n<=0) return 0;
  const i=monthlyRate(annualRate);
  if(Math.abs(i)<1e-12) return Math.max(0,(target-principal)/n);
  const g=Math.pow(1+i,n), rem=target-principal*g;
  return rem<=0?0:rem*i/(g-1);
}
function projectionSeries(principal,monthly,annualRate,years,inflation=DEFAULT_INFLATION){
  const out=[], rr=realRate(annualRate,inflation);
  for(let y=0;y<=years;y++){
    const nominal=futureValue(principal,monthly,annualRate,y);
    const real=futureValue(principal,monthly,rr,y);
    const contributed=principal+monthly*12*y;
    out.push({year:y,nominal,real,contributed,
      growth_nominal:nominal-contributed,growth_real:Math.max(0,real-contributed)});
  }
  return out;
}
function cppEstimate(startAge=65,share=1,useMax=false){
  let base=(useMax?CPP_2026.maximum_monthly_at_65:CPP_2026.average_monthly_at_65)*share;
  const months=(startAge-65)*12;
  const f=months<0?1+months*CPP_2026.early_reduction_per_month
                  :1+months*CPP_2026.late_increase_per_month;
  return Math.max(0,base*f*12);
}
function oasEstimate(startAge=65,yearsInCanada=40){
  const base=OAS_2026.maximum_monthly_at_65*Math.min(1,Math.max(0,yearsInCanada)/40);
  const months=Math.max(0,(startAge-65)*12);
  return base*(1+months*OAS_2026.late_increase_per_month)*12;
}
function retirementReadiness(p){
  const years=Math.max(0,p.retirement_age-p.current_age);
  const wr=p.withdrawal_rate??DEFAULT_WITHDRAWAL;
  const cpp=cppEstimate(p.retirement_age,p.cpp_share??1);
  const oas=oasEstimate(Math.max(p.retirement_age,65),p.years_in_canada??40);
  const government=cpp+oas;
  const gap=Math.max(0,p.target_annual_income-government);
  const nest=wr>0?gap/wr:0;
  const rr=realRate(p.annual_rate,p.inflation??DEFAULT_INFLATION);
  const projReal=futureValue(p.current_savings,p.monthly_contribution,rr,years);
  const projNom=futureValue(p.current_savings,p.monthly_contribution,p.annual_rate,years);
  const need=requiredMonthly(nest,p.current_savings,rr,years);
  return{years_to_retirement:years,cpp_annual:cpp,oas_annual:oas,government_annual:government,
    income_gap:gap,nest_egg_needed:nest,projected_real:projReal,projected_nominal:projNom,
    total_contributed:p.current_savings+p.monthly_contribution*12*years,
    required_monthly:need,monthly_shortfall:Math.max(0,need-p.monthly_contribution),
    on_track:projReal>=nest,coverage:nest>0?projReal/nest:1,
    portfolio_income:projReal*wr,projected_retirement_income:government+projReal*wr};
}
/* How many full years a balance survives a fixed annual withdrawal.
   The 4%-rule framing answers "is this sustainable forever", which is a
   different question from "when does the money run out". Withdrawal happens
   at the START of each year: the retiree needs the cash before the market
   cooperates, and assuming otherwise flatters the result by a year. */
function depletionYears(balance,annualDraw,annualRate,maxYears=60){
  if(annualDraw<=0)return maxYears;
  let b=balance;
  for(let y=0;y<maxYears;y++){
    b-=annualDraw;
    if(b<=0)return y;
    b*=(1+annualRate);
  }
  return maxYears;
}
function costOfWaiting(p,delay=5){
  const years=Math.max(0,p.retirement_age-p.current_age);
  const rr=realRate(p.annual_rate,p.inflation??DEFAULT_INFLATION);
  const now=futureValue(p.current_savings,p.monthly_contribution,rr,years);
  const later=futureValue(p.current_savings,p.monthly_contribution,rr,Math.max(0,years-delay));
  const skipped=p.monthly_contribution*12*Math.min(delay,years);
  return{delay_years:delay,start_now:now,start_later:later,cost:Math.max(0,now-later),
    contributions_skipped:skipped,lost_per_dollar_skipped:skipped>0?(now-later)/skipped:0};
}
if(typeof module!=="undefined"&&module.exports)module.exports={CPP_2026,OAS_2026,realRate,
  monthlyRate,futureValue,requiredMonthly,projectionSeries,cppEstimate,oasEstimate,
  retirementReadiness,costOfWaiting,depletionYears};
