"""Parity check: does the database-backed policy repository behave identically to the JSON one?

Was the gate for the JSON-to-database migration -- it proved the mirror matched before
anything was repointed. That cutover is done; app.py's seed_policies() now seeds an empty
table once and never re-syncs, because policies are edited live through the admin UI
(/api/admin/policies) and a resync would silently discard those edits.

This means a FAIL here after the cutover is not automatically a bug. If someone has added or
edited a policy through the admin UI since the database was seeded, the file and the database
are SUPPOSED to differ now -- that divergence is the point of having an editable policy store.
Treat a failure as a prompt to check which side changed on purpose, not as "do not cut over"
the way it was written to be read originally.

Still useful for: confirming a fresh seed matches its source file, and confirming
POLICY_SOURCE=json (the rollback path) still reads the file correctly.

Run:
    backend\\.venv\\Scripts\\python.exe tests\\policy_parity.py

Needs no running server; it builds the app context itself.
"""

import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, BACKEND)

from app import create_app                       # noqa: E402
from services import policy_repository as json_repo        # noqa: E402
from services import policy_repository_db as db_repo       # noqa: E402

# Cover every topic boost, plus phrasings that hit the no-match fallback and the
# tie-breaking path where ordering decides the result.
QUERIES = [
    "how many annual leave days do I get",
    "my cousin died",
    "what is the compassionate leave policy",
    "am I eligible for parental leave",
    "do I need an MC for sick leave",
    "can I work from home",
    "what is my notice period if I resign",
    "how do I transfer to another department",
    "when is the performance bonus paid",
    "how do I claim expenses",
    "what is the code of conduct",
    "carry over unused leave",
    "maternity leave entitlement",
    "hybrid working rules",
    "something totally unrelated to HR",
    "bereavement",
    "switch department",
    "working from home after parental leave",
    "",
    "the",
]

failures = []


def report(name, passed, detail=""):
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    if not passed:
        print(f"         {detail}")
        failures.append(name)


def main():
    app = create_app()
    with app.app_context():
        json_policies = json_repo.load_policies()
        db_policies = db_repo.load_policies()

        print(f"\nCorpus ({len(json_policies)} JSON / {len(db_policies)} database)")
        report("same number of policies", len(json_policies) == len(db_policies),
               f"{len(json_policies)} vs {len(db_policies)}")
        report("same ids", {p["id"] for p in json_policies} == {p["id"] for p in db_policies},
               f"only in JSON: {ec if (ec := {p['id'] for p in json_policies} - {p['id'] for p in db_policies}) else '-'}")

        print("\nField-level equality")
        by_id = {p["id"]: p for p in db_policies}
        mismatched = []
        for policy in json_policies:
            other = by_id.get(policy["id"])
            if other != policy:
                mismatched.append(policy["id"])
        report("every policy is field-for-field identical", not mismatched, f"differ: {mismatched}")

        print("\nLookups")
        report("get_policy_by_id agrees",
               json_repo.get_policy_by_id("LEAVE-04") == db_repo.get_policy_by_id("LEAVE-04"), "")
        report("get_policy_by_id agrees on a miss",
               json_repo.get_policy_by_id("NOPE-99") == db_repo.get_policy_by_id("NOPE-99"), "")
        report("get_policy_by_title agrees",
               json_repo.get_policy_by_title("Annual Leave") == db_repo.get_policy_by_title("Annual Leave"), "")

        print(f"\nRetrieval across {len(QUERIES)} queries")
        for query in QUERIES:
            from_json = [p["id"] for p in json_repo.search_policies(query)]
            from_db = [p["id"] for p in db_repo.search_policies(query)]
            report(
                f"'{query[:38]}' -> {','.join(from_json) or '-'}",
                from_json == from_db,
                f"json={from_json} db={from_db}",
            )

        # Everything above compares the two repositories directly. This last section goes
        # through the HTTP routes with the switch flipped, which is what actually ships --
        # it catches a façade wired to the wrong module, or a route still importing a
        # repository directly and quietly ignoring POLICY_SOURCE.
        print("\nRoute-level parity through POLICY_SOURCE")
        client = app.test_client()

        def via_routes(source):
            os.environ["POLICY_SOURCE"] = source
            listed = [p["id"] for p in client.get("/api/policies").get_json()]
            searched = {}
            for q in QUERIES:
                response = client.get("/api/policies/search", query_string={"q": q})
                payload = response.get_json()
                # An empty q is a 400 with an error object, not a list of policies. Compare
                # status alongside the body so both sources have to reject it the same way.
                searched[q] = (
                    response.status_code,
                    [p["id"] for p in payload] if isinstance(payload, list) else payload,
                )
            return listed, searched

        try:
            json_listed, json_searched = via_routes("json")
            db_listed, db_searched = via_routes("database")
        finally:
            os.environ.pop("POLICY_SOURCE", None)

        report("GET /api/policies returns the same corpus", json_listed == db_listed,
               f"json={json_listed} db={db_listed}")
        differing = [q for q in QUERIES if json_searched[q] != db_searched[q]]
        report("GET /api/policies/search agrees on every query", not differing,
               f"differ: {differing}")
        report("the switch actually switches", db_repo.load_policies() and json_listed,
               "one of the sources returned nothing")

    total = 8 + len(QUERIES)
    print(f"\n{'=' * 52}\n  {total - len(failures)}/{total} parity checks passed\n{'=' * 52}")
    if failures:
        print("\n  The database copy does NOT match the JSON source. Do not cut over.")
        for name in failures:
            print(f"    - {name}")
        return 1
    print("\n  The database copy is equivalent. Cutover is safe to attempt behind a switch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
