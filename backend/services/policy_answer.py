"""Assembles a policy answer from its three layers. Shared by both chat engines.

    1. generated prose      policy_explainer   -- the general gist, cached, may be absent
    2. tailored line        policy_situation   -- computed in Python, live figures, never cached
    3. verbatim rules       the policy itself  -- unchanged, quoted exactly

Layers 1 and 2 have to stay in their lanes. The first draft handed the employee's situation
to the generator as well, and it produced a paragraph that said exactly what the tailored
line then repeated a sentence later. Layer 1 is now general and impersonal ("Employees
may..."), layer 2 is the only place anything is said about the person asking.

Layer 3 is the receipt. It is why layer 1 is safe to generate: whatever the prose says, the
exact rules sit directly beneath it and the employee can check. If layer 1 can't be produced
(no API key, Anthropic down), the answer degrades to layers 2 and 3 -- plainer, still correct.

This lives in the backend rather than in the Rasa action on purpose. The deployed site runs
the rule-based engine, because Rasa is too heavy for a free Render service, so anything built
only into actions.py would never appear in the demo. Both engines call this.
"""

from services.policies import search_policies
from services.policy_explainer import explain
from services.policy_situation import SITUATION_CONFLICT, resolve_situation

SUMMARY_HEADING = "Just to summarise."


def _offer(employee, situation_key, has_tailored_note):
    """The closing offer, or None.

    Only offered where it means something. A policy that says nothing about this employee in
    particular (code of conduct, expenses) gets no offer -- there is nothing to raise. A
    situation the rules genuinely can't settle always gets one, because that is precisely
    when a human is needed.
    """
    if situation_key != SITUATION_CONFLICT and not has_tailored_note:
        return None

    manager = (employee or {}).get("managerName")
    if situation_key == SITUATION_CONFLICT:
        if manager:
            return f"I'd rather not guess on this one -- want me to raise it with HR and copy {manager}?"
        return "I'd rather not guess on this one -- want me to raise it with HR for you?"

    if manager:
        return f"Want me to raise a request with HR and copy {manager}?"
    return "Want me to raise a request with HR for you?"


def build_policy_answer(employee, question):
    """The full answer plus the metadata both engines need to render it.

    Returns None when the policy library can't be reached, so callers can keep their existing
    "I can't reach the policy library" handling rather than inventing a second one.
    """
    matches = search_policies(question)
    if not matches:
        return None

    policy = matches[0]
    situation_key, tailored = resolve_situation(employee, policy["id"])
    prose = explain(policy)
    offer = _offer(employee, situation_key, bool(tailored))

    rules = "\n".join(f"- {rule}" for rule in policy.get("rules", []))

    # Assembled in order, skipping whatever isn't there. Nothing emits a placeholder or a
    # hedge in place of a missing layer.
    paragraphs = [part for part in (prose, tailored, offer) if part]
    body = "\n\n".join(paragraphs)
    text = f"{body}\n\n{SUMMARY_HEADING}\n\n{rules}" if body else f"Here's what the {policy['title']} policy says:\n\n{rules}"

    return {
        "text": text,
        "policyId": policy["id"],
        "title": policy["title"],
        "source": " | ".join(p["title"] for p in matches[:2]),
        "situation": situation_key,
        "generated": bool(prose),
        # The offer is a question, so the caller must not append "anything else?" after it.
        "endsWithQuestion": bool(offer),
        "canRaiseHrRequest": bool(offer),
        "managerEmail": (employee or {}).get("managerEmail"),
    }
