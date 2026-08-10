"""The switch between the two policy repositories. Import policies from here.

    POLICY_SOURCE=database    policies table     (default, after validated cutover)
    POLICY_SOURCE=json        hr_policies.json   (the escape hatch)

Both sides are the same code path below the data layer: policy_repository.py and
policy_repository_db.py each hand their rows to score_policies() in policy_search.py, and
tests/policy_parity.py asserts the two produce identical results for identical questions
(25/25 at the time of writing, including the tie-breaking and no-match cases).

Why a switch instead of just deleting the JSON path: policies feed both chat engines, the
retrieval scorer and the career flow's citations. If the database source misbehaves on
Render, recovery is an environment variable and a restart -- no redeploy, no rollback, no
editing code against a deadline.

The source is read per call rather than captured at import, so flipping it in a test or a
shell doesn't require reimporting the module.
"""

import os

from services import policy_repository as _json_repo
from services import policy_repository_db as _db_repo


def active_source():
    """"database" or "json". Anything unrecognised means the file, on purpose -- a typo in
    an environment variable should degrade to the source that cannot fail, not crash."""
    return "json" if os.getenv("POLICY_SOURCE", "database").lower() == "json" else "database"


def _repo():
    """The configured repository, unless the database has no policies in it.

    The empty-corpus check is the one thing that makes defaulting to the database safe. A
    file that fails to load raises; a table that fails to seed just comes back empty, and an
    empty corpus is not an error anywhere downstream -- search_policies() would return [] and
    every policy question would answer "I couldn't find anything on that" while the service
    looked perfectly healthy. Falling back to the file turns a silent wrong answer into a
    correct one.
    """
    if active_source() == "json":
        return _json_repo
    return _db_repo if _db_repo.load_policies() else _json_repo


def load_policies():
    return _repo().load_policies()


def get_policy_by_id(policy_id):
    return _repo().get_policy_by_id(policy_id)


def get_policy_by_title(title):
    return _repo().get_policy_by_title(title)


def search_policies(question):
    return _repo().search_policies(question)
