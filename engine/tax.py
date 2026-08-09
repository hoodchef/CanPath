"""
Canadian personal income tax engine.

Pure functions, no I/O, no framework dependencies. This module is the
reference implementation that the Swift port must reproduce exactly.

Convention: all money is float dollars. Rounding happens at the
presentation layer only, never mid-calculation.
"""

import json
from pathlib import Path
from functools import lru_cache

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=None)
def load_year(year: int = 2026) -> dict:
    """Load the versioned config for a tax year."""
    path = DATA_DIR / f"taxyear_{year}.json"
    if not path.exists():
        raise ValueError(f"No tax data bundled for year {year}")
    with open(path) as f:
        return json.load(f)


def bracket_tax(taxable_income: float, brackets: list) -> float:
    """
    Apply a marginal bracket ladder.

    Brackets are [{floor, rate}, ...] sorted ascending. Each rate applies
    only to income above that bracket's floor and below the next floor.
    """
    if taxable_income <= 0:
        return 0.0

    tax = 0.0
    for i, b in enumerate(brackets):
        floor = b["floor"]
        if taxable_income <= floor:
            break
        ceiling = brackets[i + 1]["floor"] if i + 1 < len(brackets) else float("inf")
        slice_amount = min(taxable_income, ceiling) - floor
        tax += slice_amount * b["rate"]
    return tax


def federal_bpa(net_income: float, cfg: dict) -> float:
    """
    Federal Basic Personal Amount.

    The BPA has a base component plus an additional component that phases
    out linearly across the top two brackets. Getting this wrong creates a
    ~0.29pp error in the top brackets -- small, but it compounds into the
    marginal rate curve and makes the 4th bracket read 29% instead of 29.29%.
    """
    bpa = cfg["federal"]["bpa"]
    start, end = bpa["phaseout_start"], bpa["phaseout_end"]

    if net_income <= start:
        additional = bpa["additional"]
    elif net_income >= end:
        additional = 0.0
    else:
        fraction_remaining = (end - net_income) / (end - start)
        additional = bpa["additional"] * fraction_remaining

    return bpa["base"] + additional


def federal_tax(taxable_income: float, cfg: dict) -> float:
    """Federal income tax after the basic personal amount credit."""
    if taxable_income <= 0:
        return 0.0

    gross = bracket_tax(taxable_income, cfg["federal"]["brackets"])
    bpa = federal_bpa(taxable_income, cfg)
    credit = bpa * cfg["federal"]["credit_rate"]
    return max(0.0, gross - credit)


def provincial_tax(taxable_income: float, province: str, cfg: dict) -> float:
    """
    Provincial income tax after BPA and any low-income reduction credit.

    BC's tax reduction credit is the subtle one: it phases out at 3.56% of
    net income above the threshold, which adds 3.56 percentage points to the
    effective marginal rate for anyone in that band. This is invisible in
    the posted bracket table and is exactly the kind of thing the product
    exists to surface.
    """
    if taxable_income <= 0:
        return 0.0

    p = cfg["provinces"].get(province)
    if p is None:
        raise ValueError(f"Province {province} not yet supported")

    gross = bracket_tax(taxable_income, p["brackets"])
    credit = p["bpa"] * p["credit_rate"]
    tax = max(0.0, gross - credit)

    tr = p.get("tax_reduction")
    if tr:
        reduction = tr["max_credit"]
        if taxable_income > tr["threshold"]:
            reduction -= (taxable_income - tr["threshold"]) * tr["phaseout_rate"]
        reduction = max(0.0, reduction)
        tax = max(0.0, tax - reduction)

    return tax


def combined_tax(taxable_income: float, province: str, cfg: dict) -> float:
    """Total federal + provincial income tax."""
    return federal_tax(taxable_income, cfg) + provincial_tax(taxable_income, province, cfg)


def payroll_deductions(employment_income: float, cfg: dict) -> dict:
    """
    CPP, CPP2 and EI.

    Deliberately excluded from the RRSP marginal-rate calculation: these are
    levied on gross employment income and are unaffected by an RRSP
    deduction. Including them would overstate the value of a contribution.
    """
    pr = cfg["payroll"]

    cpp_base = max(0.0, min(employment_income, pr["cpp"]["ympe"]) - pr["cpp"]["basic_exemption"])
    cpp = cpp_base * pr["cpp"]["rate"]

    cpp2_base = max(0.0, min(employment_income, pr["cpp2"]["yampe"]) - pr["cpp"]["ympe"])
    cpp2 = cpp2_base * pr["cpp2"]["rate"]

    ei = min(employment_income, pr["ei"]["max_insurable"]) * pr["ei"]["rate"]

    return {"cpp": cpp, "cpp2": cpp2, "ei": ei, "total": cpp + cpp2 + ei}
