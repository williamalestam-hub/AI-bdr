"""
Legora BDR — local web UI.

Usage:
  python ui/app.py                   # mock mode (default)
  ANTHROPIC_API_KEY=sk-... python ui/app.py   # real Claude, mock HubSpot/Clay
  BDR_MODE=real ... python ui/app.py           # fully live

Then open http://localhost:8000
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("BDR_MODE", "mock")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from src.agents.orchestrator import run_pipeline
from src.agents.enrichment_agent import enrich_contact
from src.agents.segmentation_agent import segment_lead
from src.agents.email_writer_agent import write_email
from src.sandbox.client_factory import describe_mode

RUNS_DIR     = REPO_ROOT / "runs"
FIXTURES_DIR = REPO_ROOT / "fixtures" / "contacts"
GOLDEN_DIR   = REPO_ROOT / "training" / "golden"
TRAINING_RUNS_DIR = REPO_ROOT / "training" / "runs"

app = FastAPI(title="Legora BDR", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_fixture(contact_id: str) -> dict:
    path = FIXTURES_DIR / f"{contact_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Fixture not found: {contact_id}")
    return json.loads(path.read_text())


def _recent_runs(directory: Path, pattern: str, limit: int = 10) -> list[dict]:
    files = sorted(directory.glob(pattern), reverse=True)[:limit]
    result = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            result.append({"filename": f.name, "data": data})
        except Exception:
            pass
    return result


# ── routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    html_file = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_file.read_text())


@app.get("/api/status")
def status():
    mode = describe_mode()
    return {
        "mode": mode,
        "fixture_count": len(list(FIXTURES_DIR.glob("*.json"))),
        "golden_count": len(list(GOLDEN_DIR.glob("*.json"))),
        "run_count": len(list(RUNS_DIR.glob("digest-*.json"))),
    }


@app.get("/api/contacts")
def list_contacts():
    contacts = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        try:
            raw = json.loads(path.read_text())
            props = raw.get("properties", {})
            contacts.append({
                "id": raw["id"],
                "name": f"{props.get('firstname','')} {props.get('lastname','')}".strip(),
                "title": props.get("jobtitle", ""),
                "company": props.get("company", ""),
                "trigger": raw.get("_trigger_type", props.get("bdr_trigger_type", "")),
                "step": props.get("bdr_sequence_step", "0"),
            })
        except Exception:
            pass
    return contacts


@app.post("/api/pipeline/run")
def api_run_pipeline():
    try:
        result = run_pipeline(dry_run=True)
        RUNS_DIR.mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        (RUNS_DIR / f"digest-{ts}.json").write_text(json.dumps(result, indent=2))
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


class SimulateRequest(BaseModel):
    fixture_id: str


@app.post("/api/simulate")
def api_simulate(req: SimulateRequest):
    try:
        enriched  = enrich_contact(req.fixture_id)
        segmented = segment_lead(enriched)
        full_lead = {**enriched, **segmented}

        steps = []
        for day, step_type, step_num in [
            (0,  "email", 0),
            (2,  "call",  None),
            (4,  "email", 4),
            (7,  "call",  None),
            (10, "email", 10),
        ]:
            if step_type == "email":
                email = write_email(full_lead, step_num)
                steps.append({"day": day, "type": "email", "data": email})
            else:
                local = segmented.get("local_client_reference") or "Goodwin"
                first = enriched["first_name"]
                steps.append({
                    "day": day,
                    "type": "call",
                    "data": {
                        "script": (
                            f"Hi {first}, this is William calling from Legora — "
                            f"the AI contract review platform. I sent you an email recently "
                            f"and wanted to follow up briefly. If you have 2 minutes I'd love "
                            f"to tell you how firms like {local} are using us. "
                            f"Feel free to call me back or just reply to my email. Thanks!"
                        )
                    },
                })

        return {
            "lead": {
                "name": f"{enriched['first_name']} {enriched['last_name']}",
                "title": enriched["title"],
                "company": enriched["company_name"],
                "tier": segmented["tier"],
                "trigger": enriched["trigger_type"],
                "primary_practice": enriched["primary_practice_area"],
                "lawyer_count": enriched["lawyer_count"],
                "country": enriched["country"],
            },
            "steps": steps,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


class EmailRequest(BaseModel):
    fixture_id: str
    step: int


@app.post("/api/email")
def api_write_email(req: EmailRequest):
    if req.step not in (0, 4, 10):
        raise HTTPException(400, "step must be 0, 4, or 10")
    try:
        enriched  = enrich_contact(req.fixture_id)
        segmented = segment_lead(enriched)
        full_lead = {**enriched, **segmented}
        result    = write_email(full_lead, req.step)
        return {
            "lead": {
                "name": f"{enriched['first_name']} {enriched['last_name']}",
                "title": enriched["title"],
                "company": enriched["company_name"],
                "tier": segmented["tier"],
                "primary_practice": enriched["primary_practice_area"],
            },
            "email": result,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/runs")
def list_runs():
    RUNS_DIR.mkdir(exist_ok=True)
    runs = []
    for path in sorted(RUNS_DIR.glob("digest-*.json"), reverse=True)[:20]:
        try:
            data = json.loads(path.read_text())
            runs.append({
                "filename": path.name,
                "run_at": data.get("run_at", ""),
                "total_queued": data.get("total_queued", 0),
                "total_fetched": data.get("total_leads_fetched", 0),
                "errors": len(data.get("errors", [])),
                "mode": data.get("mode", {}),
            })
        except Exception:
            pass
    return runs


@app.get("/api/runs/{filename}")
def get_run(filename: str):
    if not re.match(r"^digest-[\dT]+\.json$", filename):
        raise HTTPException(400, "Invalid filename")
    path = RUNS_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Run not found")
    return json.loads(path.read_text())


@app.get("/api/grade")
def api_grade():
    try:
        import importlib.util, io
        from contextlib import redirect_stdout

        # Run grade_one for every golden file
        from src.agents.enrichment_agent import enrich_contact as ec
        from src.agents.segmentation_agent import segment_lead as sl
        from src.agents.email_writer_agent import write_email as we, FORBIDDEN_WORDS

        results = []
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            golden = json.loads(path.read_text())
            fixture_id = golden["lead_fixture"]
            step       = golden["step"]
            expected   = golden["expected"]
            try:
                enriched  = ec(fixture_id)
                segmented = sl(enriched)
                full_lead = {**enriched, **segmented}
                generated = we(full_lead, step)

                body       = generated.get("body", "")
                body_plain = body.replace("[TEMPLATE-MODE] ", "")
                lower      = body_plain.lower()
                words      = len(body_plain.split())

                checks = {
                    "length_under_120": words <= 120,
                    "no_forbidden_words": not any(w in lower for w in FORBIDDEN_WORDS),
                    "signoff_present": "william" in lower and "legora" in lower,
                }
                if step == 0:
                    checks["legora_intro_present"] = "i'm with legora" in lower or "i am with legora" in lower
                    checks["step0_soft_cta"] = "would you be interested" in lower or "would you have" in lower
                elif step == 4:
                    checks["call_reference_present"] = "tried reaching you by phone" in lower
                    checks["cta_placeholder_present"] = "[CALENDLY_LINK]" in body_plain or "[WEBINAR_LINK]" in body_plain
                else:
                    checks["no_cta_in_breakup"] = "[CALENDLY_LINK]" not in body_plain and "[WEBINAR_LINK]" not in body_plain

                def _tok(t):
                    return {w.lower() for w in re.findall(r"[A-Za-z0-9']+", t) if len(w) > 2}
                g, e = _tok(body_plain), _tok(expected["body"])
                sim = round(len(g & e) / len(g | e), 3) if (g | e) else 0.0

                results.append({
                    "fixture": fixture_id,
                    "step": step,
                    "trigger": enriched["trigger_type"],
                    "tier": segmented["tier"],
                    "word_count": words,
                    "similarity": sim,
                    "cta_match": generated.get("cta_type") == expected.get("cta_type"),
                    "checks": checks,
                    "passed": all(checks.values()),
                    "generated_subject": generated.get("subject", ""),
                    "generated_body": body,
                })
            except Exception as ex:
                results.append({"fixture": fixture_id, "step": step, "error": str(ex), "passed": False})

        # Persist grade run
        TRAINING_RUNS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        (TRAINING_RUNS_DIR / f"grade-{ts}.json").write_text(json.dumps({"run_at": ts, "results": results}, indent=2))

        return {
            "run_at": ts,
            "total": len(results),
            "passed": sum(1 for r in results if r.get("passed")),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/golden")
def list_golden():
    examples = []
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            examples.append({
                "filename": path.name,
                "fixture": data.get("lead_fixture", ""),
                "step": data.get("step", 0),
                "subject": data.get("expected", {}).get("subject", ""),
                "cta_type": data.get("expected", {}).get("cta_type", ""),
                "notes": data.get("notes", ""),
            })
        except Exception:
            pass
    return examples


if __name__ == "__main__":
    print(f"\n  Legora BDR UI")
    print(f"  Mode: {describe_mode()}")
    print(f"  Open: http://localhost:8000\n")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RAILWAY_ENVIRONMENT") is None
    uvicorn.run("ui.app:app", host="0.0.0.0", port=port, reload=reload, app_dir=str(REPO_ROOT))
