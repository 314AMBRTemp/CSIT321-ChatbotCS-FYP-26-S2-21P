import os
import re
from datetime import date, timedelta
from services.policies import search_policies
from services.policy_answer import build_policy_answer

IMMEDIATE_FAMILY = {
    "spouse", "husband", "wife", "partner", "parent", "father", "mother", "mum", "mom", "dad",
    "child", "son", "daughter", "sibling", "brother", "sister", "grandparent", "grandfather", "grandmother",
    "grandpa", "grandma"
}
EXTENDED_FAMILY = {"cousin", "aunt", "uncle", "niece", "nephew", "relative"}

IMMEDIATE_FAMILY_DAYS = 5
EXTENDED_FAMILY_DAYS = 3

# Mirrors the constant in rasa/actions/actions.py. Duplicating a constant across the two
# engines is safe; duplicating a *rule* is what caused the senior-parental-top-up drift,
# which is why that one moved into employee_facts() instead.
HR_CONTACT_EMAIL = os.getenv("HR_CONTACT_EMAIL", "hr@lumenvale.com")


def _hr_handoff(context):
    """Referral the employee can act on -- see _hr_handoff in rasa/actions/actions.py."""
    return f" You can reach HR at {HR_CONTACT_EMAIL} -- mention {context} so they can pick it up from there."

# Roles that qualify for the extra 2 weeks of flexible return-to-work leave.
SENIOR_ROLE_TOKENS = ("principal", "lead", "head")

def employee_facts(employee):
    sick_taken = sum(req.number_of_days for req in employee.leave_requests if req.leave_type.lower() == "sick" and req.status not in ("Rejected", "Cancelled"))
    annual_remaining = employee.annual_leave_entitlement - employee.annual_leave_taken
    band_digits = re.sub(r"\D", "", employee.salary_band or "0")
    band = int(band_digits) if band_digits else 0
    return {
        "annualLeaveRemaining": annual_remaining,
        "sickLeaveRemaining": 14 - sick_taken,
        "eligibleForCarryOver": employee.tenure_years > 2,
        "eligibleForParental": employee.tenure_years >= 1,
        "notice": "1 week" if employee.probation else ("8 weeks" if band >= 4 else "4 weeks"),
        "bonusEligible": not employee.probation,
        # Principal / Lead / Head-of-Department level, in any department. Derived here
        # so the Rasa actions can read it off /api/employees/<id> instead of repeating
        # the role test in a second codebase.
        "eligibleForSeniorParentalTopUp": any(
            token in (employee.role or "").lower() for token in SENIOR_ROLE_TOKENS
        ),
    }

def _is_bereavement(q):
    return bool(re.search(r"\b(died|death|passed away|bereave|bereavement|funeral|wake|memorial|condolence|condolences)\b", q, re.I))

def _is_leave_request(q):
    return bool(re.search(r"\b(apply|request|take|book|submit|want|need|prepare).*(leave|day|days off|time off|annual|sick|compassionate|bereavement)\b", q, re.I))

def _is_recommendation(q):
    return bool(re.search(r"\b(best|recommend|should i|what should|which leave|what leave|suitable|option)\b", q, re.I))

def _detect_relationship(q):
    low = q.lower()

    # In-laws are extended family under the policy. Checked FIRST because matching is
    # substring-based: "mother-in-law" contains "mother" and would otherwise be read
    # as immediate family and over-quoted at 5 days.
    if "in-law" in low or "in law" in low:
        return {"relationship": "in-law", "group": "extended", "suggestedDays": EXTENDED_FAMILY_DAYS}

    for word in IMMEDIATE_FAMILY:
        if word in low:
            return {"relationship": word, "group": "immediate", "suggestedDays": IMMEDIATE_FAMILY_DAYS}
    for word in EXTENDED_FAMILY:
        if word in low:
            return {"relationship": word, "group": "extended", "suggestedDays": EXTENDED_FAMILY_DAYS}
    return {"relationship": "family member", "group": "review", "suggestedDays": EXTENDED_FAMILY_DAYS}

def _source(policies):
    titles = []
    for policy in policies:
        title = policy.get("title")
        if title and title not in titles:
            titles.append(title)
    return " · ".join(titles)

