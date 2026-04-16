"""
Sandbox entry point — runs the full orchestrator against local fixtures and
prints a human-readable digest, plus writes the raw run to runs/digest-<ts>.json.

Usage:
  python -m src.sandbox.run_pipeline
  python -m src.sandbox.run_pipeline --json    # raw JSON only
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.agents.orchestrator import run_pipeline
from src.sandbox.client_factory import describe_mode


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "runs"


def _format_digest(result: dict) -> str:
    lines = []
    mode = result.get("mode", {})
    lines.append("═" * 72)
    lines.append(f"Legora BDR — Daily Digest  |  {result['run_at']}")
    lines.append(
        f"Mode: BDR_MODE={mode.get('BDR_MODE')}  "
        f"hubspot={mode.get('hubspot')}  "
        f"clay={mode.get('clay')}  "
        f"llm={mode.get('llm')}"
    )
    lines.append(
        f"{result['total_queued']} leads queued  "
        f"({result['total_leads_fetched']} fetched, "
        f"{len(result['errors'])} errors)"
    )
    lines.append("═" * 72)

    for i, entry in enumerate(result["digest"], 1):
        draft = entry["email_draft"]
        lines.append("")
        lines.append(
            f"#{i}  [score {entry['priority_score']:>3}]  "
            f"{entry['name']} — {entry['company']}  "
            f"({entry['tier']}, {entry['trigger_type']}, step {entry['sequence_step']})"
        )
        lines.append(f"     reasons: {', '.join(entry['priority_reasons'])}")
        lines.append(f"     Subject: {draft['subject']}")
        lines.append("     ─")
        for body_line in draft["body"].split("\n"):
            lines.append(f"     {body_line}")
        lines.append(f"     CTA: {draft['cta_type']}  |  words: {draft['word_count']}")
        if draft.get("_warnings"):
            lines.append(f"     ⚠ {draft['_warnings']}")

    if result["errors"]:
        lines.append("")
        lines.append("─── errors ─────────────────────────────────────────────────────────────")
        for err in result["errors"]:
            lines.append(f"  {err['contact_id']}: {err['error']}")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run the BDR pipeline in the sandbox")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of pretty output")
    args = parser.parse_args()

    # Default to mock mode when the sandbox runner is used directly
    os.environ.setdefault("BDR_MODE", "mock")

    result = run_pipeline(dry_run=True)

    RUNS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = RUNS_DIR / f"digest-{ts}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(_format_digest(result))
        print(f"Full run written to: {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
