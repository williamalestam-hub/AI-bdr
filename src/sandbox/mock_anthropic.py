"""
Template-based email generator used when ANTHROPIC_API_KEY is not set.

Mirrors the new v2 lawyer-voice format so the downstream pipeline (grading,
digest, simulation) is fully exercisable with no external calls.

Every output body is prefixed with [TEMPLATE-MODE] so it's never confused with
a real LLM draft.
"""

from src.agents.email_writer_agent import (
    COUNTRY_CLIENT_MAP,
    STEP_SUBJECTS,
    GLOBAL_REFERENCE_FIRMS,
)


TEMPLATE_BANNER = "[TEMPLATE-MODE]"


def _get_local_client(country: str) -> str | None:
    for key, val in COUNTRY_CLIENT_MAP.items():
        if key.lower() in (country or "").lower():
            return val
    return None


def generate_email(lead: dict, step: int) -> dict:
    from src.tools.practice_pain_library import get_pain_phrase

    first_name = lead.get("first_name") or "there"
    title = lead.get("title", "")
    primary_practice = lead.get("primary_practice_area", "Commercial")
    tier = lead.get("tier") or lead.get("firm_size_tier", "SMB")
    country = lead.get("country", "")

    local_client = _get_local_client(country)
    title_class = lead.get("title_classification")
    pain_phrase = get_pain_phrase(primary_practice)
    # Trim the "deal after deal / project after project" suffix for step-4 inline use
    pain_short = pain_phrase.split(" deal after deal")[0].split(" project after project")[0].split(" matter after matter")[0]

    # Senior titles get "As {title}, you're …"; junior or unknown get "You're …"
    is_senior = title and title_class != "junior"
    title_line = f"As {title}, you're" if is_senior else "You're"

    # Associates do the reviewing themselves — use a first-person pain phrase
    if not is_senior:
        pain_phrase = f"manually reviewing and marking up contracts across every matter"

    cta_type = "demo" if tier == "SMB+" else "webinar"
    step4_reference = local_client or GLOBAL_REFERENCE_FIRMS

    if step == 0:
        cta_question = (
            "Would you be interested in seeing a brief demo?"
            if tier == "SMB+"
            else "Would you be interested in joining one of our live demo webinars?"
        )
        body = (
            f"Hi {first_name},\n\n"
            f"I'm with Legora, the legal AI platform for {primary_practice} "
            f"used by partners at {GLOBAL_REFERENCE_FIRMS}.\n\n"
            f"{title_line} probably still spending too much time {pain_phrase}.\n\n"
            f"I'd love to share the use cases that other attorneys are using heavily "
            f"for similar work in your practice area and hear your thoughts.\n\n"
            f"{cta_question}\n\n"
            f"William\nLegora"
        )

    elif step == 4:
        cta_link = "[CALENDLY_LINK]" if tier == "SMB+" else "[WEBINAR_LINK]"
        body = (
            f"Hi {first_name},\n\n"
            f"I also tried reaching you by phone last week — no luck, so thought I'd try here again.\n\n"
            f"I work with {primary_practice} teams at firms like {step4_reference} — "
            f"they're using Legora to cut the time spent {pain_short}.\n\n"
            f"Would you have 25 minutes for a quick walkthrough? {cta_link}\n\n"
            f"William\nLegora"
        )

    elif step == 10:
        cta_type = "none"
        body = (
            f"Hi {first_name},\n\n"
            f"I've reached out a few times without hearing back, so I'll leave it there. "
            f"If the timing ever changes, I'll be here.\n\n"
            f"All the best,\n\n"
            f"William\nLegora"
        )
    else:
        raise ValueError(f"sequence_step must be 0, 4, or 10 (got {step})")

    body = f"{TEMPLATE_BANNER} {body}"
    subject = STEP_SUBJECTS[step].format(first_name=first_name)

    return {
        "hubspot_contact_id": lead["hubspot_contact_id"],
        "sequence_step": step,
        "subject": subject,
        "body": body,
        "cta_type": cta_type,
        "word_count": len(body.split()),
        "_source": "mock_anthropic",
    }


class MockLLM:
    """Sentinel class so client_factory can return an object with a clear type."""
    is_mock = True

    def generate_email(self, lead: dict, step: int) -> dict:
        return generate_email(lead, step)
