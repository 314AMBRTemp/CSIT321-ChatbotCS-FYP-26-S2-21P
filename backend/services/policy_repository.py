import json
from functools import lru_cache
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parent.parent / "data" / "hr_policies.json"

@lru_cache(maxsize=1)
def load_policies():
    with POLICY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def get_policy_by_id(policy_id):
    return next((p for p in load_policies() if p["id"] == policy_id), None)

def get_policy_by_title(title):
    return next((p for p in load_policies() if p["title"].lower() == title.lower()), None)

def search_policies(question):
    """Simple retrieval for local FYP demo. Can be replaced by vector search/RAG later."""
    q = question.lower()
    scored = []
    for policy in load_policies():
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

        if any(token in q for token in ["passed away", "died", "death", "bereavement", "funeral", "wake", "cousin", "aunt", "uncle"]):
            if policy["id"] == "LEAVE-04":
                score += 10
        if any(token in q for token in ["parental", "maternity", "paternity", "baby", "birth", "adoption"]):
            if policy["id"] == "LEAVE-02":
                score += 8
        if any(token in q for token in ["sick", "medical", "doctor", "mc", "clinic", "ill"]):
            if policy["id"] == "LEAVE-03":
                score += 8
        if any(token in q for token in ["annual", "holiday", "vacation", "balance", "carry"]):
            if policy["id"] == "LEAVE-01":
                score += 7
        if any(token in q for token in ["remote", "wfh", "hybrid", "work from home", "on-site", "onsite"]):
            if policy["id"] == "WFH-01":
                score += 8
        if any(token in q for token in ["notice", "resign", "quit", "departure"]):
            if policy["id"] == "RESIGN-01":
                score += 8
        # Kept narrow on purpose: bare "move"/"department" also appear in career and
        # leave questions, so only explicit transfer phrasing boosts this one.
        if any(token in q for token in ["transfer", "internal move", "change department", "switch department", "another department", "different department"]):
            if policy["id"] == "TRANSFER-01":
                score += 8
        if "bonus" in q:
            if policy["id"] == "BONUS-01":
                score += 8
        if any(token in q for token in ["expense", "claim", "receipt", "reimburse"]):
            if policy["id"] == "EXPENSE-01":
                score += 8
        if any(token in q for token in ["conduct", "harassment", "confidential", "respect"]):
            if policy["id"] == "CONDUCT-01":
                score += 8

        scored.append((score, policy))

    scored.sort(key=lambda item: item[0], reverse=True)
    hits = [policy for score, policy in scored if score > 0]
    return hits[:3] if hits else [policy for _, policy in scored[:2]]
