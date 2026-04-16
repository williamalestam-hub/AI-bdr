import os
import requests
from typing import Optional


class ClayClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ["CLAY_API_KEY"]
        self.base_url = (base_url or os.getenv("CLAY_ENRICHMENT_URL", "https://api.clay.com/v1")).rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def enrich_company(self, domain: str, company_name: Optional[str] = None) -> dict:
        payload = {"domain": domain}
        if company_name:
            payload["name"] = company_name

        resp = self.session.post(f"{self.base_url}/enrichment/company", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def enrich_person(self, email: str, first_name: Optional[str] = None, last_name: Optional[str] = None) -> dict:
        payload = {"email": email}
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name

        resp = self.session.post(f"{self.base_url}/enrichment/person", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def extract_firm_data(self, clay_company: dict) -> dict:
        """Normalise raw Clay company response into the fields we care about."""
        data = clay_company.get("data", clay_company)

        lawyer_count = (
            data.get("lawyer_count")
            or data.get("employee_count")
            or 0
        )

        practice_areas = (
            data.get("practice_areas")
            or data.get("specialties")
            or []
        )
        if isinstance(practice_areas, str):
            practice_areas = [p.strip() for p in practice_areas.split(",") if p.strip()]

        country = (
            data.get("country")
            or data.get("hq_country")
            or data.get("location", {}).get("country", "")
        )

        return {
            "lawyer_count": int(lawyer_count) if lawyer_count else 0,
            "practice_areas": practice_areas,
            "country": country,
            "company_name": data.get("name") or data.get("company_name", ""),
            "company_domain": data.get("domain") or data.get("website", ""),
        }
