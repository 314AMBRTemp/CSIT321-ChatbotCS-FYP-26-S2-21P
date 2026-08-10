"""Turns policy rules into readable prose, cached per (policy, situation).

The generated layer of a policy answer. It rewords rules that are handed to it -- it does
not decide anything. Every determination about the employee was already made by
policy_situation.py, in Python, before this file is reached.

Why the cache is shaped this way
--------------------------------
The prose depends only on the policy's rules and which situation applies, never on who is
asking, so it is shared across every employee in the same situation. Ten policies with a few
situations each means the cache converges after a handful of questions and then costs nothing.

The employee's own numbers are NOT in here. The tailored line -- which quotes live figures
like a remaining leave balance -- is computed per request by the caller and appended after
this prose. Putting it in the cache would serve one employee's balance to another.

Invalidation is by Policy.updated_at rather than a TTL. Edit a policy in the admin editor and
its timestamp moves, so the stale paragraph is ignored on the next question. A TTL would
leave an outdated explanation sitting above freshly edited rules for however long it ran.

Failure is not fatal. If the key is missing or Anthropic is unreachable, generation returns
None and the caller falls back to the verbatim rules -- the answer gets plainer, never wrong.
"""

import os

import requests

from models import db, Policy, PolicyExplanation

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Same model the Rasa action server uses for chitchat. Fast enough to sit on the hot path,
# and this is rewording, not reasoning.
CLAUDE_MODEL = os.getenv("ASKIVY_EXPLAIN_MODEL", "claude-haiku-4-5-20251001")
HTTP_TIMEOUT = float(os.getenv("ASKIVY_EXPLAIN_TIMEOUT", "8"))

SYSTEM_PROMPT = """You are AskIvy, an HR assistant for Lumen & Vale.

You will be given the rules of one HR policy. Write the one-line gist of it -- the sentence
you would say to a colleague who asked in passing.

Your paragraph is the opening of a longer answer. Immediately after it comes a sentence about
this specific employee, and below that the full rules are printed verbatim. So you are not
summarising the policy for someone who will never see it -- you are giving them the shape of
it before they read it.

- ONE sentence. Two only if the policy genuinely has two unrelated halves.
- Lead with the main rule. Do NOT walk through every exception; they are printed below and
  the sentence after yours covers the one that actually applies.
- General and impersonal ("Employees may...", "Staff can..."), never "you".
- Do not speculate about any individual's circumstances or eligibility.

Hard rules:
- Use ONLY the rules given. Never add a number, entitlement, deadline or condition that is
  not in them.
- Do not open with a greeting, and do not end by offering further help. Something else
  handles that.
- Plain conversational English. No bullet points, no headings, no bold."""

# Bumped whenever SYSTEM_PROMPT changes. It forms part of the cache key because a prompt
# change does not move Policy.updated_at -- without it, every cached paragraph would keep
# being served from the previous prompt indefinitely.
PROMPT_VERSION = 2


def _generate(policy):
    """Ask Claude for the prose. Returns None on any failure -- callers must handle that."""
    if not ANTHROPIC_API_KEY:
        return None

    rules = "\n".join(f"- {rule}" for rule in policy.get("rules", []))
    prompt = (
        f"Policy: {policy['title']}\n\n"
        f"Rules:\n{rules}\n\n"
        "Write the general summary paragraph."
    )

    try:
        response = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 220,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        blocks = response.json().get("content", [])
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        return text.strip() or None
    except (requests.RequestException, ValueError, KeyError):
        return None


# The prose is general, so one entry serves every employee regardless of situation. The
# situation column stays in the schema because the table is keyed on it and a future
# situation-specific variant should not need a migration -- but nothing writes anything else
# to it today, and the duplication it caused when it did is why the prose is general now.
# The prompt version rides along in the same key, so rewording the prompt retires the old
# rows instead of leaving them to be served forever.
GENERAL = f"general:v{PROMPT_VERSION}"


def explain(policy):
    """Cached general prose for this policy, or None if it can't be produced.

    None is a normal outcome, not an error: no API key configured, Anthropic down, or a slow
    response. The caller renders the tailored line and verbatim rules alone in that case.
    """
    policy_id = policy["id"]
    row = db.session.get(Policy, policy_id)
    # Explaining a policy that isn't in the database (JSON fallback mode) is fine, it just
    # can't be cached -- there is no updated_at to invalidate against.
    if not row:
        return _generate(policy)

    cached = db.session.get(PolicyExplanation, (policy_id, GENERAL))
    if cached and cached.policy_updated_at == row.updated_at:
        return cached.text

    text = _generate(policy)
    if not text:
        return None

    if cached:
        cached.text = text
        cached.policy_updated_at = row.updated_at
    else:
        cached = PolicyExplanation(
            policy_id=policy_id,
            situation_key=GENERAL,
            text=text,
            policy_updated_at=row.updated_at,
        )
        db.session.add(cached)
    db.session.commit()
    return text
