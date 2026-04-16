"""
MockClayClient — drop-in replacement for ClayClient.

Looks up firm data from fixtures/firms/firms.json. If the domain isn't in the
fixtures, generates a deterministic synthetic profile from a hash of the
domain so the same domain always produces the same lawyer_count/country.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
FIRMS_FILE = REPO_ROOT / "fixtures" / "firms" / "firms.json"

SYNTH_COUNTRIES = ["United Kingdom", "United States", "Australia", "Germany", "France", "Norway", "Canada"]
SYNTH_CITIES = {
    "United Kingdom": ("London", None),
    "United States": ("New York", "NY"),
    "Australia": ("Sydney", "NSW"),
    "Germany": ("Frankfurt", None),
    "France": ("Paris", None),
    "Norway": ("Oslo", None),
    "Canada": ("Toronto", "ON"),
}
SYNTH_PRACTICES = [
    ["Corporate", "M&A"],
    ["Commercial", "Corporate"],
    ["Litigation", "Dispute Resolution"],
    ["Real Estate", "Commercial"],
    ["Employment", "Commercial"],
    ["IP Litigation", "IP"],
    ["Tax", "Corporate"],
    ["Banking & Finance", "Corporate"],
]


def _synthetic_firm(domain: str) -> dict:
    digest = hashlib.sha256(domain.encode()).digest()
    raw = int.from_bytes(digest[:2], "big") % 250 + 1
    country = SYNTH_COUNTRIES[digest[2] % len(SYNTH_COUNTRIES)]
    practice = SYNTH_PRACTICES[digest[3] % len(SYNTH_PRACTICES)]
    city, state = SYNTH_CITIES.get(country, ("Unknown", None))
    return {
        "name": domain.split(".")[0].replace("-", " ").title() + " Law",
        "domain": domain,
        "lawyer_count": raw,
        "country": country,
        "hq_city": city,
        "hq_state": state,
        "practice_areas": practice,
        "_synthetic": True,
    }


class MockClayClient:
    def __init__(self, firms_file: Optional[Path] = None, **_kwargs):
        self.firms_file = Path(firms_file or FIRMS_FILE)
        self._firms = self._load_firms()

    def _load_firms(self) -> dict:
        if not self.firms_file.exists():
            return {}
        with open(self.firms_file) as f:
            return json.load(f)

    def enrich_company(self, domain: str, company_name: Optional[str] = None) -> dict:
        domain = domain.lower().strip()
        if domain in self._firms:
            return {"data": self._firms[domain]}
        return {"data": _synthetic_firm(domain)}

    def enrich_person(self, email: str, first_name: Optional[str] = None,
                      last_name: Optional[str] = None) -> dict:
        domain = email.split("@")[-1] if "@" in email else ""
        return self.enrich_company(domain)

    def extract_firm_data(self, clay_company: dict) -> dict:
        """Mirror ClayClient.extract_firm_data — normalises raw into our schema."""
        data = clay_company.get("data", clay_company)
        practice_areas = data.get("practice_areas") or data.get("specialties") or []
        if isinstance(practice_areas, str):
            practice_areas = [p.strip() for p in practice_areas.split(",") if p.strip()]
        return {
            "lawyer_count": int(data.get("lawyer_count") or data.get("employee_count") or 0),
            "practice_areas": practice_areas,
            "country": data.get("country") or data.get("hq_country") or "",
            "hq_city": data.get("hq_city") or data.get("city") or "",
            "hq_state": data.get("hq_state") or data.get("state") or None,
            "company_name": data.get("name") or data.get("company_name", ""),
            "company_domain": data.get("domain") or data.get("website", ""),
        }
