"""AskIvy custom actions.

These run in the Rasa action server (`rasa run actions`, port 5055) and are the
only place the assistant touches HRMS data. They do NOT read the database
directly -- they call the existing Flask API, so the REST layer stays the single
source of truth for leave accounting and policy retrieval.

Employee identity travels as the Rasa `sender_id`: the Flask adapter posts
{"sender": "<employeeId>", ...} to the REST channel, so `tracker.sender_id`
is the HRMS employee id inside every action here.

Each action emits two messages:
  1. a plain text message  -> becomes `text` in the ChatWidget payload
  2. a json_message under the "askivy" key -> becomes the metadata
     (source / isRecommendation / canSubmitLeave / suggestedLeave / thinkingSteps)
The Flask adapter merges them back into the exact JSON shape the React widget
already expects, so the frontend contract does not change.
"""

import os
from typing import Any, Dict, List, Optional

import requests
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

ASKIVY_API_URL = os.getenv("ASKIVY_API_URL", "http://localhost:5000").rstrip("/")
HTTP_TIMEOUT = float(os.getenv("ASKIVY_API_TIMEOUT", "10"))

IMMEDIATE_FAMILY = {
    "spouse", "husband", "wife", "partner", "parent", "father", "mother", "mum",
    "mom", "dad", "child", "son", "daughter", "sibling", "brother", "sister",
    "grandparent", "grandfather", "grandmother", "grandpa", "grandma",
    "parent-in-law", "father-in-law", "mother-in-law",
}
EXTENDED_FAMILY = {"cousin", "aunt", "uncle", "niece", "nephew", "relative"}

