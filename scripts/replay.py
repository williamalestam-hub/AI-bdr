"""
Replay the sandbox pipeline and diff the digest against the most recent run.

Useful after a prompt change: "did anything regress?"

Usage:
  python scripts/replay.py
  python scripts/replay.py --full     # show full diff, not just changed entries
"""

import argparse
import difflib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.agents.orchestrator import run_pipeline


RUNS_DIR = REPO_ROOT / "runs"


def _latest_run() -> Path | None:
    RUNS_DIR.mkdir(exist_ok=True)
    runs = sorted(RUNS_DIR.glob("digest-*.json"))
    return runs[-1] if runs else None


def _summarise(digest: list[dict]) -> dict:
    """Reduce each entry to a stable comparable shape (drop timestamps, word counts)."""
    return {
        entry["contact_id"]: {
            "priority_score": entry["priority_score"],
            "subject": entry["email_draft"]["subject"],
            "body": entry["email_draft"]["body"],
            "cta_type": entry["email_draft"]["cta_type"],
        }
        for entry in digest
    }


def main():
    parser = argparse.ArgumentParser(description="Replay pipeline and diff vs last run")
    parser.add_argument("--full", action="store_true", help="Show full body diff, not summary")
    args = parser.parse_args()

    os.environ.setdefault("BDR_MODE", "mock")

    prev_path = _latest_run()
    if not prev_path:
        print("No previous run in runs/. Running pipeline once and writing baseline.")
        new = run_pipeline(dry_run=True)
        import datetime
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
        with open(RUNS_DIR / f"digest-{ts}.json", "w") as f:
            json.dump(new, f, indent=2)
        print(f"Baseline written. Re-run to see diffs.")
        return

    with open(prev_path) as f:
        prev = json.load(f)
    new = run_pipeline(dry_run=True)

    prev_sum = _summarise(prev["digest"])
    new_sum = _summarise(new["digest"])

    added = set(new_sum) - set(prev_sum)
    removed = set(prev_sum) - set(new_sum)
    common = set(new_sum) & set(prev_sum)

    changed = []
    for cid in common:
        if prev_sum[cid] != new_sum[cid]:
            changed.append(cid)

    print(f"Baseline: {prev_path.name}")
    print(f"Leads: {len(new_sum)} (prev {len(prev_sum)})  "
          f"added {len(added)}  removed {len(removed)}  changed {len(changed)}")

    if added:
        print(f"\n+ Added: {sorted(added)}")
    if removed:
        print(f"- Removed: {sorted(removed)}")

    if changed:
        print("\nChanged entries:")
        for cid in sorted(changed):
            print(f"\n── {cid} ──────────────────────────────────────────────────────")
            p, n = prev_sum[cid], new_sum[cid]
            if p["priority_score"] != n["priority_score"]:
                print(f"  score: {p['priority_score']} → {n['priority_score']}")
            if p["subject"] != n["subject"]:
                print(f"  subject: {p['subject']!r} → {n['subject']!r}")
            if args.full and p["body"] != n["body"]:
                diff = difflib.unified_diff(
                    p["body"].splitlines(), n["body"].splitlines(),
                    fromfile="prev", tofile="new", lineterm="",
                )
                for line in diff:
                    print(f"  {line}")
    else:
        print("\nNo changes.")


if __name__ == "__main__":
    main()
