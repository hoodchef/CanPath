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
    fhsa_lifetime_remaining: float = None    # FHSA is lifetime-capped, not just annual
    resp_children: int = None                # defaults to the household's under-18 count
    cesg_remaining: float = None             # unclaimed CESG across those children
    employer_match_rate: float = 0.0         # e.g. 0.50 = 50 cents per dollar
    employer_match_cap: float = 0.0          # max employee $ that gets matched

    def resolve_room(self, cfg: dict):
        a = cfg["accounts"]
        if self.rrsp_room is None:
            self.rrsp_room = min(self.income * a["rrsp"]["earned_income_rate"],
                                 a["rrsp"]["dollar_limit"])
        if self.tfsa_room is None:
            self.tfsa_room = a["tfsa"]["annual_limit"]
        if self.fhsa_lifetime_remaining is None:
            self.fhsa_lifetime_remaining = a["fhsa"]["lifetime_limit"]
        if self.resp_children is None:
            self.resp_children = self.household.n_children
        if self.cesg_remaining is None:
            self.cesg_remaining = (a["resp"]["cesg_lifetime_max"]
                                   * self.resp_children)
        if self.fhsa_room is None:
            # The $40,000 lifetime cap binds before the $8,000 annual one in
            # the final year of an FHSA. Granting the annual limit forever is
            # how a tool ends up projecting a deduction that cannot legally
            # exist -- the FHSA runs out after five full years.
            self.fhsa_room = (min(a["fhsa"]["annual_limit"],
                                  max(0.0, self.fhsa_lifetime_remaining))
                              if self.fhsa_eligible else 0.0)


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
    acct = cfg["accounts"]

    allocated = {"employer_match": 0.0, "fhsa": 0.0, "resp": 0.0, "rrsp": 0.0,
                 "tfsa": 0.0, "non_registered": 0.0}
    # RESP room here means "contribution that still attracts the grant". Past
    # the matched amount an RESP is just another sheltered account with no
    # deduction, which the solver has no reason to rank above a TFSA, so the
    # room stops where the 20% stops.
    resp_annual = acct["resp"]["cesg_matched_contribution"] * profile.resp_children
    resp_by_grant = (profile.cesg_remaining / acct["resp"]["cesg_match_rate"]
                     if acct["resp"]["cesg_match_rate"] else 0.0)
    room = {"fhsa": profile.fhsa_room, "tfsa": profile.tfsa_room,
            "resp": max(0.0, min(resp_annual, resp_by_grant))}

    # A group-RRSP match is still an RRSP. The employee's contribution AND
    # the employer's match both consume the SAME contribution room, so they
    # draw on one pool rather than two. Tracking them separately let the
    # solver recommend $52,000 of deductible contributions against $27,000
    # of room -- a penalty-taxed over-contribution presented as advice.
    rrsp_pool = profile.rrsp_room
    match_cap_left = profile.employer_match_cap
    match_multiple = 1.0 + profile.employer_match_rate

    steps = []
    # The order accounts were FIRST funded in. The allocation dict is
    # unordered by nature, and the UI renders a ranked list -- without this
    # it has to invent a ranking, which is how a panel headed "funding
    # order" ends up showing RRSP above the TFSA that was funded first.
    sequence = []
    remaining = profile.savings_capacity
    deducted = 0.0

    while remaining > 0.01:
        amount = min(chunk, remaining)
        emr = effective_marginal_rate(
            profile.income - deducted, profile.household, cfg
        )["effective_rate"]

        # Every dollar matched costs (1 + match_rate) dollars of room.
        match_room = min(match_cap_left, rrsp_pool / match_multiple)

        scores = {}
        if match_room > 0:
            scores["employer_match"] = profile.employer_match_rate + emr
        if room["fhsa"] > 0:
            scores["fhsa"] = emr
        if room["resp"] > 0:
            # The grant rate alone. An RESP contribution is NOT deductible, so
            # unlike the employer match its score carries no emr term.
            scores["resp"] = acct["resp"]["cesg_match_rate"]
        if rrsp_pool > 0:
            scores["rrsp"] = emr - profile.expected_retirement_rate
        if room["tfsa"] > 0:
            scores["tfsa"] = 0.0

        if not scores or max(scores.values()) < 0:
            # Registered room beats a taxable account even when the score is
            # negative. This function measures YEAR ONE, and a taxable
            # account's cost is not in year one -- it is the tax on every
            # year of growth after it. Contributing at 19.6% to withdraw at
            # 25% scores -5.4 here, but over 30 years at 7% it still returns
            # 7.10 per after-tax dollar against 6.79 for a taxable account,
            # because the shelter outlives the rate difference. Falling
            # through to non-registered while RRSP room sat open traded a
            # three-decade shelter for a one-year rate gap.
            if room["tfsa"] > 0:
                best = "tfsa"
            elif rrsp_pool > 0:
                best = "rrsp"
            else:
                allocated["non_registered"] += amount
                remaining -= amount
                continue
        else:
            best = max(scores, key=scores.get)

        if best == "employer_match":
            amount = min(amount, match_room)
        elif best == "rrsp":
            amount = min(amount, rrsp_pool)
        else:
            amount = min(amount, room[best])

        # A room that is positive only by floating-point dust would otherwise
        # spin here forever, re-selecting an account it cannot fund.
        if amount <= 1e-9:
            allocated["non_registered"] += remaining
            remaining = 0.0
            continue

        if best == "employer_match":
            match_cap_left -= amount
            rrsp_pool -= amount * match_multiple
        elif best == "rrsp":
            rrsp_pool -= amount
        else:
            room[best] -= amount

        allocated[best] += amount
        remaining -= amount
        if best not in sequence:
            sequence.append(best)

        # RESP is deliberately absent: contributions are not deductible, and
        # adding it here would inflate the refund and the restored benefit
        # shown to every household with children.
        if best in ("rrsp", "fhsa", "employer_match"):
            deducted += amount

        steps.append({"account": best, "amount": amount,
                      "emr_at_step": emr, "score": scores.get(best, 0.0)})

    before = net_position(profile.income, profile.household, cfg, 0.0)
    after = net_position(profile.income, profile.household, cfg, deducted)

    return {
        "allocation": {k: v for k, v in allocated.items() if v > 0},
        "sequence": sequence,
        "total_deducted": deducted,
        "rrsp_room_used": profile.rrsp_room - rrsp_pool,
        "rrsp_room_left": rrsp_pool,
        "tax_refund": before["tax"] - after["tax"],
        "benefit_restored": after["benefits"] - before["benefits"],
        "employer_match_earned": allocated["employer_match"] * profile.employer_match_rate,
        "resp_grant_earned": allocated["resp"] * acct["resp"]["cesg_match_rate"],
        "warnings": _guardrails(profile, cfg, allocated, rrsp_pool),
        "steps": steps,
    }


def _guardrails(profile: Profile, cfg: dict, allocated: dict = None,
                rrsp_left: float = None) -> list:
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

    # An employer match you cannot legally absorb is not free money -- it is
    # an over-contribution penalty waiting to happen, and the employee is the
    # one the CRA charges.
    # Only when room is what ran out. Someone simply saving less than their
    # employer would match has a different problem, and telling them their
    # room is short would be false.
    if (allocated is not None and profile.employer_match_cap > 0
            and rrsp_left is not None and rrsp_left <= 0.01):
        taken = allocated.get("employer_match", 0.0)
        if taken < profile.employer_match_cap - 0.01:
            w.append(
                f"Your RRSP room only covers ${taken:,.0f} of the "
                f"${profile.employer_match_cap:,.0f} your employer will match. "
                "The match uses the same room your own contributions do. "
                "Check your room in CRA My Account before topping up."
            )
    return w
