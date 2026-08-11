"""Drafts a new policy from an admin's rough idea. Never saves anything itself.

The admin types something like "we need a business travel policy" into the Support tab's
policy editor; this turns that into a full draft -- title, category, summary, and 3-6
concrete rules -- in the same shape as an existing Policy row. The draft lands back in the
Add Policy form for the admin to edit, exactly like typing it by hand. Nothing is written to
the database here.

This is a genuinely different job from policy_explainer.py, which rewords rules that are
already true. Here the rules themselves are invented -- plausible, in the house style, but
not verified against anything, because there is nothing to verify against yet. That is why
the admin review step in the frontend is not optional the way it might look: this is the one
place in the app where the model is allowed to invent HR content, and the reason it's safe is
that nothing downstream treats a draft as fact until a human saves it.

Few-shot grounding comes from real policies already in the database rather than a hardcoded
example baked into the prompt, so the style follows whatever the corpus actually looks like
today, not a snapshot from whenever this file was written.
"""

import json
import os

import requests

from models import Policy

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Not the hot-path Haiku model policy_explainer.py uses -- this fires rarely (an admin
# drafting a new policy, not every employee question) and the output quality matters more
# than shaving off a second, so it defaults to a stronger model.
CLAUDE_MODEL = os.getenv("ASKIVY_DRAFT_MODEL", "claude-opus-5")
HTTP_TIMEOUT = float(os.getenv("ASKIVY_DRAFT_TIMEOUT", "20"))
MAX_EXAMPLES = 2

SYSTEM_PROMPT = """You are drafting a new HR policy for Lumen & Vale's policy library, from a
short, rough idea an HR admin typed in. What you produce is a DRAFT that a human reviews and
edits before it is ever saved or shown to an employee -- write plausible, specific defaults in
the house style, but you are not expected to know the company's actual real-world numbers, and
the admin is expected to correct every figure before publishing.

Match the style of the example policies you're given: plain, concrete, rule-based sentences,
not vague corporate language. "Employees with under 2 years of service receive 14 days of
annual leave per year" is the target register -- not "Employees are encouraged to take
reasonable time off."

Output ONLY valid JSON, no other text before or after it, in exactly this shape:
{
  "title": "Short policy title",
  "category": "1-3 word category, matching the style of the examples",
  "summary": "One or two sentence overview of what the policy covers",
  "rules": ["First specific rule.", "Second specific rule.", "..."]
}

Hard rules:
- 3 to 6 rules. Each one a complete, specific sentence, not a fragment or a heading.
- Do not include an "id" field -- that is assigned separately, outside this draft.
- Do not mention that this is a draft, AI-generated, or needs review anywhere in the text
  itself -- that is communicated by the UI around it, not the policy content."""


def _example_policies():
    """Up to two real policies from the database, for style grounding. Empty list (not an
    error) if the table is empty or unreachable -- the draft still works, just with less to
    go on, matching every other "degrade gracefully" path in this codebase."""
    try:
        rows = Policy.query.order_by(Policy.sort_order).limit(MAX_EXAMPLES).all()
        return [row.to_dict() for row in rows]
    except Exception:
        return []


def draft_policy(idea):
    """(draft_dict, None) on success, (None, error_message) on failure.

    error_message is written to be shown directly to the admin -- "no API key configured",
    "Claude did not return valid JSON", etc. -- since this is an interactive admin action, not
    a background fallback path like policy_explainer.py's silent None.
    """
    if not ANTHROPIC_API_KEY:
        return None, "ANTHROPIC_API_KEY is not set on the backend, so drafting is unavailable."

    idea = (idea or "").strip()
    if not idea:
        return None, "Describe the policy you want drafted first."

    examples = _example_policies()
    examples_block = "\n\n".join(
        f"Example -- {p['title']} ({p['category']}):\n"
        f"{p['summary']}\n" + "\n".join(f"- {rule}" for rule in p["rules"])
        for p in examples
    ) or "(No existing policies to show as examples -- use your own judgement on house style.)"

    prompt = f"{examples_block}\n\n---\n\nAdmin's rough idea for a new policy:\n{idea}"

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
                "max_tokens": 700,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return None, f"Couldn't reach Claude: {exc}"

    blocks = response.json().get("content", [])
    text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()
    # Claude generally honours "JSON only", but strip code-fence wrapping defensively rather
    # than fail a whole draft over three stray backticks.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        draft = json.loads(text)
    except ValueError:
        return None, "Claude didn't return valid JSON. Try rephrasing the idea, or try again."

    for field in ("title", "category", "summary", "rules"):
        if field not in draft:
            return None, f"Claude's draft was missing '{field}'. Try again."
    if not isinstance(draft["rules"], list) or not all(isinstance(r, str) for r in draft["rules"]):
        return None, "Claude's draft had a malformed rules list. Try again."

    return draft, None