def _thinking_steps(question, policies):
    q = question.lower()
    if _is_bereavement(q):
        return [
            {"tag": "Understand", "text": "Recognised a family bereavement situation"},
            {"tag": "Retrieve", "text": "Matched the Compassionate Leave policy"},
            {"tag": "Profile", "text": "Checked relationship scope and available HR action"},
            {"tag": "Recommend", "text": "Prepared the suitable leave type and next step"},
        ]
    if _is_recommendation(q):
        return [
            {"tag": "Understand", "text": "Identified that the user needs an HR recommendation"},
            {"tag": "Retrieve", "text": _source(policies)},
            {"tag": "Compare", "text": "Compared policy rules with employee profile and balance"},
            {"tag": "Decide", "text": "Selected the safest HR route"},
        ]
    return [
        {"tag": "Understand", "text": "Detected the HR intent from the question"},
        {"tag": "Retrieve", "text": _source(policies)},
        {"tag": "Context", "text": "Checked profile and computed HRMS facts where needed"},
        {"tag": "Answer", "text": "Grounded the answer in the relevant policy source"},
    ]

def _leave_details(question):
    q = question.lower()
    relation = _detect_relationship(q)
    days_match = re.search(r"(\d+)\s*(day|days|working days|calendar days)", q, re.I)
    type_match = re.search(r"(sick|annual|parental|compassionate|bereavement)", q, re.I)
    leave_type = type_match.group(1).lower() if type_match else "annual"

    if leave_type == "bereavement" or _is_bereavement(q):
        leave_type = "compassionate"

    days = int(days_match.group(1)) if days_match else (relation["suggestedDays"] if leave_type == "compassionate" else 1)
    return leave_type.capitalize(), days, relation

def _policy_reply(employee, question, policies):
    """A three-layer policy answer in this engine's response shape, or None.

    Returns None when no policy matched, so each caller keeps whatever fallback it already
    had rather than this inventing one.
    """
    answer = build_policy_answer(employee.to_dict(), question)
    if not answer:
        return None

    return {
        "text": answer["text"],
        "source": answer["source"],
        "isRecommendation": False,
        "canSubmitLeave": False,
        # Drives the "Yes, raise it" button in the widget.
        "canRaiseHrRequest": answer["canRaiseHrRequest"],
        "policyId": answer["policyId"],
        "policyTopic": answer["title"],
        "situation": answer["situation"],
        # The offer is itself a question, so the widget must not tack another one on.
        "endsWithQuestion": answer["endsWithQuestion"],
        "thinkingSteps": _thinking_steps(question, policies),
    }


