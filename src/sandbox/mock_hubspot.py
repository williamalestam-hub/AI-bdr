"""
MockHubSpotClient — drop-in replacement for HubSpotClient that reads from
fixtures/contacts/*.json and logs writes to runs/writes-<timestamp>.jsonl.

Method signatures match HubSpotClient exactly so the agents don't need to know
which one they're talking to.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures" / "contacts"
RUNS_DIR = REPO_ROOT / "runs"


class MockHubSpotClient:
    def __init__(self, fixtures_dir: Optional[Path] = None, writes_log: Optional[Path] = None):
        self.fixtures_dir = Path(fixtures_dir or FIXTURES_DIR)
        RUNS_DIR.mkdir(exist_ok=True)
        if writes_log is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            writes_log = RUNS_DIR / f"writes-{ts}.jsonl"
        self.writes_log = Path(writes_log)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _load_all_fixtures(self) -> list[dict]:
        if not self.fixtures_dir.exists():
            return []
        contacts = []
        for path in sorted(self.fixtures_dir.glob("*.json")):
            with open(path) as f:
                contacts.append(json.load(f))
        return contacts

    def get_contact(self, contact_id: str) -> dict:
        for contact in self._load_all_fixtures():
            if str(contact.get("id")) == str(contact_id):
                return contact
        raise ValueError(f"Mock contact {contact_id} not found in {self.fixtures_dir}")

    def search_contacts(self, trigger: str) -> list[dict]:
        return [c for c in self._load_all_fixtures() if c.get("_trigger_type") == trigger]

    def fetch_all_trigger_leads(self) -> list[dict]:
        return self._load_all_fixtures()

    # ------------------------------------------------------------------
    # Write (logged, never hits a real API)
    # ------------------------------------------------------------------

    def _log_write(self, action: str, contact_id: str, payload: dict) -> dict:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "contact_id": str(contact_id),
            "payload": payload,
        }
        with open(self.writes_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return {"mocked": True, **entry}

    def update_contact(self, contact_id: str, properties: dict) -> dict:
        return self._log_write("update_contact", contact_id, {"properties": properties})

    def log_engagement(self, contact_id: str, engagement_type: str, body: str,
                       timestamp: Optional[str] = None) -> dict:
        return self._log_write("log_engagement", contact_id, {
            "type": engagement_type,
            "body": body,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        })

    def log_touch(self, contact_id: str, touch_type: str, step: int,
                  outcome: str, notes: str = "") -> dict:
        return self._log_write("log_touch", contact_id, {
            "touch_type": touch_type,
            "step": step,
            "outcome": outcome,
            "notes": notes,
        })

    def mark_pending(self, contact_id: str) -> dict:
        return self._log_write("mark_pending", contact_id, {})

    def mark_approved(self, contact_id: str) -> dict:
        return self._log_write("mark_approved", contact_id, {})

    def mark_rejected(self, contact_id: str) -> dict:
        return self._log_write("mark_rejected", contact_id, {})

    def move_to_nurture(self, contact_id: str) -> dict:
        return self._log_write("move_to_nurture", contact_id, {})
