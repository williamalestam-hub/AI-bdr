"""
Segmentation agent — CLI entry point and reusable function.

Tier logic (v2): title seniority is primary signal.
  - Senior titles (partner, chair, head, counsel, C-suite, …) → SMB+ → demo CTA
  - Junior titles (associate, trainee, paralegal, …)          → SMB  → webinar CTA
  - Unknown title → fall back to lawyer_count (≥10 → SMB+)

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
    "United States": "Goodwin", "US": "Goodwin",
    "AU": "MinterEllison", "Australia": "MinterEllison",
    "DE": "Hengeler Mueller", "Germany": "Hengeler Mueller",
    "Norway": "BAHR", "NO": "BAHR",
}

# Any of these words in a title (case-insensitive) → senior → demo tier
SENIOR_TITLE_KEYWORDS = {
    "partner", "chair", "co-chair", "head", "managing partner", "founding partner",
    "principal", "managing director", "counsel", "of counsel", "senior counsel",
    "ceo", "chairman", "cfo", "coo", "president", "vice president", "vp",
    "director", "practice group leader", "practice lead", "general counsel", "gc",
}

# Any of these → junior → webinar tier (takes priority over lawyer count fallback,
# but JUNIOR overrides SENIOR if both match — edge case, be conservative)
JUNIOR_TITLE_KEYWORDS = {
    "associate", "junior associate", "trainee", "paralegal",
    "clerk", "intern", "staff attorney", "legal assistant",
}


def _classify_title(title: str) -> str | None:
    """Returns 'senior', 'junior', or None (unknown)."""
    if not title:
        return None
    lower = title.lower()
    is_junior = any(kw in lower for kw in JUNIOR_TITLE_KEYWORDS)
    is_senior = any(kw in lower for kw in SENIOR_TITLE_KEYWORDS)
    if is_junior:
        return "junior"
    if is_senior:
        return "senior"
    return None


def segment_lead(enriched: dict) -> dict:
    lawyer_count = enriched.get("lawyer_count", 0) or 0
    country = enriched.get("country", "")
    title = enriched.get("title", "")
    sequence_step = int(enriched.get("bdr_sequence_step", 0) or 0)

    title_class = _classify_title(title)
    if title_class == "senior":
        tier = "SMB+"
    elif title_class == "junior":
        tier = "SMB"
    else:
        # Unknown title — fall back to lawyer count
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
        "title_classification": title_class,
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
