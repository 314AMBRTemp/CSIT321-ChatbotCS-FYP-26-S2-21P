"""Career path retrieval — mirrors policy_repository.py on purpose.

Same rule as policies: this is structured data the bot cites, not something an
LLM invents on the fly. If a (from, to) pair isn't in the dataset, callers get
an honest "no plan for that yet" signal plus whatever alternatives exist from
the same starting department, rather than a fabricated-sounding answer.
"""

import json
from functools import lru_cache
from pathlib import Path

CAREER_PATH = Path(__file__).resolve().parent.parent / "data" / "career_paths.json"


@lru_cache(maxsize=1)
def load_career_paths():
    with CAREER_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_career_path(from_department, to_department):
    from_dep = (from_department or "").strip().lower()
    to_dep = (to_department or "").strip().lower()
    for path in load_career_paths():
        if path["fromDepartment"].lower() == from_dep and path["toDepartment"].lower() == to_dep:
            return path
    return None


def list_target_departments_from(from_department):
    from_dep = (from_department or "").strip().lower()
    return [p["toDepartment"] for p in load_career_paths() if p["fromDepartment"].lower() == from_dep]
