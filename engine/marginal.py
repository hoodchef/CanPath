"""
Effective marginal rate -- tax PLUS benefit clawback.

The number every Canadian thinks they know (their bracket) and the number
that actually governs their decisions (this one) can differ by 25+ points.
"""

from .tax import combined_tax, load_year
from .benefits import Household, total_benefits


def net_position(income: float, household: Household, cfg: dict,
                 deduction: float = 0.0) -> dict:
    """
    Household position at a given income, after a deduction (e.g. RRSP/FHSA).

    Both taxable income and AFNI are reduced by the deduction -- that dual
    effect is precisely what makes registered contributions worth more than
    the refund alone.
    """
    taxable = max(0.0, income - deduction)
    partner = max(0.0, household.partner_income)

    # AFNI is the sum of BOTH partners' net incomes (line 23600 each).
    # Modelling only the primary earner overstates CCB for dual-income
    # households -- often by thousands of dollars.
    afni = taxable + partner

    tax = combined_tax(taxable, household.province, cfg)
    partner_tax = combined_tax(partner, household.province, cfg) if partner else 0.0
    benefits = total_benefits(afni, household, cfg)

    return {
        "gross_income": income,
        "partner_income": partner,
        "deduction": deduction,
        "taxable_income": taxable,
        "afni": afni,
        "tax": tax,
        "partner_tax": partner_tax,
        "household_tax": tax + partner_tax,
        "benefits": benefits["total"],
        "net_cash": income + partner - deduction - tax - partner_tax + benefits["total"],
        "net_burden": tax + partner_tax - benefits["total"],
    }


def effective_marginal_rate(income: float, household: Household, cfg: dict,
                            delta: float = 100.0) -> dict:
    """
    Marginal rate on the next dollar, decomposed into tax and clawback.

    Numeric differentiation with a $100 step. Analytic differentiation is
    possible but fragile across bracket and threshold boundaries; the
    numeric approach is robust and the cost is irrelevant.
    """
    lo = net_position(income, household, cfg)
    hi = net_position(income + delta, household, cfg)

    tax_rate = (hi["tax"] - lo["tax"]) / delta
    clawback_rate = (lo["benefits"] - hi["benefits"]) / delta

    return {
        "income": income,
        "statutory_rate": tax_rate,
        "clawback_rate": clawback_rate,
        "effective_rate": tax_rate + clawback_rate,
    }


def value_of_contribution(income: float, contribution: float,
                          household: Household, cfg: dict) -> dict:
    """
    True first-year value of a deductible contribution (RRSP or FHSA).

    Returns the tax refund, the benefit restored, and the blended return on
    the contributed dollar. For families near a CCB phase-out threshold the
    benefit component frequently exceeds the refund itself.
    """
    before = net_position(income, household, cfg, deduction=0.0)
    after = net_position(income, household, cfg, deduction=contribution)

    refund = before["tax"] - after["tax"]
    benefit_gain = after["benefits"] - before["benefits"]
    total = refund + benefit_gain

    return {
        "contribution": contribution,
        "tax_refund": refund,
        "benefit_restored": benefit_gain,
        "total_value": total,
        "blended_rate": total / contribution if contribution else 0.0,
        "refund_share": refund / total if total else 0.0,
    }


def marginal_curve(low: float, high: float, household: Household,
                   cfg: dict, step: float = 500.0) -> list:
    """Sample the effective marginal rate across an income range."""
    curve = []
    x = low
    while x <= high:
        curve.append(effective_marginal_rate(x, household, cfg))
        x += step
    return curve
