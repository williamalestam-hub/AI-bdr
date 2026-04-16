"""
Practice-area pain phrases for the Legora BDR email system.

Each entry should read naturally in:
  "As {title}, you're probably still spending too much time {pain_phrase}."

Keep phrases concrete (name real document types), avoid generic business-speak.
"""

PAIN_PHRASES: dict[str, str] = {
    "litigation":
        "overseeing associates manually reviewing pleadings, discovery documents, "
        "and case law deal after deal",

    "ip litigation":
        "managing associates buried in manually reviewing prior art and case law "
        "across complex patent disputes",

    "ip":
        "managing associates buried in manually reviewing prior art, prosecution "
        "histories, and licence agreements",

    "real estate":
        "coordinating and guiding associates through developing contract forms, "
        "playbooks, and lease agreements project after project",

    "m&a":
        "guiding associates through repetitive NDA, purchase agreement, and "
        "disclosure document review deal after deal",

    "corporate":
        "coordinating associates through repetitive contract drafting and review "
        "across transactions",

    "banking & finance":
        "coordinating associates through credit agreement and facility document "
        "review deal after deal",

    "finance":
        "coordinating associates through credit agreement and facility document "
        "review deal after deal",

    "employment":
        "managing the manual review of employment contracts, settlement agreements, "
        "and restrictive covenants across matters",

    "tax":
        "overseeing associates checking compliance language across dozens of "
        "transaction documents deal after deal",

    "commercial":
        "coordinating and guiding associates through contract negotiation, NDA "
        "review, and playbook creation project after project",

    "dispute resolution":
        "overseeing associates manually reviewing and analysing case documents, "
        "witness statements, and settlement terms matter after matter",

    "restructuring":
        "managing associates through the review of complex debt documents, "
        "intercreditor agreements, and workout materials deal after deal",

    "construction":
        "coordinating associates through the review of building contracts, "
        "subcontractor agreements, and delay claims project after project",

    "default":
        "overseeing associates spending hours manually reviewing and marking up "
        "contracts deal after deal",
}


def get_pain_phrase(practice_area: str) -> str:
    """Look up pain phrase by practice area, case-insensitive, with fallback."""
    key = (practice_area or "").lower().strip()
    if key in PAIN_PHRASES:
        return PAIN_PHRASES[key]
    for candidate, phrase in PAIN_PHRASES.items():
        if candidate in key or key in candidate:
            return phrase
    return PAIN_PHRASES["default"]
