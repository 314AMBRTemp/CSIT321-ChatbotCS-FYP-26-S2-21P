"""API-level checks: does AskIvy give the RIGHT ANSWER, not just route correctly?

Why this exists
---------------
The Rasa e2e suite (rasa/tests/e2e_test_cases.yml) proves Claude routes to the right flow
and fills the right slots. It cannot prove the answers are correct, because Rasa sets
`sender_id` to the test case name plus a timestamp -- and in this system sender_id IS the
HRMS employee id. So every e2e test runs against an employee that does not exist, every
HRMS-backed action takes its API-unreachable branch, and the assertions still pass because
they only check that an action ran, never what it produced.

These checks close that half: they drive the same endpoints the widget uses, with REAL
seeded employee ids, and assert on the content of the reply.

Run (no venv activation needed):
    backend\\.venv\\Scripts\\python.exe tests\\api_checks.py

Requires Flask (:5000), the action server (:5055) and the Rasa server (:5005) running.
Exits non-zero if any check fails, so it can gate a commit.
"""

import os
import sys
import time

import requests

# 127.0.0.1, deliberately not "localhost". On Windows, localhost resolves to ::1 first and
# the Flask dev server only listens on IPv4, so every single request paid a ~2 second
# connect timeout before falling back -- roughly two minutes across this suite, and enough
# to make any timing assertion meaningless. Nothing to do with the app; it only ever showed
# up as "the checks are slow".
BASE = os.getenv("ASKIVY_API_URL", "http://127.0.0.1:5000").rstrip("/")
TIMEOUT = float(os.getenv("ASKIVY_CHECK_TIMEOUT", "90"))

_results = []


