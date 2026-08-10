"""Policy retrieval, backed by the JSON file. The original and still the live source.

The scoring algorithm now lives in policy_search.py so the database-backed repository can
share it verbatim -- see policy_repository_db.py. Behaviour here is unchanged; verified
against a snapshot of the previous implementation across 18 queries.
"""

import json
from functools import lru_cache
from pathlib import Path

from services.policy_search import score_policies

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
    return score_policies(load_policies(), question)
