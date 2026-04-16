"""
Lead priority scorer.

Given an enriched + segmented lead, returns a priority_score and a list of
reasons describing why the score was given.

Weights are defined at module top so they're easy to tune.
"""

TIER_WEIGHTS = {
    "SMB+": 40,
    "SMB": 0,
}

TRIGGER_WEIGHTS = {
    "demo_request": 30,
    "event_lead": 20,
    "webinar_no_trial": 15,
    "webinar_no_show": 10,
    "backlog": 5,
}

HIGH_VALUE_PRACTICE_KEYWORDS = {"corporate", "m&a", "commercial"}

LOCAL_CLIENT_BONUS = 10
LARGE_FIRM_BONUS = 10
LARGE_FIRM_THRESHOLD = 50


def score_lead(enriched: dict, segmented: dict) -> dict:
    reasons = []
    score = 0

    tier = segmented.get("tier", "SMB")
    tier_points = TIER_WEIGHTS.get(tier, 0)
    if tier_points:
        score += tier_points
        reasons.append(f"{tier} firm (+{tier_points})")

    trigger = enriched.get("trigger_type", "backlog")
    trigger_points = TRIGGER_WEIGHTS.get(trigger, 0)
    if trigger_points:
        score += trigger_points
        reasons.append(f"Trigger: {trigger} (+{trigger_points})")

    if segmented.get("local_client_reference"):
        score += LOCAL_CLIENT_BONUS
        reasons.append(
            f"Local reference client: {segmented['local_client_reference']} (+{LOCAL_CLIENT_BONUS})"
        )

    practice_areas = [p.lower() for p in (enriched.get("practice_areas") or [])]
    if any(any(k in p for k in HIGH_VALUE_PRACTICE_KEYWORDS) for p in practice_areas):
        score += LARGE_FIRM_BONUS
        reasons.append(f"High-value practice area (+{LARGE_FIRM_BONUS})")

    lawyer_count = enriched.get("lawyer_count", 0) or 0
    if lawyer_count >= LARGE_FIRM_THRESHOLD:
        score += LARGE_FIRM_BONUS
        reasons.append(f"Large firm ({lawyer_count} lawyers) (+{LARGE_FIRM_BONUS})")

    return {"priority_score": score, "reasons": reasons}
