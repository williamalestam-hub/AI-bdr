import os
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional


TRIGGER_QUERIES = {
    "demo_request": {
        "filterGroups": [{
            "filters": [
                {"propertyName": "hs_lead_status", "operator": "EQ", "value": "NEW"},
                {"propertyName": "demo_request_date__c", "operator": "HAS_PROPERTY"},
                {
                    "propertyName": "notes_last_contacted",
                    "operator": "NOT_HAS_PROPERTY",
                },
            ]
        }]
    },
    "webinar_no_show": {
        "filterGroups": [{
            "filters": [
                {"propertyName": "webinar_registered", "operator": "EQ", "value": "true"},
                {"propertyName": "webinar_attended", "operator": "NEQ", "value": "true"},
            ]
        }]
    },
    "webinar_no_trial": {
        "filterGroups": [{
            "filters": [
                {"propertyName": "webinar_attended", "operator": "EQ", "value": "true"},
                {"propertyName": "lifecyclestage", "operator": "NEQ", "value": "opportunity"},
                {"propertyName": "free_trial_started", "operator": "NEQ", "value": "true"},
            ]
        }]
    },
    "event_lead": {
        "filterGroups": [{
            "filters": [
                {"propertyName": "hs_lead_source", "operator": "EQ", "value": "event"},
                {"propertyName": "notes_last_contacted", "operator": "NOT_HAS_PROPERTY"},
            ]
        }]
    },
    "backlog": {
        "filterGroups": [{
            "filters": [
                {"propertyName": "lifecyclestage", "operator": "EQ", "value": "lead"},
                {"propertyName": "notes_last_contacted", "operator": "NOT_HAS_PROPERTY"},
                {
                    "propertyName": "createdate",
                    "operator": "BETWEEN",
                    "value": "2024-07-01",
                    "highValue": "2024-12-31",
                },
            ]
        }]
    },
}

CONTACT_PROPERTIES = [
    "email", "firstname", "lastname", "company", "website",
    "phone", "country", "hs_lead_status", "lifecyclestage",
    "notes_last_contacted", "hs_lead_source",
    "bdr_sequence_step", "bdr_last_touch_date",
    "bdr_approval_status", "bdr_trigger_type",
    "webinar_registered", "webinar_attended", "free_trial_started",
    "demo_request_date__c", "createdate",
]


class HubSpotClient:
    def __init__(self, access_token: Optional[str] = None):
        self.token = access_token or os.environ["HUBSPOT_ACCESS_TOKEN"]
        self.base = "https://api.hubapi.com"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_contact(self, contact_id: str) -> dict:
        resp = self.session.get(
            f"{self.base}/crm/v3/objects/contacts/{contact_id}",
            params={"properties": ",".join(CONTACT_PROPERTIES)},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def search_contacts(self, trigger: str) -> list[dict]:
        query = TRIGGER_QUERIES.get(trigger)
        if not query:
            raise ValueError(f"Unknown trigger: {trigger}")

        query["properties"] = CONTACT_PROPERTIES
        query["limit"] = 100

        resp = self.session.post(
            f"{self.base}/crm/v3/objects/contacts/search",
            json=query,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def fetch_all_trigger_leads(self) -> list[dict]:
        seen = set()
        leads = []
        for trigger_type, _ in TRIGGER_QUERIES.items():
            for contact in self.search_contacts(trigger_type):
                cid = contact["id"]
                if cid not in seen:
                    seen.add(cid)
                    contact["_trigger_type"] = trigger_type
                    leads.append(contact)
        return leads

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def update_contact(self, contact_id: str, properties: dict) -> dict:
        resp = self.session.patch(
            f"{self.base}/crm/v3/objects/contacts/{contact_id}",
            json={"properties": properties},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def log_engagement(self, contact_id: str, engagement_type: str, body: str, timestamp: Optional[str] = None) -> dict:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        payload = {
            "engagement": {
                "active": True,
                "type": engagement_type.upper(),
                "timestamp": ts,
            },
            "associations": {
                "contactIds": [int(contact_id)],
            },
            "metadata": {"body": body},
        }
        resp = self.session.post(
            f"{self.base}/engagements/v1/engagements",
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def log_touch(self, contact_id: str, touch_type: str, step: int, outcome: str, notes: str = "") -> dict:
        now = datetime.now(timezone.utc).isoformat()
        self.update_contact(contact_id, {
            "bdr_sequence_step": str(step),
            "bdr_last_touch_date": now,
            "bdr_approval_status": outcome,
        })
        return self.log_engagement(
            contact_id,
            "NOTE",
            f"[BDR] Step {step} {touch_type} — {outcome}. {notes}".strip(),
        )

    def mark_pending(self, contact_id: str) -> dict:
        return self.update_contact(contact_id, {"bdr_approval_status": "pending"})

    def mark_approved(self, contact_id: str) -> dict:
        return self.update_contact(contact_id, {"bdr_approval_status": "approved"})

    def mark_rejected(self, contact_id: str) -> dict:
        return self.update_contact(contact_id, {"bdr_approval_status": "rejected"})

    def move_to_nurture(self, contact_id: str) -> dict:
        return self.update_contact(contact_id, {
            "lifecyclestage": "lead",
            "bdr_approval_status": "nurture",
            "bdr_sequence_step": "10",
        })
