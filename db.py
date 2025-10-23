import os
import json
from typing import Dict

DB_FILE = "hiring_workflows.json"

def _ensure_db_exists():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({}, f)

def _load_db() -> Dict:
    _ensure_db_exists()
    try:
        with open(DB_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Warning: Error decoding database file: {e}")
        return {}

def save_state(job_id: str, state: Dict):
    """Saves the entire state for a given job ID."""
    _ensure_db_exists()
    db = _load_db()
    db[job_id] = state
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def load_state(job_id: str) -> Dict:
    """Loads the state for a given job ID."""
    db = _load_db()
    return db.get(job_id)