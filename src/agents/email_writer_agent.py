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

# Kept for step-4 reference; no longer used as step-0 openers
TRIGGER_OPENINGS = {
    "demo_request": "Thanks for requesting a demo of Legora — I wanted to make sure you got the right introduction.",
    "webinar_no_show": "I saw you registered for our recent webinar but couldn't make it — completely understandable.",
    "webinar_no_trial": "I noticed you joined our webinar last week — hoping it was useful.",
    "event_lead": "Great to know you connected with the Legora team recently.",
    "backlog": "I wanted to reach out as Legora has evolved a lot since you first came across us.",
}

# Used in step-4 body as a local social-proof reference
COUNTRY_CLIENT_MAP = {
    "GB": "BAHR", "UK": "BAHR", "United Kingdom": "BAHR",
    "US": "Goodwin", "United States": "Goodwin",
    "AU": "MinterEllison", "Australia": "MinterEllison",
    "DE": "Hengeler Mueller", "Germany": "Hengeler Mueller",
    "Norway": "BAHR", "NO": "BAHR",
}

STEP_SUBJECTS = {
    0: "{first_name}, quick note from Legora",
    4: "Following up, {first_name}",
    10: "Closing the loop, {first_name}",
}

# Global reference firms used in step-0 (proven to resonate across markets)
GLOBAL_REFERENCE_FIRMS = "Goodwin and White & Case"


def _get_local_client(country: str) -> str | None:
    for key, val in COUNTRY_CLIENT_MAP.items():
        if key.lower() in (country or "").lower():
            return val
    return None


def _build_system_prompt() -> str:
    return """You are writing outreach emails for William at Legora, an AI contract review platform for law firms.

Voice: You write like a practicing attorney speaking to a peer, not a vendor pitching a product.
Credibility comes from understanding the day-to-day work of the recipient's practice area —
name real document types, not vague business outcomes.

Rules you must follow without exception:
- Maximum 120 words in the email body.
- Never use these words: innovative, excited, leverage, synergy, revolutionise, revolutionize.
- Address recipient by first name.
- Sign off: William\\nLegora (no title, no phone number).
- Plain text only — no HTML, no markdown, no bullet points.
- Step 0 CTAs are soft questions ("Would you be interested in…"), NOT hyperlinks.
- Step 4 CTAs include the link placeholder ([CALENDLY_LINK] or [WEBINAR_LINK]).
- Return ONLY valid JSON, no prose before or after.
"""


def _build_user_prompt(lead: dict, step: int) -> str:
    from src.tools.practice_pain_library import get_pain_phrase

    first_name = lead.get("first_name", "there")
    title = lead.get("title", "")
    primary_practice = lead.get("primary_practice_area", "Commercial")
    tier = lead.get("tier") or lead.get("firm_size_tier", "SMB")
    country = lead.get("country", "")
    lawyer_count = lead.get("lawyer_count", 0)
    local_client = _get_local_client(country)
    step4_reference = local_client or GLOBAL_REFERENCE_FIRMS

    pain_phrase = get_pain_phrase(primary_practice)

    cta_type = "demo" if tier == "SMB+" else "webinar"
    cta_link = "[CALENDLY_LINK]" if tier == "SMB+" else "[WEBINAR_LINK]"
    cta_question = (
        "Would you be interested in seeing a brief demo?"
        if tier == "SMB+" else
        "Would you be interested in joining one of our live demo webinars?"
    )

    title_class = lead.get("title_classification")
    is_senior = title and title_class != "junior"
    title_line = f"As {title}, you're" if is_senior else "You're"
    if not is_senior:
        pain_phrase = "spending too much time manually reviewing and marking up contracts across every matter"

    step_instructions = {
        0: f"""Write a first-touch email in peer-to-peer attorney voice.

Structure:
1. "I'm with Legora, the legal AI platform for {primary_practice} used by partners at {GLOBAL_REFERENCE_FIRMS}."
2. "{title_line} probably still spending too much time {pain_phrase}."
3. "I'd love to share the use cases that other attorneys are using heavily for similar work in your practice area and hear your thoughts."
4. "{cta_question}"
5. Sign off: William\\nLegora

Do NOT open with a trigger reference. Do NOT include a hyperlink. Do NOT use "I hope this email finds you well" or any similar filler.""",

        4: f"""Write a follow-up email after an unanswered call attempt.

Structure:
1. "I also tried reaching you by phone last week — no luck, so thought I'd try here again."
2. One sentence referencing {primary_practice} work at firms like {step4_reference} and how Legora helps cut review time.
3. Offer a concrete next step with the link: {cta_link}
4. Sign off: William\\nLegora""",

        10: f"""Write a break-up email. Light, no pressure, no CTA link.

Acknowledge you've reached out a few times without hearing back.
Leave the door open: "If the timing ever changes, I'll be here."
Sign off: William\\nLegora""",
    }

    subject = STEP_SUBJECTS[step].format(first_name=first_name)

    return f"""Write a step-{step} BDR email for Legora.

Contact: {first_name} {lead.get('last_name', '')}
Title: {title or 'unknown'}
Company: {lead.get('company_name', '')} ({lawyer_count} lawyers, {country})
Practice area: {primary_practice}
Tier: {tier}
Sequence step: {step}

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

Fill in the body. Set word_count to the actual word count of the body."""


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
