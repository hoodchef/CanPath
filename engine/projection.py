"""
Compound growth and retirement readiness.

Design note: this module is written for people who have never been told how
any of this works. That imposes two hard requirements on the math.

1. Everything must be reportable in TODAY'S dollars. Telling someone they
   will have $2.4M in 40 years is technically true and practically a lie --
   it implies a standard of living that number will not buy. Nominal figures
   are available, but real is the default.

2. CPP and OAS must be included. The average new CPP retirement pension at
   65 is well under half the maximum, and most retirement calculators either
   ignore government pensions entirely (overstating what you must save) or
   silently assume the maximum (understating it). Both are wrong for an
   ordinary earner.
"""

from dataclasses import dataclass

# Canada.ca, January 2026. Averages matter more than maximums here: the
# maximum assumes ~39 years of contributions at the earnings ceiling.
CPP_2026 = {
    "average_monthly_at_65": 925.35,
    "maximum_monthly_at_65": 1507.65,
    "early_reduction_per_month": 0.006,   # before 65
    "late_increase_per_month": 0.007,     # after 65
}
OAS_2026 = {
    "maximum_monthly_at_65": 742.31,
    "late_increase_per_month": 0.006,
    "bump_at_75": 0.10,
    "clawback_threshold": 95323,
    "clawback_rate": 0.15,
}

DEFAULT_INFLATION = 0.02
DEFAULT_WITHDRAWAL_RATE = 0.04


def real_rate(nominal: float, inflation: float = DEFAULT_INFLATION) -> float:
    """
    Fisher equation. NOT nominal minus inflation.

    At 8% nominal and 2% inflation the naive subtraction gives 6.00%; the
    correct figure is 5.88%. Over 40 years that error compounds into tens of
    thousands of dollars of false confidence.
    """
    return (1.0 + nominal) / (1.0 + inflation) - 1.0


def monthly_rate(annual_rate: float) -> float:
    """
    Convert an annual growth rate to its true monthly equivalent.

    Uses (1+r)^(1/12)-1 rather than r/12 so that twelve months of compounding
    reproduces exactly the annual rate the user typed. r/12 quietly returns
    more than advertised.
    """
    return (1.0 + annual_rate) ** (1.0 / 12.0) - 1.0


def future_value(principal: float, monthly_contribution: float,
                 annual_rate: float, years: float,
                 contribute_at_start: bool = False) -> float:
    """
    Future value of a lump sum plus a monthly contribution stream.

    Handles the zero-rate case explicitly; the standard annuity formula
    divides by the periodic rate and blows up at exactly 0%.
    """
    n = int(round(years * 12))
    i = monthly_rate(annual_rate)

    if abs(i) < 1e-12:
        return principal + monthly_contribution * n

    growth = (1.0 + i) ** n
    fv = principal * growth
    annuity = monthly_contribution * ((growth - 1.0) / i)
    if contribute_at_start:
        annuity *= (1.0 + i)
    return fv + annuity


def required_monthly(target: float, principal: float,
                     annual_rate: float, years: float) -> float:
    """Monthly contribution needed to reach a target. Inverse of future_value."""
    n = int(round(years * 12))
    if n <= 0:
        return 0.0
    i = monthly_rate(annual_rate)

    if abs(i) < 1e-12:
        return max(0.0, (target - principal) / n)

    growth = (1.0 + i) ** n
    remaining = target - principal * growth
    if remaining <= 0:
        return 0.0
    return remaining * i / (growth - 1.0)


def projection_series(principal: float, monthly_contribution: float,
                      annual_rate: float, years: int,
                      inflation: float = DEFAULT_INFLATION) -> list:
    """
    Year-by-year balance, split into money contributed vs growth earned.

    The contributed/growth split is the single most persuasive thing you can
    show someone who has never invested: the moment growth overtakes
    contributions is the whole argument for starting early, in one image.
    """
    out = []
    r_real = real_rate(annual_rate, inflation)
    for y in range(0, years + 1):
        nominal = future_value(principal, monthly_contribution, annual_rate, y)
        real = future_value(principal, monthly_contribution, r_real, y)
        contributed = principal + monthly_contribution * 12 * y
        out.append({
            "year": y,
            "nominal": nominal,
            "real": real,
            "contributed": contributed,
            "growth_nominal": nominal - contributed,
            "growth_real": max(0.0, real - contributed),
        })
    return out