def answer_question(employee, question):
    policies = search_policies(question)
    facts = employee_facts(employee)
    q = question.lower()

    if re.search(r"q1|dynamic.*ai|ai.*portion|where.*ai|hr policy.*ai", q):
        return {
            "text": "The dynamic AI portion sits between the HRMS data, HR policy repository, and chatbot reply. AskIvy receives a natural question, retrieves the relevant policy, checks the employee profile and leave records, then produces a grounded answer or prepares an HRMS action such as a leave request.",
            "source": "Project AI Design Notes",
            "isRecommendation": False,
            "canSubmitLeave": False,
            "thinkingSteps": _thinking_steps(question, policies),
        }

    if re.search(r"q2|actually think|how.*think|not just fetch|not just tabulate|thinking", q):
        return {
            "text": "The AI part is the decision layer, not only a search box. It interprets the user's situation, compares policy rules with the employee's profile, selects the most suitable HR route, and explains why that route fits the case.",
            "source": "Project AI Design Notes",
            "isRecommendation": False,
            "canSubmitLeave": False,
            "thinkingSteps": _thinking_steps(question, policies),
        }

    if re.search(r"q3|best stock|translate.*hr|best.*buy.*today|stock.*hr", q):
        return {
            "text": "The HR equivalent of 'what is the best stock to buy today?' is 'what is the best HR option for my situation?' AskIvy recommends the best route based on context, such as sick leave for illness, compassionate leave for bereavement, parental leave for childbirth or adoption, annual leave for planned personal time, and WFH for work arrangement needs.",
            "source": "Project AI Design Notes",
            "isRecommendation": True,
            "canSubmitLeave": False,
            "thinkingSteps": _thinking_steps(question, policies),
        }

    if _is_bereavement(question):
        relation = _detect_relationship(question)
        if relation["group"] == "immediate":
            detail = f"For a {relation['relationship']}, the policy treats this as immediate family bereavement and allows up to 5 paid working days, subject to approval and possible supporting documents."
        elif relation["group"] == "extended":
            detail = f"For a {relation['relationship']}, the policy treats this as extended family bereavement and allows up to 3 paid working days, subject to manager approval."
        else:
            detail = "The policy covers bereavement, but HR or the manager should confirm the relationship category and required supporting documents."
        # Only the unrecognised case needs a handoff -- the other two already have an answer.
        # Deliberately does NOT quote relation["relationship"]: this branch is reached when the
        # regex matched nothing, so that value is the literal fallback "family member", not
        # anything the employee actually said.
        handoff = _hr_handoff("you're asking about compassionate leave and they'll need to confirm the relationship category") if relation["group"] == "review" else ""
        return {
            "text": f"I'm sorry to hear that. The most relevant HR policy is Compassionate Leave, not annual leave or sick leave. {detail} If more time is needed, the better HR route is to combine compassionate leave with annual leave or request a special arrangement through HR.{handoff}",
            "source": "Compassionate Leave",
            "isRecommendation": True,
            "canSubmitLeave": True,
            "suggestedLeave": {"type": "Compassionate", "days": relation["suggestedDays"]},
            "thinkingSteps": _thinking_steps(question, policies),
        }

    if _is_leave_request(question):
        leave_type, days, relation = _leave_details(question)
        source = f"{leave_type} Leave"
        if leave_type == "Compassionate":
            source = "Compassionate Leave"
            if relation["group"] == "immediate":
                note = f"The policy allows up to 5 paid working days for immediate family bereavement involving a {relation['relationship']}."
            elif relation["group"] == "extended":
                note = f"The policy allows up to 3 paid working days for extended family bereavement involving a {relation['relationship']}, subject to manager approval."
            else:
                note = "HR or the manager should confirm the relationship category and any supporting documents."
        elif leave_type == "Sick":
            source = "Sick Leave"
            note = f"Your sick leave balance is {facts['sickLeaveRemaining']} day(s). A medical certificate is required if the absence exceeds 2 consecutive days."
        elif leave_type == "Parental":
            source = "Parental Leave"
            note = "Your profile meets the 12-month service requirement." if facts["eligibleForParental"] else "Your profile does not currently meet the 12-month service requirement, so HR should review this before submission."
        else:
            source = "Annual Leave"
            note = f"Your annual leave balance is {facts['annualLeaveRemaining']} day(s)."

        return {
            "text": f"I can prepare a {leave_type.lower()} leave request for {days} day(s). {note} Click submit to create a pending request in the HRMS demo.",
            "source": source,
            "isRecommendation": False,
            "canSubmitLeave": True,
            "suggestedLeave": {"type": leave_type, "days": days},
            "thinkingSteps": _thinking_steps(question, policies),
        }

    if "how many" in q or "balance" in q or "remaining" in q or "leave days" in q:
        return {
            "text": f"You have {facts['annualLeaveRemaining']} annual leave day(s) remaining out of your {employee.annual_leave_entitlement}-day entitlement. This is based on your HRMS record and the Annual Leave policy.",
            "source": "Annual Leave",
            "isRecommendation": False,
            "canSubmitLeave": False,
            "thinkingSteps": _thinking_steps(question, policies),
        }

    if any(token in q for token in ["parental", "maternity", "paternity", "baby", "birth", "child", "adoption"]):
        extra = " Because you are at Principal, Lead, or Head-of-Department level, the policy also gives you an additional 2 weeks of flexible return-to-work leave at reduced hours." if facts["eligibleForSeniorParentalTopUp"] else ""
        text = f"Yes, your profile meets the 12-month continuous service requirement for parental leave.{extra}" if facts["eligibleForParental"] else "Based on your profile, you are not yet eligible because parental leave requires at least 12 months of continuous service." + _hr_handoff(f"you're asking about parental leave with {employee.tenure_years} year(s) of service")
        return {"text": text, "source": "Parental Leave", "isRecommendation": False, "canSubmitLeave": False, "thinkingSteps": _thinking_steps(question, policies)}

    # Everything above this line is an ACTION or a live-data lookup -- submitting leave,
    # quoting a balance, offering a career path. Everything that reaches here is a policy
    # question, and they all get the same three-layer answer.
    #
    # This replaced three hand-written branches (work-from-home, notice period, bonus) that
    # duplicated the policy text in Python and had to be edited whenever a rule changed. The
    # WFH one had reimplemented the probation and parental clauses by hand. The wording now
    # comes from the policy itself and the eligibility line from policy_situation, so there
    # is one place to change and no chance of the two drifting apart.
    reply = _policy_reply(employee, question, policies)
    if reply:
        return reply

    return {
        "text": "I couldn't find a policy covering that. Try asking AskIvy about compassionate leave, annual leave, sick leave, parental leave, work from home, notice period, bonus, expenses, or conduct.",
        "source": _source(policies),
        "isRecommendation": False,
        "canSubmitLeave": False,
        "thinkingSteps": _thinking_steps(question, policies),
    }

def default_leave_dates(days):
    start = date.today() + timedelta(days=7)
    end = start + timedelta(days=max(days - 1, 0))
    return start, end