def check(name, passed, detail=""):
    _results.append((name, bool(passed), detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if detail and not passed:
        print(f"         {detail}")


def reset(employee_id):
    requests.post(f"{BASE}/api/askivy/rasa/reset", json={"employeeId": employee_id}, timeout=TIMEOUT)


def ask_rasa(employee_id, message, display_text=None):
    payload = {"employeeId": employee_id, "message": message}
    if display_text:
        payload["displayText"] = display_text
    r = requests.post(f"{BASE}/api/askivy/chat-rasa", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def ask_rules(employee_id, message):
    r = requests.post(
        f"{BASE}/api/askivy/chat", json={"employeeId": employee_id, "message": message}, timeout=TIMEOUT
    )
    r.raise_for_status()
    return r.json()


def leave_state(employee_id):
    r = requests.get(f"{BASE}/api/employees/{employee_id}/leave", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def clear_pending(employee_id):
    """Leave the employee with zero pending requests, so a check can seed exactly what it needs."""
    for req in leave_state(employee_id)["leaveHistory"]:
        if req["status"] == "Pending":
            requests.post(f"{BASE}/api/employees/{employee_id}/leave/{req['id']}/cancel", timeout=TIMEOUT)


def submit_leave(employee_id, leave_type, days=1):
    r = requests.post(
        f"{BASE}/api/askivy/submit-leave",
        json={"employeeId": employee_id, "type": leave_type, "days": days},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def pending_of(employee_id, leave_type):
    return [
        r for r in leave_state(employee_id)["leaveHistory"]
        if r["status"] == "Pending" and r["type"] == leave_type
    ]


# ── the checks ───────────────────────────────────────────────────────────────

def check_real_data_reaches_the_answer():
    """The single thing the e2e suite structurally cannot show."""
    print("\nReal HRMS data reaches the reply")
    reset("sarah")
    text = ask_rasa("sarah", "How many leave days do I have?")["text"]
    facts = requests.get(f"{BASE}/api/employees/sarah", timeout=TIMEOUT).json()["facts"]
    expected = str(facts["annualLeaveRemaining"])
    check(
        "leave balance quotes the employee's actual remaining days",
        expected in text and "can't reach the HRMS" not in text,
        f"expected {expected} in reply, got: {text[:120]}",
    )


def check_compassionate_day_counts():
    """The four policy figures corrected on 2026-08-09, on both engines."""
    print("\nCompassionate leave day counts (both engines)")
    cases = [
        ("mother", 5, "immediate family"),
        ("cousin", 3, "extended family"),
        ("mother-in-law", 3, "in-law is extended, not immediate"),
    ]
    for relation, expected_days, note in cases:
        reset("aiden")
        rasa = ask_rasa("aiden", f"My {relation} passed away")
        got = (rasa.get("suggestedLeave") or {}).get("days")
        check(f"rasa: {relation} -> {expected_days} days ({note})", got == expected_days, f"got {got}")

        rules = ask_rules("aiden", f"My {relation} passed away")
        got_rules = (rules.get("suggestedLeave") or {}).get("days")
        check(f"rules: {relation} -> {expected_days} days", got_rules == expected_days, f"got {got_rules}")


def check_senior_parental_top_up():
    """Widened from 'Principal' only to Principal/Lead/Head, in any department."""
    print("\nSenior parental top-up")
    for employee_id, should_have in [("rachel", True), ("meiling", True), ("priya", False)]:
        reset(employee_id)
        text = ask_rasa(employee_id, "Am I eligible for parental leave?")["text"]
        has = "extra 2 weeks" in text
        check(
            f"{employee_id}: top-up {'offered' if should_have else 'not offered'}",
            has == should_have,
            text[:120],
        )


def check_career_path_and_handoff():
    print("\nCareer path advice and the HR handoff")
    reset("siti")
    matched = ask_rasa("siti", "I want to move into Sales, what do I need to do?")["text"]
    check("matched path cites a real certification", "Certified Sales Professional" in matched, matched[:120])
    check("matched path cites the transfer requirement", "12 months in your current role" in matched, "")

    reset("siti")
    no_match = ask_rasa("siti", "What would it take to move into Marketing?")["text"]
    check("no-match says so honestly", "don't have a specific plan" in no_match, no_match[:120])
    check("no-match hands off to HR with context", "hr@lumenvale.com" in no_match and "Operations" in no_match, "")


def check_policy_question_is_not_a_bereavement():
    print("\nPolicy question does not trigger condolences")
    reset("kevin")
    text = ask_rasa("kevin", "What is the compassionate leave policy?")["text"]
    check("no condolences for a policy lookup", "sorry for your loss" not in text.lower(), text[:120])
    check("returns actual policy content", "paid working days" in text, text[:120])


def check_cancel_restores_balance():
    """Self-seeding so it stays idempotent: create a request, then cancel it.

    This is the branch the e2e suite can never reach -- action_find_pending_leave cannot
    find pending requests for an employee that does not exist.
    """
    print("\nCancelling a leave request restores the balance")
    employee_id = "junwei"

    # Normalise: clear any pending left by an earlier run so the flow sees exactly one.
    for req in leave_state(employee_id)["leaveHistory"]:
        if req["status"] == "Pending":
            requests.post(f"{BASE}/api/employees/{employee_id}/leave/{req['id']}/cancel", timeout=TIMEOUT)

    before = leave_state(employee_id)["facts"]["annualLeaveRemaining"]
    requests.post(
        f"{BASE}/api/askivy/submit-leave",
        json={"employeeId": employee_id, "type": "Annual", "days": 1},
        timeout=TIMEOUT,
    ).raise_for_status()
    after_submit = leave_state(employee_id)["facts"]["annualLeaveRemaining"]
    check("submitting deducts a day", after_submit == before - 1, f"{before} -> {after_submit}")

    reset(employee_id)
    ask_rasa(employee_id, "I'd like to cancel my pending leave request")
    confirmed = ask_rasa(employee_id, "/SetSlots(confirm_cancel=true)", display_text="Yes, cancel it")

    state = leave_state(employee_id)
    check("cancel confirms in the reply", "cancelled" in confirmed["text"].lower(), confirmed["text"][:120])
    check(
        "balance is restored",
        state["facts"]["annualLeaveRemaining"] == before,
        f"expected {before}, got {state['facts']['annualLeaveRemaining']}",
    )
    check(
        "no pending request left behind",
        not any(r["status"] == "Pending" for r in state["leaveHistory"]),
        "",
    )


def check_declining_keeps_the_request():
    """Declining must leave the request untouched.

    A decline that silently cancelled anyway would be the worst failure this feature could
    have, and nothing exercised this branch before.
    """
    print("\nDeclining a cancellation leaves the request alone")
    employee_id = "kevin"
    clear_pending(employee_id)
    submit_leave(employee_id, "Annual", 1)
    before = leave_state(employee_id)["facts"]["annualLeaveRemaining"]

    reset(employee_id)
    ask_rasa(employee_id, "I want to cancel my pending leave request")
    declined = ask_rasa(employee_id, "/SetSlots(confirm_cancel=false)", display_text="No, keep it")

    state = leave_state(employee_id)
    still_pending = [r for r in state["leaveHistory"] if r["status"] == "Pending"]
    check("reply says the request was kept", "kept" in declined["text"].lower(), declined["text"][:120])
    check("request is STILL pending", len(still_pending) == 1, f"found {len(still_pending)} pending")
    check(
        "balance unchanged by the decline",
        state["facts"]["annualLeaveRemaining"] == before,
        f"expected {before}, got {state['facts']['annualLeaveRemaining']}",
    )
    clear_pending(employee_id)


def check_multi_pending_disambiguation():
    """The branch that had never executed once -- in any test, or by hand.

    _match_pending() matches on leave TYPE first, then on a literal ISO date string, so this
    seeds one Annual and one Sick request and asks for the sick one by type.
    """
    print("\nTwo pending requests: the right one is cancelled")
    employee_id = "weijian"
    clear_pending(employee_id)
    submit_leave(employee_id, "Annual", 1)
    submit_leave(employee_id, "Sick", 1)
    check("two pending requests seeded", len(leave_state(employee_id)["leaveHistory"]) >= 2, "")

    reset(employee_id)
    asked = ask_rasa(employee_id, "I want to cancel a leave request")
    check(
        "bot asks which one rather than guessing",
        "which" in asked["text"].lower(),
        asked["text"][:140],
    )

    resolved = ask_rasa(employee_id, "the sick one")
    check("bot confirms a cancellation", "cancelled" in resolved["text"].lower(), resolved["text"][:140])
    check("it names the SICK request", "sick" in resolved["text"].lower(), resolved["text"][:140])

    check("sick request is gone from pending", len(pending_of(employee_id, "Sick")) == 0, "")
    check("annual request is untouched", len(pending_of(employee_id, "Annual")) == 1, "")
    clear_pending(employee_id)


def check_support_access_control():
    print("\nSupport log access")
    ok = requests.get(f"{BASE}/api/admin/chats", params={"requesterId": "nadia", "limit": 1}, timeout=TIMEOUT)
    check("admin can read the log", ok.status_code == 200, f"HTTP {ok.status_code}")

    denied = requests.get(f"{BASE}/api/admin/chats", params={"requesterId": "sarah"}, timeout=TIMEOUT)
    check("non-admin is refused", denied.status_code == 403, f"HTTP {denied.status_code}")

    anon = requests.get(f"{BASE}/api/admin/chats", timeout=TIMEOUT)
    check("no requester is refused", anon.status_code == 403, f"HTTP {anon.status_code}")


def explain(employee_id, question):
    r = requests.post(
        f"{BASE}/api/policies/explain",
        json={"employeeId": employee_id, "question": question},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def check_tailored_policy_answers():
    """The whole point of the tailored layer: two employees, one question, different answers.

    If this ever fails with both answers identical, the eligibility line has stopped being
    computed and the answer has quietly gone back to being a generic policy dump.
    """
    print("\nPolicy answers are tailored to the employee")

    marcus = explain("marcus", "Can I work from home?")      # probation
    sarah = explain("sarah", "Can I work from home?")        # returning from parental leave

    check("same question, different situations resolved",
          marcus["situation"] == "probation" and sarah["situation"] == "parental_return",
          f"marcus={marcus['situation']} sarah={sarah['situation']}")
    check("probation answer states the 4-day on-site rule",
          "4 days" in marcus["text"], marcus["text"][:160])
    check("parental answer offers the fully-remote arrangement",
          "fully-remote" in sarah["text"] or "fully remote" in sarah["text"], sarah["text"][:160])
    check("the two answers actually differ", marcus["text"] != sarah["text"], "")

    # Layer 3 is the receipt that makes layer 1 safe to generate. Its absence would mean a
    # generated paragraph is being shown with nothing to check it against.
    for name, answer in (("marcus", marcus), ("sarah", sarah)):
        check(f"{name}: verbatim rules are still quoted",
              "Just to summarise." in answer["text"]
              and "Employees may work remotely up to 3 days per week with manager approval." in answer["text"],
              answer["text"][-200:])


def check_no_offer_without_a_conditional_clause():
    """Policies whose rules don't depend on the employee must say nothing about them."""
    print("\nNo invented personalisation on unconditional policies")
    answer = explain("sarah", "what is the code of conduct")
    check("conduct policy resolves to standard", answer["situation"] == "standard", answer["situation"])
    check("no HR offer is made", answer["canRaiseHrRequest"] is False, "")
    check("no trailing question", answer["endsWithQuestion"] is False, "")
    check("still returns the real rules", "integrity" in answer["text"], answer["text"][:120])


def check_explanation_cache():
    """Second identical request must come from the cache, not a second generation."""
    print("\nGenerated prose is cached")
    first = explain("priya", "hybrid working rules")
    start = time.monotonic()
    second = explain("priya", "hybrid working rules")
    elapsed = time.monotonic() - start

    check("cached answer is byte-identical", first["text"] == second["text"], "")
    # A generation round trip is >1s; a cache hit is milliseconds. Generous bound so this
    # doesn't turn into a flaky timing test.
    check("cached answer returns fast", elapsed < 0.75, f"took {elapsed:.2f}s")


def check_closer_is_suppressed_after_a_question():
    """A reply that ends by asking something must not be followed by a second question."""
    print("\nClosing line respects the reply")
    reset("marcus")
    ends_with_question = ask_rasa("marcus", "Can I work from home?")["text"]
    check("no 'anything else' after the bot asked something",
          "Anything else" not in ends_with_question and "anything else" not in ends_with_question,
          ends_with_question[-160:])

    reset("kevin")
    no_question = ask_rasa("kevin", "what is the code of conduct")["text"]
    check("closer still appears when the reply didn't ask anything",
          "?" in no_question.split("Just to summarise.")[-1],
          no_question[-160:])


def check_hr_requests():
    print("\nRaising a request with HR")
    before = requests.get(
        f"{BASE}/api/admin/hr-requests", params={"requesterId": "nadia"}, timeout=TIMEOUT
    ).json()

    created = requests.post(
        f"{BASE}/api/hr-requests",
        json={
            "employeeId": "marcus",
            "topic": "Work From Home / Hybrid",
            "policyId": "WFH-01",
            "question": "Can I work from home?",
            "situation": "probation",
        },
        timeout=TIMEOUT,
    )
    check("request is created", created.status_code == 201, f"HTTP {created.status_code}")
    row = created.json()
    check("manager is copied from the employee record",
          row["managerEmail"] == "ethan@lumenvale.com", row.get("managerEmail"))
    check("opens in the Open state", row["status"] == "Open", row.get("status"))

    after = requests.get(
        f"{BASE}/api/admin/hr-requests", params={"requesterId": "nadia"}, timeout=TIMEOUT
    ).json()
    check("it shows up in the support view", len(after) == len(before) + 1,
          f"{len(before)} -> {len(after)}")

    denied = requests.get(
        f"{BASE}/api/admin/hr-requests", params={"requesterId": "marcus"}, timeout=TIMEOUT
    )
    check("non-admin cannot read HR requests", denied.status_code == 403, f"HTTP {denied.status_code}")

    unknown = requests.post(
        f"{BASE}/api/hr-requests", json={"employeeId": "nobody", "question": "hi"}, timeout=TIMEOUT
    )
    check("unknown employee is rejected", unknown.status_code == 404, f"HTTP {unknown.status_code}")


def main():
    print(f"AskIvy API checks against {BASE}")
    try:
        requests.get(f"{BASE}/api/health", timeout=10).raise_for_status()
    except requests.RequestException as exc:
        print(f"\n  Flask is not reachable at {BASE} -- start it with run-askivy.bat.\n  {exc}")
        return 1

    for fn in (
        check_real_data_reaches_the_answer,
        check_compassionate_day_counts,
        check_senior_parental_top_up,
        check_career_path_and_handoff,
        check_policy_question_is_not_a_bereavement,
        check_tailored_policy_answers,
        check_no_offer_without_a_conditional_clause,
        check_explanation_cache,
        check_closer_is_suppressed_after_a_question,
        check_hr_requests,
        check_cancel_restores_balance,
        check_declining_keeps_the_request,
        check_multi_pending_disambiguation,
        check_support_access_control,
    ):
        try:
            fn()
        except Exception as exc:  # a broken check should not hide the rest
            check(f"{fn.__name__} raised", False, repr(exc))

    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print(f"\n{'=' * 52}\n  {passed}/{total} checks passed\n{'=' * 52}")
    if passed != total:
        print("\n  Failed:")
        for name, ok, detail in _results:
            if not ok:
                print(f"    - {name}  {detail}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
