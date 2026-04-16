"""
Synthetic contact generator for the sandbox.

Produces plausible HubSpot-shaped contact JSON files — law firm domains,
distributed trigger types, weighted country mix, lognormal lawyer counts.

Usage:
  python scripts/generate_contacts.py --count 50
  python scripts/generate_contacts.py --count 100 --seed 42 --prefix synth
"""

import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "fixtures" / "contacts"


FIRST_NAMES = [
    "Alex", "Maria", "Chen", "Aisha", "Oliver", "Ingrid", "Raj", "Sofia",
    "Marcus", "Yuki", "Elena", "David", "Fatima", "Liam", "Nora", "Henry",
    "Zara", "Thomas", "Lina", "Samuel", "Clara", "Ethan", "Mei", "Noah",
    "Isla", "Felix", "Anya", "Jonas", "Hannah", "Leo",
]
LAST_NAMES = [
    "Okafor", "Hartley", "Sharma", "Becker", "Laurent", "Nguyen", "Schmidt",
    "O'Brien", "Patel", "Rossi", "Müller", "Dubois", "Sato", "Andersson",
    "Jansen", "Kowalski", "Álvarez", "Bianchi", "Henriksen", "Vidal",
    "Tanaka", "Fraser", "Morales", "Krause", "Lindqvist", "Haugen",
    "Carvalho", "Reddy", "Blake", "Norton",
]

DOMAINS = [
    ("helmsleylaw.co.uk", "Helmsley & Co", "United Kingdom"),
    ("bartonchambers.co.uk", "Barton Chambers", "United Kingdom"),
    ("whitemoore.co.uk", "White Moore LLP", "United Kingdom"),
    ("ashmead-partners.co.uk", "Ashmead Partners", "United Kingdom"),
    ("pembertonwells.co.uk", "Pemberton Wells", "United Kingdom"),
    ("drakerlaw.com", "Draker Law Group", "United States"),
    ("cliffmorgan.com", "Cliff Morgan PC", "United States"),
    ("harringtonstone.com", "Harrington Stone", "United States"),
    ("voss-levine.com", "Voss & Levine", "United States"),
    ("beaumont-hale.com", "Beaumont Hale", "United States"),
    ("nordlaw.se", "Nordlaw Advokater", "Sweden"),
    ("bergsjolegal.no", "Bergsjö Legal", "Norway"),
    ("schneiderpartner.de", "Schneider & Partner", "Germany"),
    ("holtzberg.de", "Holtzberg Rechtsanwälte", "Germany"),
    ("delacroix-avocats.fr", "Delacroix Avocats", "France"),
    ("martel-legal.fr", "Martel Legal", "France"),
    ("kellystroud.com.au", "Kelly & Stroud", "Australia"),
    ("hartfieldchambers.com.au", "Hartfield Chambers", "Australia"),
    ("vandermeer.nl", "Van der Meer Advocaten", "Netherlands"),
    ("strand-co.dk", "Strand & Co", "Denmark"),
]

TRIGGERS = [
    ("demo_request", 30),
    ("webinar_no_show", 25),
    ("webinar_no_trial", 20),
    ("event_lead", 15),
    ("backlog", 10),
]

STEPS = [(0, 80), (4, 15), (10, 5)]


def _weighted_choice(rng: random.Random, weighted: list[tuple]) -> object:
    total = sum(w for _, w in weighted)
    r = rng.uniform(0, total)
    acc = 0
    for value, weight in weighted:
        acc += weight
        if r <= acc:
            return value
    return weighted[-1][0]


def _lognormal_lawyer_count(rng: random.Random) -> int:
    # mu/sigma tuned so median ≈ 15, long tail to ~400
    mu, sigma = math.log(15), 1.2
    val = int(rng.lognormvariate(mu, sigma))
    return max(1, min(val, 500))


def _make_contact(idx: int, rng: random.Random, prefix: str) -> dict:
    domain, company, country = rng.choice(DOMAINS)
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    trigger = _weighted_choice(rng, TRIGGERS)
    step = _weighted_choice(rng, STEPS)
    clean_last = last.lower().replace("'", "")
    email_local = f"{first.lower()}.{clean_last}"

    created = datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 400))

    props = {
        "email": f"{email_local}@{domain}",
        "firstname": first,
        "lastname": last,
        "company": company,
        "website": domain,
        "country": country,
        "hs_lead_status": "NEW",
        "lifecyclestage": "lead",
        "hs_lead_source": trigger,
        "createdate": created.isoformat(),
        "bdr_sequence_step": str(step),
        "bdr_trigger_type": trigger,
    }

    if trigger == "demo_request":
        props["demo_request_date__c"] = created.isoformat()
    if trigger in ("webinar_no_show", "webinar_no_trial"):
        props["webinar_registered"] = "true"
        props["webinar_attended"] = "true" if trigger == "webinar_no_trial" else "false"
        if trigger == "webinar_no_trial":
            props["free_trial_started"] = "false"

    return {
        "id": f"{prefix}_{idx:04d}",
        "_trigger_type": trigger,
        "_synthetic_lawyer_count": _lognormal_lawyer_count(rng),
        "properties": props,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic BDR contact fixtures")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--prefix", default="synth")
    parser.add_argument("--out", default=str(FIXTURES_DIR))
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, args.count + 1):
        contact = _make_contact(i, rng, args.prefix)
        path = out_dir / f"{contact['id']}.json"
        with open(path, "w") as f:
            json.dump(contact, f, indent=2)

    print(f"Wrote {args.count} contacts to {out_dir.relative_to(REPO_ROOT)}  "
          f"(prefix={args.prefix}, seed={args.seed})")


if __name__ == "__main__":
    main()
