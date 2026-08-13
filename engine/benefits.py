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
    # Explicit, because it is no longer cosmetic. It selects the CGEB couple
    # amount and the BCFB single-parent supplement, so inferring it from
    # partner_income alone would treat a couple with one non-earning partner
    # as a single parent and hand them a supplement they cannot claim.
    partnered_flag: bool = None

    @property
    def partnered(self) -> bool:
        if self.partnered_flag is not None:
            return self.partnered_flag
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


def bc_family_benefit(afni: float, child_ages: List[int], cfg: dict,
                      single_parent: bool = False) -> float:
    """
    BC Family Benefit.

    Two 4% clawback bands with a FLAT PLATEAU between them, which is the
    part that matters for the marginal rate. The benefit reduces at 4% of
    AFNI above threshold_1 but never below a per-child floor; the floor
    then holds -- costing nothing at the margin -- until threshold_2, above
    which it reduces at 4% again. So a BC family crosses 4%, then 0%, then
    4% as income rises. Modelling it as a single continuous phase-out would
    put the clawback in the wrong income bands entirely.
    """
    b = cfg["benefits"].get("bc_family_benefit")
    if not b:
        return 0.0
    n = len([a for a in child_ages if a < 18])
    if n == 0:
        return 0.0

    maximum = b["max_first_child"]
    if n >= 2:
        maximum += b["max_second_child"]
    if n > 2:
        maximum += b["max_additional_child"] * (n - 2)

    floor = b["floor_first_child"]
    if n >= 2:
        floor += b["floor_second_child"]
    if n > 2:
        floor += b["floor_additional_child"] * (n - 2)

    if single_parent:
        maximum += b["single_parent_supplement"]

    rate, t1, t2 = b["phaseout_rate"], b["threshold_1"], b["threshold_2"]

    # Band 1: reduce toward the floor, never past it.
    reduced = maximum - rate * max(0.0, min(afni, t2) - t1)
    benefit = max(floor, reduced)
    # Band 2: the residual itself now phases out.
    if afni > t2:
        benefit -= rate * (afni - t2)
    return max(0.0, benefit)


def canada_groceries_essentials_benefit(afni: float, household: Household,
                                        cfg: dict) -> float:
    """
    Canada Groceries and Essentials Benefit -- the renamed GST/HST credit.

    Note the age limit is under 19, NOT the under-18 the CCB uses. Reusing
    the CCB's child count here would silently underpay every household with
    an 18-year-old.
    """
    c = cfg["benefits"].get("cgeb")
    if not c:
        return 0.0
    kids = len([a for a in household.child_ages if a < c["child_age_limit"]])
    maximum = (c["max_couple"] if household.partnered else c["max_single"])
    maximum += c["max_per_child"] * kids
    reduction = c["phaseout_rate"] * max(0.0, afni - c["threshold"])
    return max(0.0, maximum - reduction)


def _stacked_max(amounts: List[float], n: int) -> float:
    """Per-child amounts that differ by birth order, last value repeating."""
    return sum(amounts[min(i, len(amounts) - 1)] for i in range(n))


def provincial_child_benefit(afni: float, child_ages: List[int],
                             province: str, cfg: dict,
                             employment_income: float = None) -> float:
    """
    Provincial child benefits other than BC's, which has its own shape.

    Three forms, because three are what the supplied data describes:

      linear -- one maximum, one threshold, one rate.
      tiered -- a literal step per income band. Not a phase-out: a CLIFF,
                producing a marginal rate of several hundred percent on the
                dollar that crosses it. That is what PEI's data says, so it
                is what is modelled.
      ab     -- Alberta's two independent components, a base and a working
                amount, each with its own threshold and rate. The working
                component is treated as available in full above its
                employment-income floor rather than phasing in, because no
                phase-in rate was supplied.

    A province mapped to null has no benefit at all -- Saskatchewan -- which
    is a different fact from "not yet modelled" and is recorded as such.
    """
    table = cfg["benefits"].get("provincial_child_benefits") or {}
    b = table.get(province)
    if not b:
        return 0.0
    n = len([a for a in child_ages if a < 18])
    if n == 0:
        return 0.0

    kind = b["type"]
    if kind == "linear":
        maximum = _stacked_max(b["amounts"], n)
        return max(0.0, maximum - b["rate"] * max(0.0, afni - b["threshold"]))

    if kind == "tiered":
        for tier in b["tiers"]:
            if afni <= tier["upto"]:
                return tier["per_child"] * n
        return 0.0

    if kind == "ab":
        base = max(0.0, _stacked_max(b["base_amounts"], n)
                   - b["base_rate"] * max(0.0, afni - b["base_threshold"]))
        earned = afni if employment_income is None else employment_income
        working = 0.0
        if earned > b["working_min_employment"]:
            working = max(0.0, _stacked_max(b["working_amounts"], n)
                          - b["working_rate"] * max(0.0, afni - b["working_threshold"]))
        return base + working

    return 0.0


def total_benefits(afni: float, household: Household, cfg: dict) -> dict:
    """All income-tested benefits for a household. Extend as coverage grows."""
    ccb = canada_child_benefit(afni, household.child_ages, cfg)
    bcfb = (bc_family_benefit(afni, household.child_ages, cfg,
                              single_parent=not household.partnered)
            if household.province == "BC" else 0.0)
    pcb = provincial_child_benefit(afni, household.child_ages,
                                   household.province, cfg)
    cgeb = canada_groceries_essentials_benefit(afni, household, cfg)
    return {"ccb": ccb, "bcfb": bcfb, "pcb": pcb, "cgeb": cgeb,
            "total": ccb + bcfb + pcb + cgeb}
