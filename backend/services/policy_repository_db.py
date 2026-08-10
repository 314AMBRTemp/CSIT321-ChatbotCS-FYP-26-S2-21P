"""Policy retrieval, backed by the database. The migration target — NOT yet live.

Deliberately a mirror of services/policy_repository.py rather than a replacement:

    policy_repository.py     JSON file  ->  score_policies()   <- live
    policy_repository_db.py  database   ->  score_policies()   <- this file, validated first

Both call the same scorer from policy_search.py, so a difference between them can only come
from the data layer, never from the algorithm. tests/policy_parity.py asserts they agree.

Nothing imports this yet. The cutover happens only once parity is proven, and then behind a
switch so it can be reversed without a deploy.

Note the deliberate absence of @lru_cache. The JSON repository caches because the file never
changes at runtime; these rows are about to become editable, and a cache would serve stale
policies straight after an edit.
"""

from models import Policy
from services.policy_search import score_policies


def load_policies():
    """Every policy, in the order hr_policies.json lists them.

    Ordering matters far more than it looks, and getting it wrong is the bug this migration
    was most likely to ship. score_policies() sorts by score and Python's sort is stable, so
    equal-scoring policies fall back to input order. `ORDER BY id` looked like the obvious
    deterministic choice, but alphabetical id order is not file order -- and the fallback
    that answers a vague question with "here's the closest area I found" returns whichever
    policies come first. Ordering by id changed that answer from Annual Leave to Bonus.

    tests/policy_parity.py caught it. sort_order is what keeps it caught.
    """
    return [policy.to_dict() for policy in Policy.query.order_by(Policy.sort_order).all()]


def get_policy_by_id(policy_id):
    policy = Policy.query.get(policy_id)
    return policy.to_dict() if policy else None


def get_policy_by_title(title):
    return next(
        (p for p in load_policies() if p["title"].lower() == (title or "").lower()),
        None,
    )


def search_policies(question):
    return score_policies(load_policies(), question)
