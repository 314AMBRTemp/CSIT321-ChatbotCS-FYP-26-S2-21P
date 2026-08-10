"""Policy retrieval scoring — the algorithm, with no opinion about where policies live.

Extracted so the JSON-backed and database-backed repositories can share it verbatim. That
matters for the migration: with one scorer, a differential test between the two repositories
is testing the DATA LAYER only. If the algorithm lived in both, the two could drift and the
comparison would quietly stop meaning anything.

Pure function, no I/O, no caching. Callers supply the policies.
"""

# Keyword -> policy id boosts. Plain keyword overlap alone puts the wrong policy first for
# a lot of natural phrasings ("my cousin died" shares no words with "Compassionate Leave"),
# so these encode the domain knowledge that scoring can't infer.
TOPIC_BOOSTS = [
    (["passed away", "died", "death", "bereavement", "funeral", "wake", "cousin", "aunt", "uncle"], "LEAVE-04", 10),
    (["parental", "maternity", "paternity", "baby", "birth", "adoption"], "LEAVE-02", 8),
    (["sick", "medical", "doctor", "mc", "clinic", "ill"], "LEAVE-03", 8),
    (["annual", "holiday", "vacation", "balance", "carry"], "LEAVE-01", 7),
    (["remote", "wfh", "hybrid", "work from home", "on-site", "onsite"], "WFH-01", 8),
    (["notice", "resign", "quit", "departure"], "RESIGN-01", 8),
    # Kept narrow on purpose: bare "move"/"department" also appear in career and leave
    # questions, so only explicit transfer phrasing boosts this one.
    (["transfer", "internal move", "change department", "switch department", "another department", "different department"], "TRANSFER-01", 8),
    (["bonus"], "BONUS-01", 8),
    (["expense", "claim", "receipt", "reimburse"], "EXPENSE-01", 8),
    (["conduct", "harassment", "confidential", "respect"], "CONDUCT-01", 8),
]


def score_policies(policies, question):
    """Rank `policies` against `question`. Returns the best matches, most relevant first.

    Returns up to 3 policies that scored above zero. If nothing matched at all, returns the
    first 2 as a weak fallback rather than nothing -- the callers phrase that as "here's the
    closest area I found", which is honest about the uncertainty.
    """
    q = (question or "").lower()
    scored = []

    for policy in policies:
        haystack = " ".join([
            policy.get("id", ""),
            policy.get("title", ""),
            policy.get("category", ""),
            policy.get("summary", ""),
            " ".join(policy.get("rules", [])),
        ]).lower()

        score = 0
        for word in [w for w in q.replace("/", " ").replace("-", " ").split() if len(w) > 3]:
            if word in haystack:
                score += 1

        for tokens, policy_id, boost in TOPIC_BOOSTS:
            if policy["id"] == policy_id and any(token in q for token in tokens):
                score += boost

        scored.append((score, policy))

    scored.sort(key=lambda item: item[0], reverse=True)
    hits = [policy for score, policy in scored if score > 0]
    return hits[:3] if hits else [policy for _, policy in scored[:2]]
