"""
Enrichment agent — CLI entry point and reusable function.

Usage:
  python src/agents/enrichment_agent.py --contact-id 12345
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.sandbox.client_factory import get_hubspot_client, get_clay_client


TRIGGER_TYPE_MAP = {
    "demo_request": "demo_request",
    "webinar_no_show": "webinar_no_show",
    "webinar_no_trial": "webinar_no_trial",
    "event_lead": "event_lead",
    "backlog": "backlog",
}

# Keywords in a job title that hint at a practice area when Clay returns none
_TITLE_PRACTICE_HINTS = [
    ("ip litigation", "IP Litigation"),
    ("ip", "IP"),
    ("real estate", "Real Estate"),
    ("litigation", "Litigation"),
    ("m&a", "M&A"),
    ("mergers", "M&A"),
    ("corporate", "Corporate"),
    ("banking", "Banking & Finance"),
    ("finance", "Banking & Finance"),
    ("employment", "Employment"),
    ("tax", "Tax"),
    ("construction", "Construction"),
    ("restructuring", "Restructuring"),
    ("dispute", "Dispute Resolution"),
]


def _derive_primary_practice(practice_areas: list[str], title: str) -> str:
    if practice_areas:
        return practice_areas[0]
    title_lower = (title or "").lower()
    for keyword, practice in _TITLE_PRACTICE_HINTS:
        if keyword in title_lower:
            return practice
    return "Commercial"


def enrich_contact(contact_id: str) -> dict:
    hs = get_hubspot_client()
    contact = hs.get_contact(contact_id)
    props = contact.get("properties", {})

    email = props.get("email", "")
    first_name = props.get("firstname", "")
    last_name = props.get("lastname", "")
    title = props.get("jobtitle", "")
    company_name = props.get("company", "")
    company_domain = props.get("website", "").replace("https://", "").replace("http://", "").split("/")[0]
    trigger_type = props.get("bdr_trigger_type") or contact.get("_trigger_type", "backlog")

    clay_enriched = False
    clay_data = {}
    lawyer_count = 0
    practice_areas: list[str] = []
    country = props.get("country", "")
    hq_city = ""
    hq_state = None
    enriched_company = company_name
    enriched_domain = company_domain

    if company_domain:
        try:
            clay = get_clay_client()
            raw = clay.enrich_company(domain=company_domain, company_name=company_name)
            firm = clay.extract_firm_data(raw)

            lawyer_count = firm["lawyer_count"]
            practice_areas = firm["practice_areas"]
            country = firm["country"] or country
            hq_city = firm.get("hq_city", "")
            hq_state = firm.get("hq_state")
            enriched_company = firm["company_name"] or company_name
            enriched_domain = firm["company_domain"] or company_domain
            clay_data = raw
            clay_enriched = True
        except Exception as e:
            clay_data = {"error": str(e)}

    lawyer_count = int(lawyer_count) if lawyer_count else 0
    primary_practice_area = _derive_primary_practice(practice_areas, title)

    trigger_date = (
        props.get("demo_request_date__c")
        or props.get("bdr_last_touch_date")
        or props.get("createdate")
        or ""
    )

    return {
        "hubspot_contact_id": contact_id,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "title": title,
        "company_name": enriched_company,
        "company_domain": enriched_domain,
        "country": country,
        "hq_city": hq_city,
        "hq_state": hq_state,
        "lawyer_count": lawyer_count,
        "practice_areas": practice_areas,
        "primary_practice_area": primary_practice_area,
        "trigger_type": TRIGGER_TYPE_MAP.get(trigger_type, trigger_type),
        "trigger_date": trigger_date,
        "clay_enriched": clay_enriched,
        "raw_clay_response": clay_data,
    }


def main():
    parser = argparse.ArgumentParser(description="Enrich a HubSpot contact via Clay API")
    parser.add_argument("--contact-id", required=True, help="HubSpot contact ID")
    args = parser.parse_args()

    result = enrich_contact(args.contact_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
