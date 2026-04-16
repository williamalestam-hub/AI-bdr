"""
HubSpot agent — CLI entry point and reusable function.

Usage:
  python src/agents/hubspot_agent.py --action fetch-triggers
  python src/agents/hubspot_agent.py --action log-touch --contact-id 123 --touch-type email --step 0 --outcome sent
  python src/agents/hubspot_agent.py --action update-step --contact-id 123 --step 2
  python src/agents/hubspot_agent.py --action move-to-nurture --contact-id 123
  python src/agents/hubspot_agent.py --action mark-pending --contact-id 123
  python src/agents/hubspot_agent.py --action mark-approved --contact-id 123
  python src/agents/hubspot_agent.py --action mark-rejected --contact-id 123
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.tools.hubspot_client import HubSpotClient


def main():
    parser = argparse.ArgumentParser(description="HubSpot agent for Legora BDR")
    parser.add_argument("--action", required=True, choices=[
        "fetch-triggers", "get-contact", "log-touch", "update-step",
        "move-to-nurture", "mark-pending", "mark-approved", "mark-rejected",
    ])
    parser.add_argument("--contact-id", help="HubSpot contact ID")
    parser.add_argument("--touch-type", choices=["email", "call", "voicemail"])
    parser.add_argument("--step", type=int)
    parser.add_argument("--outcome", choices=["sent", "pending", "failed", "approved", "rejected"])
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    hs = HubSpotClient()

    if args.action == "fetch-triggers":
        leads = hs.fetch_all_trigger_leads()
        print(json.dumps({"action": "fetch-triggers", "count": len(leads), "leads": leads}, indent=2))

    elif args.action == "get-contact":
        contact = hs.get_contact(args.contact_id)
        print(json.dumps({"action": "get-contact", "contact_id": args.contact_id, "success": True, "hubspot_response": contact}, indent=2))

    elif args.action == "log-touch":
        result = hs.log_touch(args.contact_id, args.touch_type, args.step, args.outcome, args.notes)
        print(json.dumps({"action": "log-touch", "contact_id": args.contact_id, "success": True, "hubspot_response": result}, indent=2))

    elif args.action == "update-step":
        result = hs.update_contact(args.contact_id, {"bdr_sequence_step": str(args.step)})
        print(json.dumps({"action": "update-step", "contact_id": args.contact_id, "success": True, "hubspot_response": result}, indent=2))

    elif args.action == "move-to-nurture":
        result = hs.move_to_nurture(args.contact_id)
        print(json.dumps({"action": "move-to-nurture", "contact_id": args.contact_id, "success": True, "hubspot_response": result}, indent=2))

    elif args.action == "mark-pending":
        result = hs.mark_pending(args.contact_id)
        print(json.dumps({"action": "mark-pending", "contact_id": args.contact_id, "success": True, "hubspot_response": result}, indent=2))

    elif args.action == "mark-approved":
        result = hs.mark_approved(args.contact_id)
        print(json.dumps({"action": "mark-approved", "contact_id": args.contact_id, "success": True, "hubspot_response": result}, indent=2))

    elif args.action == "mark-rejected":
        result = hs.mark_rejected(args.contact_id)
        print(json.dumps({"action": "mark-rejected", "contact_id": args.contact_id, "success": True, "hubspot_response": result}, indent=2))


if __name__ == "__main__":
    main()