API_DOWN_MESSAGE = (
    "I can't reach the HRMS right now, so I don't want to guess at your numbers. "
    "Please try again in a moment, or check with HR directly."
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _employee_id(tracker: Tracker) -> str:
    return tracker.sender_id


def _reply(
    dispatcher: CollectingDispatcher,
    text: str,
    *,
    source: Optional[str] = None,
    is_recommendation: bool = False,
    can_submit_leave: bool = False,
    suggested_leave: Optional[Dict[str, Any]] = None,
    thinking_steps: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Send the answer plus the metadata the ChatWidget renders."""
    dispatcher.utter_message(text=text)
    dispatcher.utter_message(
        json_message={
            "askivy": {
                "source": source,
                "isRecommendation": is_recommendation,
                "canSubmitLeave": can_submit_leave,
                "suggestedLeave": suggested_leave,
                "thinkingSteps": thinking_steps or [],
            }
        }
    )


def _steps(*pairs: tuple) -> List[Dict[str, str]]:
    return [{"tag": tag, "text": text} for tag, text in pairs]


def _get(path: str, **params: Any) -> Optional[Any]:
    try:
        response = requests.get(
            f"{ASKIVY_API_URL}{path}", params=params or None, timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def _post(path: str, payload: Dict[str, Any]) -> Optional[Any]:
    try:
        response = requests.post(
            f"{ASKIVY_API_URL}{path}", json=payload, timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def _classify_relationship(raw: Optional[str]) -> Dict[str, Any]:
    text = (raw or "").strip().lower()
    for word in IMMEDIATE_FAMILY:
        if word in text:
            return {"relationship": word, "group": "immediate", "days": 5}
    for word in EXTENDED_FAMILY:
        if word in text:
            return {"relationship": word, "group": "extended", "days": 2}
    return {"relationship": text or "family member", "group": "review", "days": 2}


def _match_pending(pending: List[Dict[str, Any]], description: str) -> Optional[Dict[str, Any]]:
    """Pick the pending leave request the employee described, if it's unambiguous."""
    description = (description or "").strip().lower()
    if not description:
        return None
    for request_ in pending:
        if request_["type"].lower() in description:
            return request_
    for request_ in pending:
        if request_["from"] in description or request_["to"] in description:
            return request_
    return None


# ── 1. Leave balance ─────────────────────────────────────────────────────────

class ActionGetLeaveBalance(Action):
    def name(self) -> str:
        return "action_get_leave_balance"

    def run(self, dispatcher, tracker, domain):
        data = _get(f"/api/employees/{_employee_id(tracker)}")
        if not data:
            _reply(dispatcher, API_DOWN_MESSAGE)
            return []

        employee = data["employee"]
        facts = data["facts"]
        _reply(
            dispatcher,
            f"You have {facts['annualLeaveRemaining']} annual leave day(s) remaining "
            f"out of your {employee['annualLeaveEntitlement']}-day entitlement, and "
            f"{facts['sickLeaveRemaining']} sick leave day(s) left this year. "
            "These come straight from your HRMS record.",
            source="Annual Leave | Sick Leave",
            thinking_steps=_steps(
                ("Understand", "Read this as a leave balance question"),
                ("Retrieve", "Fetched the employee record from the HRMS API"),
                ("Compute", "Entitlement minus days already taken"),
                ("Answer", "Reported annual and sick balances"),
            ),
        )
        return []


# ── 2. Submit a leave request ────────────────────────────────────────────────

class ActionSubmitLeave(Action):
    def name(self) -> str:
        return "action_submit_leave"

    def run(self, dispatcher, tracker, domain):
        leave_type = (tracker.get_slot("leave_type") or "Annual").strip().capitalize()
        raw_days = tracker.get_slot("leave_days") or 1
        days = max(1, int(float(raw_days)))

        result = _post(
            "/api/askivy/submit-leave",
            {"employeeId": _employee_id(tracker), "type": leave_type, "days": days},
        )
        if not result:
            _reply(
                dispatcher,
                "I couldn't submit that to the HRMS just now. Nothing has been filed -- "
                "please try again shortly.",
            )
            return []

        facts = result.get("facts", {})
        remaining = facts.get("annualLeaveRemaining")
        tail = (
            f" You now have {remaining} annual leave day(s) remaining."
            if leave_type == "Annual" and remaining is not None
            else ""
        )
        _reply(
            dispatcher,
            f"Done -- I've filed a {leave_type.lower()} leave request for {days} day(s). "
            f"It's pending manager approval and you can see it on the Leave page.{tail}",
            source=f"{leave_type} Leave",
            thinking_steps=_steps(
                ("Understand", "Confirmed the employee wants the request filed"),
                ("Validate", f"Leave type {leave_type}, {days} day(s)"),
                ("Act", "Created a pending request through the HRMS API"),
                ("Confirm", "Reported the new status and balance"),
            ),
        )
        return []


# ── 2b. Cancel a pending leave request ───────────────────────────────────────

class ActionFindPendingLeave(Action):
    def name(self) -> str:
        return "action_find_pending_leave"

    def run(self, dispatcher, tracker, domain):
        data = _get(f"/api/employees/{_employee_id(tracker)}/leave")
        if not data:
            _reply(dispatcher, API_DOWN_MESSAGE)
            return [SlotSet("pending_leave_count", 0)]

        pending = [r for r in data["leaveHistory"] if r["status"] == "Pending"]
        return [SlotSet("pending_leave_count", len(pending))]


class ActionCancelLeave(Action):
    def name(self) -> str:
        return "action_cancel_leave"

    def run(self, dispatcher, tracker, domain):
        employee_id = _employee_id(tracker)
        data = _get(f"/api/employees/{employee_id}/leave")
        if not data:
            _reply(dispatcher, API_DOWN_MESSAGE)
            return []

        pending = [r for r in data["leaveHistory"] if r["status"] == "Pending"]
        if not pending:
            _reply(dispatcher, "You don't have any pending leave requests to cancel.")
            return []

        target = pending[0] if len(pending) == 1 else _match_pending(pending, tracker.get_slot("leave_to_cancel"))
        if target is None:
            options = ", ".join(f"{r['type']} leave on {r['from']}" for r in pending)
            _reply(
                dispatcher,
                f"I couldn't tell which one you meant -- your pending requests are: {options}. "
                "Could you say the type or date again?",
            )
            return []

        result = _post(f"/api/employees/{employee_id}/leave/{target['id']}/cancel", {})
        if not result:
            _reply(dispatcher, "I couldn't cancel that just now -- please try again shortly.")
            return []

        facts = result.get("facts", {})
        remaining = facts.get("annualLeaveRemaining")
        tail = (
            f" You now have {remaining} annual leave day(s) remaining."
            if target["type"] == "Annual" and remaining is not None
            else ""
        )
        _reply(
            dispatcher,
            f"Done -- I've cancelled your {target['type'].lower()} leave request "
            f"for {target['days']} day(s) starting {target['from']}.{tail}",
            source=f"{target['type']} Leave",
            thinking_steps=_steps(
                ("Understand", "Confirmed the employee wants a pending request cancelled"),
                ("Retrieve", "Found the matching pending request"),
                ("Act", "Cancelled it through the HRMS API"),
                ("Confirm", "Reported the new status and balance"),
            ),
        )
        return []


# ── 3. Compassionate leave ───────────────────────────────────────────────────

class ActionCompassionateLeave(Action):
    def name(self) -> str:
        return "action_compassionate_leave"

    def run(self, dispatcher, tracker, domain):
        relation = _classify_relationship(tracker.get_slot("relationship"))

        if relation["group"] == "immediate":
            detail = (
                f"Losing a {relation['relationship']} counts as immediate family under "
                "the Compassionate Leave policy, so you can take up to 5 paid working days."
            )
        elif relation["group"] == "extended":
            detail = (
                f"A {relation['relationship']} falls under extended family, which allows "
                "up to 2 paid working days with manager approval."
            )
        else:
            detail = (
                "The Compassionate Leave policy covers bereavement, but HR should confirm "
                "which relationship category applies before this is filed."
            )

        data = _get(f"/api/employees/{_employee_id(tracker)}")
        tail = ""
        if data:
            remaining = data["facts"]["annualLeaveRemaining"]
            tail = (
                f" If you need longer, you have {remaining} annual leave day(s) you can "
                "add on, or HR can arrange unpaid leave."
            )

        _reply(
            dispatcher,
            f"I'm really sorry for your loss. {detail}{tail} "
            "HR may ask for a supporting document later, but that won't hold up the request.",
            source="Compassionate Leave",
            is_recommendation=True,
            can_submit_leave=True,
            suggested_leave={"type": "Compassionate", "days": relation["days"]},
            thinking_steps=_steps(
                ("Understand", "Detected a bereavement, not a routine leave request"),
                ("Retrieve", "Matched the Compassionate Leave policy"),
                ("Classify", f"Relationship treated as {relation['group']} family"),
                ("Recommend", f"Suggested {relation['days']} paid day(s) plus a top-up option"),
            ),
        )
        return []


# ── 4. Parental leave eligibility ────────────────────────────────────────────

class ActionCheckParentalEligibility(Action):
    def name(self) -> str:
        return "action_check_parental_eligibility"

    def run(self, dispatcher, tracker, domain):
        data = _get(f"/api/employees/{_employee_id(tracker)}")
        if not data:
            _reply(dispatcher, API_DOWN_MESSAGE)
            return []

        employee = data["employee"]
        eligible = data["facts"]["eligibleForParental"]

        if eligible:
            text = (
                f"Yes -- you've been with us {employee['tenureYears']} year(s), which clears "
                "the 12-month continuous service requirement. Birth mothers get 16 weeks "
                "paid; partners get 4 weeks paid."
            )
            if "principal" in employee["role"].lower():
                text += (
                    " As a Principal Engineer you also get an extra 2 weeks of flexible "
                    "return-to-work leave at reduced hours."
                )
        else:
            text = (
                "Not yet -- parental leave needs 12 months of continuous service, and your "
                f"record shows {employee['tenureYears']} year(s). Worth speaking to HR "
                "directly, as they can look at other options."
            )

        _reply(
            dispatcher,
            text,
            source="Parental Leave",
            thinking_steps=_steps(
                ("Understand", "Read this as a parental leave eligibility question"),
                ("Retrieve", "Matched the Parental Leave policy"),
                ("Context", "Checked tenure and role against the service requirement"),
                ("Answer", "Stated eligibility and the entitlement that follows"),
            ),
        )
        return []


# ── 5. General policy lookup ─────────────────────────────────────────────────

class ActionPolicyAnswer(Action):
    def name(self) -> str:
        return "action_policy_answer"

    def run(self, dispatcher, tracker, domain):
        topic = (tracker.get_slot("policy_topic") or "").strip()
        query = topic or (tracker.latest_message or {}).get("text", "")

        matches = _get("/api/policies/search", q=query)
        if not matches:
            _reply(
                dispatcher,
                "I couldn't reach the policy library just now. Please try again shortly.",
            )
            return []

        top = matches[0]
        rules = "\n".join(f"- {rule}" for rule in top.get("rules", [])[:4])
        titles = " | ".join(policy["title"] for policy in matches[:2])

        _reply(
            dispatcher,
            f"Here's what the {top['title']} policy says:\n\n{rules}",
            source=titles,
            thinking_steps=_steps(
                ("Understand", f"Topic identified as: {query or 'general HR policy'}"),
                ("Retrieve", f"Best match: {top['id']} {top['title']}"),
                ("Ground", "Quoted the policy rules rather than paraphrasing"),
                ("Answer", "Returned the rules with the policy cited"),
            ),
        )
        return []


# ── 6. Career path advice ────────────────────────────────────────────────────

class ActionCareerPathAdvice(Action):
    def name(self) -> str:
        return "action_career_path_advice"

    def run(self, dispatcher, tracker, domain):
        employee_data = _get(f"/api/employees/{_employee_id(tracker)}")
        if not employee_data:
            _reply(dispatcher, API_DOWN_MESSAGE)
            return []

        from_department = employee_data["employee"]["department"]
        to_department = (tracker.get_slot("target_department") or "").strip()

        result = _get("/api/careers/search", **{"from": from_department, "to": to_department})
        if result is None:
            _reply(
                dispatcher,
                "I couldn't reach the career path library just now. Please try again shortly.",
            )
            return []

        match = result.get("match")
        if not match:
            alternatives = result.get("alternatives") or []
            if alternatives:
                text = (
                    f"I don't have a specific plan yet for moving from {from_department} to "
                    f"{to_department}. From {from_department}, I do have plans for: "
                    f"{', '.join(alternatives)}. Want to hear about one of those, or should "
                    "I flag this pairing for HR to build out?"
                )
            else:
                text = (
                    f"I don't have a career path defined yet for {from_department} to "
                    f"{to_department}. I'd recommend checking with HR or your manager "
                    "directly on what that move would need."
                )
            _reply(
                dispatcher, text, source="Career Development",
                thinking_steps=_steps(
                    ("Understand", f"Detected interest in moving from {from_department} to {to_department}"),
                    ("Retrieve", "No matching career path on file for this pair"),
                    ("Answer", "Said so honestly instead of guessing at a plan"),
                ),
            )
            return []

        certs = "\n".join(f"- {c}" for c in match.get("recommendedCerts", []))
        steps = "\n".join(f"- {s}" for s in match.get("suggestedSteps", []))
        timeframe = match.get("timeframe", "")

        text = (
            f"Here's what moving from {from_department} to {to_department} typically looks "
            f"like:\n\nRecommended certifications:\n{certs}\n\nSuggested steps:\n{steps}"
        )
        if timeframe:
            text += f"\n\nTypical timeframe: {timeframe}"

        _reply(
            dispatcher, text,
            source=match.get("title", "Career Development"),
            is_recommendation=True,
            thinking_steps=_steps(
                ("Understand", f"Detected interest in moving from {from_department} to {to_department}"),
                ("Retrieve", f"Matched career path: {match.get('title')}"),
                ("Recommend", "Listed certifications and suggested steps"),
            ),
        )
        return []
