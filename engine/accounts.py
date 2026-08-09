"""
Registered account allocation solver.

Rather than applying a static rule-of-thumb ladder, this allocates savings
in small increments and re-scores every account at each step. That matters:
as contributions pull income down out of a clawback zone, the marginal value
of the next dollar falls, and the solver naturally stops at the threshold
instead of blindly maxing one account.
"""

from dataclasses import dataclass
from .marginal import effective_marginal_rate, net_position
from .benefits import Household


@dataclass
class Profile:
    income: float
    household: Household
    savings_capacity: float
    expected_retirement_rate: float = 0.25   # blended draw-down rate
    fhsa_eligible: bool = False
    rrsp_room: float = None
    tfsa_room: float = None
    fhsa_room: float = None
    employer_match_rate: float = 0.0         # e.g. 0.50 = 50 cents per dollar
    employer_match_cap: float = 0.0          # max employee $ that gets matched

    def resolve_room(self, cfg: dict):
        a = cfg["accounts"]
        if self.rrsp_room is None:
            self.rrsp_room = min(self.income * a["rrsp"]["earned_income_rate"],
                                 a["rrsp"]["dollar_limit"])
        if self.tfsa_room is None:
            self.tfsa_room = a["tfsa"]["annual_limit"]
        if self.fhsa_room is None:
            self.fhsa_room = a["fhsa"]["annual_limit"] if self.fhsa_eligible else 0.0


def optimize(profile: Profile, cfg: dict, chunk: float = 250.0) -> dict:
    """
    Greedily allocate savings to the highest-marginal-value account.

    Scoring, per dollar contributed:
      employer match -- the match rate itself, uncontested best return
      FHSA           -- full effective marginal rate, since withdrawal for a
                        qualifying home purchase is tax-free (deduct in AND
                        tax-free out; strictly dominates RRSP when eligible)
      RRSP           -- current effective marginal rate minus the expected
                        rate at withdrawal; this is the arbitrage, and it
                        goes NEGATIVE when someone is contributing at a
                        lower rate than they'll withdraw at
      TFSA           -- zero immediate value, but never negative; the
                        baseline every other account must beat
    """
    profile.resolve_room(cfg)

    allocated = {"employer_match": 0.0, "fhsa": 0.0, "rrsp": 0.0,
                 "tfsa": 0.0, "non_registered": 0.0}
    room = {
        "employer_match": profile.employer_match_cap,
        "fhsa": profile.fhsa_room,
        "rrsp": profile.rrsp_room,
        "tfsa": profile.tfsa_room,
    }
    steps = []
    remaining = profile.savings_capacity
    deducted = 0.0

    while remaining > 0.01:
        amount = min(chunk, remaining)
        emr = effective_marginal_rate(
            profile.income - deducted, profile.household, cfg
        )["effective_rate"]

        scores = {}
        if room["employer_match"] > 0:
            scores["employer_match"] = profile.employer_match_rate + emr
        if room["fhsa"] > 0:
            scores["fhsa"] = emr
        if room["rrsp"] > 0:
            scores["rrsp"] = emr - profile.expected_retirement_rate
        if room["tfsa"] > 0:
            scores["tfsa"] = 0.0

        if not scores or max(scores.values()) < 0:
            # Nothing beats a taxable account (or all deductible options
            # would be actively value-destroying)
            if room["tfsa"] > 0:
                best = "tfsa"
            else:
                allocated["non_registered"] += amount
                remaining -= amount
                continue
        else:
            best = max(scores, key=scores.get)

        amount = min(amount, room[best])
        allocated[best] += amount
        room[best] -= amount
        remaining -= amount

        if best in ("rrsp", "fhsa", "employer_match"):
            deducted += amount

        steps.append({"account": best, "amount": amount,
                      "emr_at_step": emr, "score": scores.get(best, 0.0)})

    before = net_position(profile.income, profile.household, cfg, 0.0)
    after = net_position(profile.income, profile.household, cfg, deducted)

    return {
        "allocation": {k: v for k, v in allocated.items() if v > 0},
        "total_deducted": deducted,
        "tax_refund": before["tax"] - after["tax"],
        "benefit_restored": after["benefits"] - before["benefits"],
        "employer_match_earned": allocated["employer_match"] * profile.employer_match_rate,
        "warnings": _guardrails(profile, cfg),
        "steps": steps,
    }


def _guardrails(profile: Profile, cfg: dict) -> list:
    """
    Detect cases where the obvious advice is actively harmful.

    Getting this wrong is not a cosmetic bug. Telling a low-income Canadian
    to load an RRSP sets up a ~50% GIS clawback in retirement -- the tool
    must refuse to make that recommendation, loudly.
    """
    w = []
    emr = effective_marginal_rate(profile.income, profile.household, cfg)["effective_rate"]

    if emr < profile.expected_retirement_rate:
        w.append(
            "RRSP contributions look value-destroying here: your current "
            f"effective rate ({emr:.1%}) is below your expected withdrawal "
            f"rate ({profile.expected_retirement_rate:.1%}). TFSA first."
        )
    if profile.income < 45000:
        w.append(
            "At this income level, RRSP/RRIF withdrawals in retirement may "
            "trigger GIS clawback of roughly 50 cents on the dollar. TFSA "
            "withdrawals do not affect GIS."
        )
    if profile.fhsa_eligible and profile.fhsa_room > 0:
        w.append(
            "FHSA room is unused. It is the only account that is both "
            "deductible going in and tax-free coming out."
        )
    return w
