"""
AI BDR orchestrator — runs the full daily pipeline.

Usage:
  python src/agents/orchestrator.py --dry-run        # print digest, don't send to Slack
  python src/agents/orchestrator.py                   # full run: fetch → enrich → draft → queue digest
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.sandbox.client_factory import get_hubspot_client, describe_mode
from src.agents.enrichment_agent import enrich_contact
from src.agents.segmentation_agent import segment_lead
from src.agents.email_writer_agent import write_email
from src.agents.prioritizer import score_lead


SEQUENCE_EMAIL_STEPS = {0, 4, 10}


def should_process_today(enriched: dict) -> bool:
    step = int(enriched.get("bdr_sequence_step", 0) or 0)
    return step in SEQUENCE_EMAIL_STEPS


def run_pipeline(dry_run: bool = False) -> dict:
    hs = get_hubspot_client()
    leads = hs.fetch_all_trigger_leads()

    digest = []
    errors = []

    for contact in leads:
        contact_id = contact["id"]
        try:
            enriched = enrich_contact(contact_id)
            segmented = segment_lead(enriched)

            step = segmented["sequence_step"]
            if step not in SEQUENCE_EMAIL_STEPS:
                continue

            full_lead = {**enriched, **segmented}
            email_draft = write_email(full_lead, step)
            priority = score_lead(enriched, segmented)

            digest.append({
                "contact_id": contact_id,
                "name": f"{enriched['first_name']} {enriched['last_name']}",
                "company": enriched["company_name"],
                "tier": segmented["tier"],
                "trigger_type": enriched["trigger_type"],
                "sequence_step": step,
                "priority_score": priority["priority_score"],
                "priority_reasons": priority["reasons"],
                "email_draft": email_draft,
            })

            if not dry_run:
                hs.mark_pending(contact_id)

        except Exception as e:
            errors.append({"contact_id": contact_id, "error": str(e)})

    digest.sort(key=lambda x: x["priority_score"], reverse=True)

    result = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "mode": describe_mode(),
        "dry_run": dry_run,
        "total_leads_fetched": len(leads),
        "total_queued": len(digest),
        "errors": errors,
        "digest": digest,
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="Legora AI BDR orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and draft without writing to HubSpot or Slack")
    args = parser.parse_args()

    result = run_pipeline(dry_run=args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
