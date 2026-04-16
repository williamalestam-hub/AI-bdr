"""
Template-based email generator used when ANTHROPIC_API_KEY is not set.

Produces emails that follow the same trigger / step / tier / country rules
as the real Claude prompt, so the downstream pipeline (grading, digest,
simulation) is fully exercisable with no external calls.

Every output body is prefixed with [TEMPLATE-MODE] so a template draft
is never confused with a real LLM draft.
"""

from src.agents.email_writer_agent import (
    TRIGGER_OPENINGS,
    COUNTRY_CLIENT_MAP,
    STEP_SUBJECTS,
)


TEMPLATE_BANNER = "[TEMPLATE-MODE]"


def _get_local_client(country: str) -> str | None:
    for key, val in COUNTRY_CLIENT_MAP.items():
        if key.lower() in (country or "").lower():
            return val
    return None


def _value_prop(local_client: str | None) -> str:
    if local_client:
        return (f"Firms like {local_client} are already using Legora to cut "
                f"contract review time by around 60%.")
    return ("Legora is an AI contract review platform — firms use it to cut "
            "review time substantially without sacrificing accuracy.")


def _step0_body(first_name: str, trigger_opening: str, value_prop: str,
                cta_line: str) -> str:
    return (
        f"Hi {first_name},\n\n"
        f"{trigger_opening}\n\n"
        f"{value_prop}\n\n"
        f"{cta_line}\n\n"
        f"William\nLegora"
    )


def _step4_body(first_name: str, value_prop: str, cta_line: str) -> str:
    return (
        f"Hi {first_name},\n\n"
        f"I also tried reaching you by phone last week — no luck, so thought I'd try here again.\n\n"
        f"{value_prop}\n\n"
        f"{cta_line}\n\n"
        f"William\nLegora"
    )


def _step10_body(first_name: str) -> str:
    return (
        f"Hi {first_name},\n\n"
        f"I've reached out a few times without hearing back, so I'll leave it there. "
        f"If the timing ever changes, I'll be here.\n\n"
        f"All the best,\n\n"
        f"William\nLegora"
    )


def generate_email(lead: dict, step: int) -> dict:
    first_name = lead.get("first_name") or "there"
    trigger_type = lead.get("trigger_type", "backlog")
    tier = lead.get("firm_size_tier", "SMB")
    country = lead.get("country", "")

    trigger_opening = TRIGGER_OPENINGS.get(trigger_type, TRIGGER_OPENINGS["backlog"])
    local_client = _get_local_client(country)
    value_prop = _value_prop(local_client)

    if tier == "SMB+":
        cta_line = "If useful, grab a 25-minute walkthrough here: [CALENDLY_LINK]."
        cta_type = "demo"
    else:
        cta_line = "We run a live demo webinar each week — save a seat here: [WEBINAR_LINK]."
        cta_type = "webinar"

    if step == 0:
        body = _step0_body(first_name, trigger_opening, value_prop, cta_line)
    elif step == 4:
        body = _step4_body(first_name, value_prop, cta_line)
    elif step == 10:
        body = _step10_body(first_name)
        cta_type = "none"
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
