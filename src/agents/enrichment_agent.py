"""
Enrichment agent — CLI entry point and reusable function.

Usage:
  python src/agents/enrichment_agent.py --contact-id 12345
"""

import argparse
import json
import sys
import os
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.tools.hubspot_client import HubSpotClient
from src.tools.clay_client import ClayClient


TRIGGER_TYPE_MAP = {
    "demo_request": "demo_request",
    "webinar_no_show": "webinar_no_show",
    "webinar_no_trial": "webinar_no_trial",
    "event_lead": "event_lead",
    "backlog": "backlog",
}


def enrich_contact(contact_id: str) -> dict:
    hs = HubSpotClient()
    contact = hs.get_contact(contact_id)
    props = contact.get("properties", {})

    email = props.get("email", "")
    first_name = props.get("firstname", "")
    last_name = props.get("lastname", "")
    company_name = props.get("company", "")
    company_domain = props.get("website", "").replace("https://", "").replace("http://", "").split("/")[0]
    trigger_type = props.get("bdr_trigger_type") or contact.get("_trigger_type", "backlog")

    clay_enriched = False
    clay_data = {}
    lawyer_count = 0
    practice_areas = []
    country = props.get("country", "")
    enriched_company = company_name
    enriched_domain = company_domain

    clay_api_key = os.getenv("CLAY_API_KEY")
    if clay_api_key and company_domain:
        try:
            clay = ClayClient(api_key=clay_api_key)
            raw = clay.enrich_company(domain=company_domain, company_name=company_name)
            firm = clay.extract_firm_data(raw)

            lawyer_count = firm["lawyer_count"]
            practice_areas = firm["practice_areas"]
            country = firm["country"] or country
            enriched_company = firm["company_name"] or company_name
            enriched_domain = firm["company_domain"] or company_domain
            clay_data = raw
            clay_enriched = True
        except Exception as e:
            clay_data = {"error": str(e)}

    lawyer_count = int(lawyer_count) if lawyer_count else 0
    firm_size_tier = "SMB+" if lawyer_count >= 10 else "SMB"

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
        "company_name": enriched_company,
        "company_domain": enriched_domain,
        "country": country,
        "lawyer_count": lawyer_count,
        "practice_areas": practice_areas,
        "firm_size_tier": firm_size_tier,
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
