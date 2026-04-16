"""
Segmentation agent — CLI entry point and reusable function.

Usage:
  python src/agents/segmentation_agent.py --lead-json '{"hubspot_contact_id": "123", ...}'
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


COUNTRY_CLIENT_MAP = {
    "GB": "BAHR", "UK": "BAHR", "United Kingdom": "BAHR",
    "US": "Goodwin", "United States": "Goodwin",
    "AU": "MinterEllison", "Australia": "MinterEllison",
    "DE": "Hengeler Mueller", "Germany": "Hengeler Mueller",
}


def segment_lead(enriched: dict) -> dict:
    lawyer_count = enriched.get("lawyer_count", 0) or 0
    country = enriched.get("country", "")
    sequence_step = int(enriched.get("bdr_sequence_step", 0) or 0)

    tier = "SMB+" if lawyer_count >= 10 else "SMB"
    cta_type = "demo" if tier == "SMB+" else "webinar"
    ae_assigned = tier == "SMB+"

    local_client = None
    for key, val in COUNTRY_CLIENT_MAP.items():
        if key.lower() in country.lower():
            local_client = val
            break

    return {
        "hubspot_contact_id": enriched["hubspot_contact_id"],
        "tier": tier,
        "cta_type": cta_type,
        "ae_assigned": ae_assigned,
        "local_client_reference": local_client,
        "sequence_step": sequence_step,
    }


def main():
    parser = argparse.ArgumentParser(description="Segment an enriched Legora lead")
    parser.add_argument("--lead-json", required=True, help="Enriched lead JSON string")
    args = parser.parse_args()

    enriched = json.loads(args.lead_json)
    result = segment_lead(enriched)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
