"""Works out how a policy applies to one specific employee. No LLM, ever.

This is the line between "safe" and "not safe" in the tailored policy answer.

A policy answer has three layers. The prose layer may be generated, because it only rewords
rules that were handed to it. The tailored layer -- "you're on probation, so you're expected
on-site four days a week" -- is an ELIGIBILITY DETERMINATION, and if a language model guesses
it, it will eventually tell someone in probation they can work remotely three days a week.
In an HR tool that is the failure that actually costs something.

So the determination is made here, in Python, from the employee record and the policy's own
rules. The explainer is then handed the conclusion and forbidden from adding to it. Same
approach ActionCareerPathAdvice already takes with _transfer_eligibility_note().

Adding a policy: write a resolver, register it in RESOLVERS. A policy with no resolver gets
SITUATION_STANDARD and no tailored line -- silence rather than a guess, which is the correct
default for the four policies (sick, compassionate, conduct, expenses) whose rules don't
depend on who is asking.
"""

import re

# Returned when a policy has no employee-conditional clause, or none that matches.
SITUATION_STANDARD = "standard"
# Returned when two clauses collide and the honest answer is "HR should confirm".
SITUATION_CONFLICT = "needs_hr"

# Roles that LEAVE-02 grants the extra 2 weeks to. Matched against the employee's role text.
SENIOR_ROLE_TOKENS = ("principal", "lead", "head of", "head-of", "director")

# Phrases in recent_event that mean "recently had or adopted a child". Deliberately narrow:
# a false positive here tells someone they qualify for three months fully-remote when they
# don't.
PARENTAL_EVENT_TOKENS = ("gave birth", "birth of", "adopted", "adoption", "parental leave", "maternity", "paternity")


def _has_parental_event(employee):
    event = (employee.get("recentEvent") or "").lower()
    return any(token in event for token in PARENTAL_EVENT_TOKENS)


def _is_senior(employee):
    role = (employee.get("role") or "").lower()
    return any(token in role for token in SENIOR_ROLE_TOKENS)


def _band_number(employee):
    """Pull the integer out of "Band 6". Returns None when it can't be read.

    None matters: RESIGN-01 sets notice period from the band, so an unparseable band must
    produce no tailored line rather than a defaulted one.
    """
    match = re.search(r"(\d+)", employee.get("salaryBand") or "")
    return int(match.group(1)) if match else None


def _wfh(employee):
    probation = bool(employee.get("probation"))
    parental = _has_parental_event(employee)

    # Both clauses apply and they point opposite ways -- one says on-site four days, the
    # other says fully remote for three months. The policy doesn't say which wins, so
    # neither do we.
    if probation and parental:
        return SITUATION_CONFLICT, (
            "Your record shows both a recent parental event and an active probation period. "
            "Those two rules pull in different directions, so HR should confirm which applies to you."
        )

    if probation:
        return "probation", (
            "You're currently in probation, so the hybrid norm doesn't apply to you yet -- "
            "you're expected on-site at least 4 days per week."
        )

    if parental:
        return "parental_return", (
            "Because you're returning from parental leave, you can request a temporary "
            "fully-remote arrangement for up to 3 months, rather than the usual 3 days."
        )

    # Deliberately short and confirmatory. The general paragraph above has already stated the
    # 3-day rule; repeating it here is the duplication this split was meant to remove. What
    # this line adds is that nothing on THIS employee's record changes it.
    return "standard", "Nothing on your record changes that, so the standard arrangement applies to you."


def _annual_leave(employee):
    tenure = employee.get("tenureYears") or 0
    entitlement = employee.get("annualLeaveEntitlement") or 0
    taken = employee.get("annualLeaveTaken") or 0
    remaining = entitlement - taken

    if tenure < 2:
        band, carry = "under_2", "Carry-over needs more than 2 years of service, so it doesn't apply to you yet."
    elif tenure <= 5:
        band, carry = "2_to_5", "You can carry up to 5 unused days into next year; they expire on 31 March."
    else:
        band, carry = "over_5", "You can carry up to 5 unused days into next year; they expire on 31 March."

    # The balance is live data, which is why this line is never cached -- see the note at the
    # top of policy_explainer.py.
    years = "1 year" if tenure == 1 else f"{tenure} years"
    days_left = "1 day" if remaining == 1 else f"{remaining} days"
    return band, (
        f"On {years} of service your entitlement is {entitlement} days, and you have "
        f"{days_left} left this year. {carry}"
    )


def _parental_leave(employee):
    if _is_senior(employee):
        return "senior", (
            f"At {employee.get('role')} level you also get an additional 2 weeks of flexible "
            "return-to-work leave, which can be taken at reduced hours."
        )
    return "standard", None


def _resignation(employee):
    if employee.get("probation"):
        return "probation", "As you're still in probation, your notice period is 1 week."

    band = _band_number(employee)
    if band is None:
        return SITUATION_STANDARD, None
    if band <= 3:
        return "band_1_3", f"On {employee.get('salaryBand')} as a confirmed employee, your notice period is 4 weeks."
    return "band_4_plus", f"On {employee.get('salaryBand')} as a confirmed employee, your notice period is 8 weeks."


def _transfer(employee):
    # Mirrors _transfer_eligibility_note() in rasa/actions/actions.py. Only tenure is
    # inferable -- the disciplinary and prior-transfer clauses aren't in the data model, so
    # nothing is claimed about them.
    if (employee.get("tenureYears") or 0) < 1:
        return "under_12_months", (
            "You haven't completed 12 months in your current role yet, so you're not eligible "
            "to apply for an internal transfer at the moment."
        )
    return "eligible_on_tenure", (
        "You meet the 12-month service requirement. Time in your current role and the "
        "endorsement steps are for HR to confirm."
    )


def _bonus(employee):
    if employee.get("probation"):
        return "probation", (
            "Bonuses require you to be confirmed, so as you're still in probation you wouldn't "
            "be eligible for the next payment."
        )
    return "confirmed", "You're confirmed, so you'd be eligible provided you're still employed on the March payment date."


RESOLVERS = {
    "WFH-01": _wfh,
    "LEAVE-01": _annual_leave,
    "LEAVE-02": _parental_leave,
    "RESIGN-01": _resignation,
    "TRANSFER-01": _transfer,
    "BONUS-01": _bonus,
}


def resolve_situation(employee, policy_id):
    """(situation_key, tailored_note) for this employee against this policy.

    tailored_note is None when nothing employee-specific can be said. Callers must render
    nothing in that case -- not a hedge, not a generic sentence.

    situation_key is what the explanation cache is keyed on, so it must depend only on the
    employee attributes the policy actually cares about. Keying on employee id instead would
    give every employee their own cache entry and defeat the point.
    """
    if not employee:
        return SITUATION_STANDARD, None

    resolver = RESOLVERS.get(policy_id)
    if not resolver:
        return SITUATION_STANDARD, None

    return resolver(employee)
