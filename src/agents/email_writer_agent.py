"""
Email-writer agent — CLI entry point and reusable function.

Usage:
  python src/agents/email_writer_agent.py --lead-json '{"hubspot_contact_id": "123", ...}' --step 0
  python src/agents/email_writer_agent.py --lead-file lead.json --step 4
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


FORBIDDEN_WORDS = {"innovative", "excited", "leverage", "synergy", "revolutionise", "revolutionize"}

TRIGGER_OPENINGS = {
    "demo_request": "Thanks for requesting a demo of Legora — I wanted to make sure you got the right introduction.",
    "webinar_no_show": "I saw you registered for our recent webinar but couldn't make it — completely understandable.",
    "webinar_no_trial": "I noticed you joined our webinar last week — hoping it was useful.",
    "event_lead": "Great to know you connected with the Legora team recently.",
    "backlog": "I wanted to reach out as Legora has evolved a lot since you first came across us.",
}

COUNTRY_CLIENT_MAP = {
    "GB": "BAHR",
    "UK": "BAHR",
    "United Kingdom": "BAHR",
    "US": "Goodwin",
    "United States": "Goodwin",
    "AU": "MinterEllison",
    "Australia": "MinterEllison",
    "DE": "Hengeler Mueller",
    "Germany": "Hengeler Mueller",
}

STEP_SUBJECTS = {
    0: "{first_name}, quick note from Legora",
    4: "Following up, {first_name}",
    10: "Closing the loop, {first_name}",
}


def _get_local_client(country: str) -> str | None:
    for key, val in COUNTRY_CLIENT_MAP.items():
        if key.lower() in country.lower():
            return val
    return None


def _build_system_prompt() -> str:
    return """You are writing outreach emails for Legora, an AI contract review platform for law firms.

Rules you must follow without exception:
- Maximum 120 words in the email body.
- Never use these words: innovative, excited, leverage, synergy, revolutionise, revolutionize.
- Address recipient by first name.
- Sign off: William\\nLegora (no title, no phone number).
- Plain text only — no HTML, no markdown, no bullet points.
- Return ONLY valid JSON, no prose before or after.
"""


def _build_user_prompt(lead: dict, step: int) -> str:
    first_name = lead.get("first_name", "there")
    trigger_type = lead.get("trigger_type", "backlog")
    tier = lead.get("firm_size_tier", "SMB")
    country = lead.get("country", "")
    lawyer_count = lead.get("lawyer_count", 0)
    local_client = _get_local_client(country)

    trigger_opening = TRIGGER_OPENINGS.get(trigger_type, TRIGGER_OPENINGS["backlog"])

    if tier == "SMB+":
        cta = "direct 25-minute product walkthrough — book at [CALENDLY_LINK]"
        cta_type = "demo"
    else:
        cta = "upcoming live demo webinar — sign up at [WEBINAR_LINK]"
        cta_type = "webinar"

    client_line = ""
    if local_client:
        client_line = f"Firms like {local_client} are already using Legora to cut contract review time by 60%."

    step_instructions = {
        0: f"""Write a first-touch email.
Opening: "{trigger_opening}"
Then: one sentence on what Legora does (AI contract review for law firms, faster + more accurate than manual review).
{"Include: " + client_line if client_line else ""}
CTA: invite them to the {cta}.
Sign off as William\\nLegora.""",

        4: f"""Write a follow-up email after an unanswered call attempt.
Acknowledge: "I also tried reaching you by phone last week — no luck, so thought I'd try here again."
Then briefly re-state Legora's value.
{"Include: " + client_line if client_line else ""}
CTA: {cta}.
Sign off as William\\nLegora.""",

        10: f"""Write a break-up email. Light, no pressure.
Acknowledge you've reached out a few times.
Leave the door open: "If the timing ever changes, I'll be here."
No CTA link.
Sign off as William\\nLegora.""",
    }

    subject = STEP_SUBJECTS[step].format(first_name=first_name)

    return f"""Write a step-{step} BDR email for Legora.

Contact: {first_name} {lead.get('last_name', '')}
Company: {lead.get('company_name', '')} ({lawyer_count} lawyers)
Country: {country}
Trigger: {trigger_type}
Tier: {tier}

{step_instructions[step]}

Return ONLY this JSON (no other text):
{{
  "hubspot_contact_id": "{lead['hubspot_contact_id']}",
  "sequence_step": {step},
  "subject": "{subject}",
  "body": "<email body here>",
  "cta_type": "{cta_type if step < 10 else 'none'}",
  "word_count": 0
}}

Fill in the body and set word_count to the actual word count of the body."""


def write_email(lead: dict, step: int) -> dict:
    if step not in (0, 4, 10):
        raise ValueError(f"sequence_step must be 0, 4, or 10, got {step}")

    from src.sandbox.client_factory import get_llm

    client = get_llm()

    if getattr(client, "is_mock", False):
        result = client.generate_email(lead, step)
    else:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        message = client.messages.create(
            model=model,
            max_tokens=600,
            system=_build_system_prompt(),
            messages=[{"role": "user", "content": _build_user_prompt(lead, step)}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)

    body = result.get("body", "")
    result["word_count"] = len(body.split())

    lower_body = body.lower()
    found = [w for w in FORBIDDEN_WORDS if w in lower_body]
    if found:
        result["_warnings"] = [f"Forbidden words found: {found}"]

    return result


def main():
    parser = argparse.ArgumentParser(description="Write a BDR email for a Legora lead")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lead-json", help="Enriched lead JSON string")
    group.add_argument("--lead-file", help="Path to enriched lead JSON file")
    parser.add_argument("--step", type=int, required=True, choices=[0, 4, 10],
                        help="Sequence step: 0 (first touch), 4 (follow-up), 10 (break-up)")
    args = parser.parse_args()

    if args.lead_json:
        lead = json.loads(args.lead_json)
    else:
        with open(args.lead_file) as f:
            lead = json.load(f)

    result = write_email(lead, args.step)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
