"""
Interactive CLI to append a new golden email example.

Usage:
  python scripts/add_golden.py                  # interactive
  python scripts/add_golden.py --fixture demo_request_001 --step 0 \
      --tier SMB+ --subject "Rachel, ..." --body "Hi Rachel..." --cta demo

File naming convention: <trigger>__step<N>__<tier>.json
(tier SMB+ written as "smb_plus", SMB as "smb" in the filename)
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / "training" / "golden"
FIXTURES_DIR = REPO_ROOT / "fixtures" / "contacts"


def _tier_slug(tier: str) -> str:
    return {"SMB+": "smb_plus", "SMB": "smb"}.get(tier, tier.lower().replace("+", "_plus"))


def _prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or (default or "")


def _read_fixture_trigger(fixture_id: str) -> str:
    path = FIXTURES_DIR / f"{fixture_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No fixture {path}")
    with open(path) as f:
        data = json.load(f)
    return data.get("_trigger_type") or data.get("properties", {}).get("bdr_trigger_type", "backlog")


def _multiline_prompt(label: str) -> str:
    print(f"{label} (end with a single '.' on its own line):")
    lines = []
    while True:
        line = input()
        if line.strip() == ".":
            break
        lines.append(line)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Add a golden email example")
    parser.add_argument("--fixture", help="Fixture contact id (e.g. demo_request_001)")
    parser.add_argument("--step", type=int, choices=[0, 4, 10])
    parser.add_argument("--tier", choices=["SMB", "SMB+"])
    parser.add_argument("--subject")
    parser.add_argument("--body")
    parser.add_argument("--cta", choices=["demo", "webinar", "none"])
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    fixture = args.fixture or _prompt("Fixture id (e.g. demo_request_001)")
    trigger = _read_fixture_trigger(fixture)

    step = args.step if args.step is not None else int(_prompt("Step (0/4/10)", "0"))
    tier = args.tier or _prompt("Tier (SMB / SMB+)", "SMB+")
    subject = args.subject or _prompt("Subject")
    body = args.body or _multiline_prompt("Body")
    cta = args.cta or _prompt("CTA type (demo/webinar/none)", "demo")
    notes = args.notes or _prompt("Notes (optional)", "")

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{trigger}__step{step}__{_tier_slug(tier)}.json"
    out = GOLDEN_DIR / filename

    if out.exists():
        confirm = input(f"{filename} already exists — overwrite? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(1)

    record = {
        "lead_fixture": fixture,
        "step": step,
        "expected": {
            "subject": subject,
            "body": body,
            "cta_type": cta,
        },
        "notes": notes,
    }

    with open(out, "w") as f:
        json.dump(record, f, indent=2)

    print(f"Wrote {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
