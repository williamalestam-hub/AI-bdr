"""
Grade generated emails against training/golden/*.json.

For each golden example:
  1. Load the matching fixture.
  2. Enrich + segment + write_email via the current agents.
  3. Score the output on four axes.

Scoring axes:
  - length (hard): body ≤ 120 words → pass/fail
  - forbidden_words (hard): none of the banned list → pass/fail
  - structural: trigger opening matches trigger type; signs off "William\\nLegora";
                CTA placeholder present when step < 10 → pass/fail per check
  - similarity: keyword overlap vs expected.body → 0.0–1.0 score

Usage:
  python scripts/grade.py
  python scripts/grade.py --json     # raw JSON output
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.agents.enrichment_agent import enrich_contact
from src.agents.segmentation_agent import segment_lead
from src.agents.email_writer_agent import write_email, FORBIDDEN_WORDS, TRIGGER_OPENINGS


GOLDEN_DIR = REPO_ROOT / "training" / "golden"
RUNS_DIR = REPO_ROOT / "training" / "runs"

WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(text) if len(w) > 2}


def similarity(generated: str, expected: str) -> float:
    g, e = _tokens(generated), _tokens(expected)
    if not e:
        return 0.0
    return round(len(g & e) / len(g | e), 3)


def grade_one(golden: dict) -> dict:
    fixture_id = golden["lead_fixture"]
    step = golden["step"]
    expected = golden["expected"]

    enriched = enrich_contact(fixture_id)
    segmented = segment_lead(enriched)
    full_lead = {**enriched, **segmented}
    generated = write_email(full_lead, step)

    body = generated.get("body", "")
    body_plain = body.replace("[TEMPLATE-MODE] ", "")
    words = len(body_plain.split())

    checks = {}

    checks["length_under_120"] = words <= 120

    lower = body_plain.lower()
    checks["no_forbidden_words"] = not any(w in lower for w in FORBIDDEN_WORDS)

    trigger = enriched["trigger_type"]
    expected_opening = TRIGGER_OPENINGS.get(trigger, "")
    checks["trigger_opening_present"] = expected_opening.split("—")[0].strip().lower() in lower

    checks["signoff_present"] = "william" in lower and "legora" in lower

    if step < 10:
        checks["cta_placeholder_present"] = (
            "[CALENDLY_LINK]" in body_plain or "[WEBINAR_LINK]" in body_plain
        )
    else:
        checks["no_cta_in_breakup"] = (
            "[CALENDLY_LINK]" not in body_plain and "[WEBINAR_LINK]" not in body_plain
        )

    sim = similarity(body_plain, expected["body"])
    cta_match = generated.get("cta_type") == expected.get("cta_type")

    return {
        "fixture": fixture_id,
        "step": step,
        "trigger": trigger,
        "tier": segmented["tier"],
        "word_count": words,
        "similarity_to_golden": sim,
        "cta_match": cta_match,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "generated": {
            "subject": generated["subject"],
            "body": body,
            "cta_type": generated.get("cta_type"),
        },
        "expected": expected,
    }


def _print_table(results: list[dict]) -> None:
    print(f"{'fixture':<28} {'trig':<18} {'tier':<5} {'words':>5} {'sim':>5} {'cta':>4} {'checks':>12}")
    print("─" * 88)
    for r in results:
        checks = r["checks"]
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        icon = "✓" if r["all_checks_passed"] else "✗"
        print(
            f"{r['fixture']:<28} {r['trigger']:<18} {r['tier']:<5} "
            f"{r['word_count']:>5} {r['similarity_to_golden']:>5.2f} "
            f"{('Y' if r['cta_match'] else 'N'):>4} "
            f"{icon} {passed}/{total}"
        )


def main():
    parser = argparse.ArgumentParser(description="Grade agent-generated emails against golden corpus")
    parser.add_argument("--json", action="store_true", help="Print raw JSON")
    args = parser.parse_args()

    os.environ.setdefault("BDR_MODE", "mock")

    golden_files = sorted(GOLDEN_DIR.glob("*.json"))
    if not golden_files:
        print(f"No golden examples in {GOLDEN_DIR}", file=sys.stderr)
        sys.exit(1)

    results = []
    for path in golden_files:
        with open(path) as f:
            golden = json.load(f)
        try:
            results.append(grade_one(golden))
        except Exception as e:
            results.append({
                "fixture": golden.get("lead_fixture"),
                "step": golden.get("step"),
                "error": str(e),
                "all_checks_passed": False,
            })

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = RUNS_DIR / f"grade-{ts}.json"
    with open(out_path, "w") as f:
        json.dump({"run_at": ts, "results": results}, f, indent=2)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        _print_table([r for r in results if "error" not in r])
        errors = [r for r in results if "error" in r]
        if errors:
            print("\nErrors:")
            for r in errors:
                print(f"  {r['fixture']} step {r['step']}: {r['error']}")

        passed = sum(1 for r in results if r.get("all_checks_passed"))
        print(f"\nSummary: {passed}/{len(results)} golden examples pass all checks")
        print(f"Full report: {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
