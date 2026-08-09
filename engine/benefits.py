"""
Income-tested federal benefits.

This module is the product's reason to exist. The CCB clawback is a hidden
marginal tax that routinely exceeds the posted bracket rate, and no
consumer tool in Canada surfaces it properly.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Household:
    """A household's benefit-relevant characteristics."""
    province: str = "BC"
    child_ages: List[int] = field(default_factory=list)
    partner_income: float = 0.0

    @property
    def partnered(self) -> bool:
        return self.partner_income > 0

    @property
    def n_children(self) -> int:
        return len([a for a in self.child_ages if a < 18])


def ccb_max(child_ages: List[int], cfg: dict) -> float:
    """Maximum CCB before any income testing."""
    c = cfg["benefits"]["ccb"]
    total = 0.0
    for age in child_ages:
        if age < 6:
            total += c["max_under_6"]
        elif age < 18:
            total += c["max_6_to_17"]
    return total


def _rate_for(n_children: int, table: dict) -> float:
    """Phase-out rates are capped at the 4+ children tier."""
    key = str(min(max(n_children, 1), 4))
    return table[key]


def canada_child_benefit(afni: float, child_ages: List[int], cfg: dict) -> float:
    """
    Canada Child Benefit for a given adjusted family net income.

    Two-zone phase-out:
      Zone 1 -- reduction = rate1 x (AFNI - threshold_1)
      Zone 2 -- reduction = rate1 x (threshold_2 - threshold_1)
                            + rate2 x (AFNI - threshold_2)

    Note the zone-2 rate is LOWER than zone-1. The reductions do not stack;
    zone 2 carries forward the accumulated zone-1 reduction as a fixed
    dollar amount. Implementing this as a naive sum of both rates is the
    single most common error in third-party CCB calculators.
    """
    c = cfg["benefits"]["ccb"]
    n = len([a for a in child_ages if a < 18])
    if n == 0:
        return 0.0

    maximum = ccb_max(child_ages, cfg)
    t1, t2 = c["threshold_1"], c["threshold_2"]

    if afni <= t1:
        reduction = 0.0
    elif afni <= t2:
        reduction = _rate_for(n, c["phase1_rates"]) * (afni - t1)
    else:
        accumulated = _rate_for(n, c["phase1_rates"]) * (t2 - t1)
        reduction = accumulated + _rate_for(n, c["phase2_rates"]) * (afni - t2)

    return max(0.0, maximum - reduction)


def total_benefits(afni: float, household: Household, cfg: dict) -> dict:
    """All income-tested benefits for a household. Extend as coverage grows."""
    ccb = canada_child_benefit(afni, household.child_ages, cfg)
    return {"ccb": ccb, "total": ccb}
