"""
Simulate the full 10-day outreach sequence for a single fixture lead.

Runs Day 0 → Day 2 (call stub) → Day 4 → Day 7 (call stub) → Day 10 emails
end-to-end so you can read them as a thread and check that the rhythm /
tone / CTAs make sense together.

Usage:
  python scripts/simulate_sequence.py --fixture demo_request_001
  python scripts/simulate_sequence.py --fixture backlog_001 --start-date 2026-05-01
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.agents.enrichment_agent import enrich_contact
from src.agents.segmentation_agent import segment_lead
from src.agents.email_writer_agent import write_email


SEPARATOR = "═" * 72


def _print_email(day: int, when: date, email: dict) -> None:
    print(SEPARATOR)
    print(f"Day {day}  |  {when.isoformat()}  |  EMAIL (step {email['sequence_step']})")
    print(SEPARATOR)
    print(f"Subject: {email['subject']}")
    print("─" * 72)
    print(email["body"])
    print("─" * 72)
    print(f"CTA: {email['cta_type']}  |  {email['word_count']} words")
    print()


def _print_call_stub(day: int, when: date, lead: dict) -> None:
    first = lead.get("first_name", "there")
    local = lead.get("local_client_reference")
    local_phrase = f"firms like {local}" if local else "firms like yours"
    print(SEPARATOR)
    print(f"Day {day}  |  {when.isoformat()}  |  VOICE CALL (Phase 2 — stub)")
    print(SEPARATOR)
    print(f"Script: Hi {first}, this is William calling from Legora — the AI contract review platform.")
    print(f"        I sent you an email recently and wanted to follow up briefly.")
    print(f"        If you have 2 minutes I'd love to tell you how {local_phrase} are using us.")
    print(f"        Feel free to call me back or just reply to my email. Thanks!")
    print("(voicemail-safe, under 30s)")
    print()


def simulate(fixture_id: str, start: date) -> None:
    os.environ.setdefault("BDR_MODE", "mock")

    enriched = enrich_contact(fixture_id)
    segmented = segment_lead(enriched)
    full_lead = {**enriched, **segmented}

    print(f"\nSimulating sequence for {fixture_id}")
    print(f"{enriched['first_name']} {enriched['last_name']} — {enriched['company_name']}  "
          f"({segmented['tier']}, {enriched['trigger_type']}, "
          f"{enriched['lawyer_count']} lawyers, {enriched['country']})")
    print()

    for day, step in [(0, 0), (2, None), (4, 4), (7, None), (10, 10)]:
        when = start + timedelta(days=day)
        if step is None:
            _print_call_stub(day, when, full_lead)
        else:
            email = write_email(full_lead, step)
            _print_email(day, when, email)

    print("End of simulated sequence. Day 10 break-up would be followed by a")
    print("HubSpot move-to-nurture action in the real pipeline.\n")


def main():
    parser = argparse.ArgumentParser(description="Simulate a full 10-day sequence")
    parser.add_argument("--fixture", required=True, help="Fixture contact id")
    parser.add_argument("--start-date", help="ISO date for Day 0 (default: today)")
    args = parser.parse_args()

    start = date.fromisoformat(args.start_date) if args.start_date else datetime.now().date()
    simulate(args.fixture, start)


if __name__ == "__main__":
    main()