def cpp_estimate(start_age: float = 65, share_of_average: float = 1.0,
                 use_maximum: bool = False) -> float:
    """
    Annual CPP, adjusted for start age.

    Defaults to the AVERAGE rather than the maximum. Someone who has never
    looked at a Statement of Contributions is far closer to average.
    """
    base = CPP_2026["maximum_monthly_at_65"] if use_maximum else CPP_2026["average_monthly_at_65"]
    base *= share_of_average

    months = (start_age - 65) * 12
    if months < 0:
        factor = 1.0 + months * CPP_2026["early_reduction_per_month"]
    else:
        factor = 1.0 + months * CPP_2026["late_increase_per_month"]
    return max(0.0, base * factor * 12)


def oas_estimate(start_age: float = 65, years_in_canada: float = 40) -> float:
    """Annual OAS, prorated for residency and adjusted for start age."""
    base = OAS_2026["maximum_monthly_at_65"] * min(1.0, max(0.0, years_in_canada) / 40.0)
    months = max(0.0, (start_age - 65) * 12)
    return base * (1.0 + months * OAS_2026["late_increase_per_month"]) * 12


@dataclass
class RetirementPlan:
    current_age: float
    retirement_age: float
    target_annual_income: float
    current_savings: float = 0.0
    monthly_contribution: float = 0.0
    annual_rate: float = 0.08
    inflation: float = DEFAULT_INFLATION
    withdrawal_rate: float = DEFAULT_WITHDRAWAL_RATE
    years_in_canada: float = 40
    cpp_share: float = 1.0


def retirement_readiness(plan: RetirementPlan) -> dict:
    """
    Are they on track? Reported entirely in today's dollars.

    Government pensions are subtracted from the income target FIRST -- the
    portfolio only has to cover the gap. Skipping this step is what makes
    most retirement calculators produce numbers that frighten people out of
    starting at all.
    """
    years = max(0.0, plan.retirement_age - plan.current_age)

    cpp = cpp_estimate(plan.retirement_age, plan.cpp_share)
    oas = oas_estimate(max(plan.retirement_age, 65), plan.years_in_canada)
    government = cpp + oas

    gap = max(0.0, plan.target_annual_income - government)
    nest_egg_needed = gap / plan.withdrawal_rate if plan.withdrawal_rate > 0 else 0.0

    r_real = real_rate(plan.annual_rate, plan.inflation)
    projected_real = future_value(plan.current_savings, plan.monthly_contribution, r_real, years)
    projected_nominal = future_value(plan.current_savings, plan.monthly_contribution, plan.annual_rate, years)

    needed_monthly = required_monthly(nest_egg_needed, plan.current_savings, r_real, years)
    portfolio_income = projected_real * plan.withdrawal_rate

    return {
        "years_to_retirement": years,
        "cpp_annual": cpp,
        "oas_annual": oas,
        "government_annual": government,
        "income_gap": gap,
        "nest_egg_needed": nest_egg_needed,
        "projected_real": projected_real,
        "projected_nominal": projected_nominal,
        "total_contributed": plan.current_savings + plan.monthly_contribution * 12 * years,
        "required_monthly": needed_monthly,
        "monthly_shortfall": max(0.0, needed_monthly - plan.monthly_contribution),
        "on_track": projected_real >= nest_egg_needed,
        "coverage": (projected_real / nest_egg_needed) if nest_egg_needed > 0 else 1.0,
        "projected_retirement_income": government + portfolio_income,
        "portfolio_income": portfolio_income,
    }


def cost_of_waiting(plan: RetirementPlan, delay_years: float = 5) -> dict:
    """
    What procrastination costs, in today's dollars.

    For someone unaware of compounding this is the most motivating number in
    the entire application, because the loss is wildly disproportionate to
    the delay.
    """
    years = max(0.0, plan.retirement_age - plan.current_age)
    r_real = real_rate(plan.annual_rate, plan.inflation)

    now = future_value(plan.current_savings, plan.monthly_contribution, r_real, years)
    later = future_value(plan.current_savings, plan.monthly_contribution, r_real,
                         max(0.0, years - delay_years))

    skipped = plan.monthly_contribution * 12 * min(delay_years, years)
    return {
        "delay_years": delay_years,
        "start_now": now,
        "start_later": later,
        "cost": max(0.0, now - later),
        "contributions_skipped": skipped,
        "lost_per_dollar_skipped": ((now - later) / skipped) if skipped > 0 else 0.0,
    }
