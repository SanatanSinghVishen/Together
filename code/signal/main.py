import os
import uvicorn
import json
import queue
import threading
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from shared.config import PORTFOLIO_PULSE_PORT as PORT, DATASETS_DIR
from shared.models import PulseBriefingResponse

from core.portfolio_pulse import PortfolioPulseAgent
from database.db_manager import PulseMemory

app = FastAPI(title="Signal — Portfolio Health Triage")

# Initialize database controllers
db = PulseMemory()

# Auto load initial mock data if empty
companies_file = os.path.join(DATASETS_DIR, "portfolio_companies.json")
updates_file = os.path.join(DATASETS_DIR, "founder_updates.json")
db.load_initial_companies(companies_file)
db.load_initial_updates(updates_file)

# Initialize Agent components
pulse_agent = PortfolioPulseAgent()

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/workspace")
def read_workspace():
    return FileResponse(os.path.join(static_dir, "workspace.html"))

class ExtractedCompanyProfile(BaseModel):
    name: str
    sector: str
    stage: str
    founders: List[str]
    description: str
    investment_thesis: str
    founded: str

class AddCompanyRequest(BaseModel):
    id: str
    name: Optional[str] = None
    sector: Optional[str] = None
    stage: Optional[str] = None
    founded: Optional[str] = None
    founders: Optional[List[str]] = None
    description: Optional[str] = None
    investment_thesis: Optional[str] = None
    key_metrics: Optional[Dict[str, Any]] = None
    scrape_url: Optional[str] = None

@app.post("/api/company/add")
def add_new_company(request: AddCompanyRequest):
    try:
        from core.corridor_auditor import fetch_and_clean_page
        from shared.llm_client import TogetherLLMClient
        
        company_data = {
            "id": request.id.strip().lower(),
            "name": request.name,
            "sector": request.sector or "SaaS",
            "stage": request.stage or "Seed",
            "founded": request.founded or "2024",
            "founders": request.founders or [],
            "description": request.description or "",
            "investment_thesis": request.investment_thesis or "Acquired startup.",
            "key_metrics": request.key_metrics or {"arr": 0, "headcount": 1}
        }
        
        if request.scrape_url:
            try:
                scraped_data = fetch_and_clean_page(request.scrape_url)
                extraction_prompt = (
                    f"Extract the company profile details for the website of {request.id}.\n"
                    f"Website URL: {request.scrape_url}\n"
                    f"Scraped Web Content:\n"
                    f"Title: {scraped_data.get('title')}\n"
                    f"Headings: {', '.join(scraped_data.get('headings', []))}\n"
                    f"Paragraphs Preview:\n"
                    f"{' '.join(scraped_data.get('paragraphs', []))[:2000]}\n"
                )
                llm = TogetherLLMClient()
                extracted = llm.generate_structured(
                    prompt=extraction_prompt,
                    schema_class=ExtractedCompanyProfile,
                    system_instruction=(
                        "You are an expert venture capitalist. Extract the startup's name, sector, stage, "
                        "founders (list of names, or empty if not found), description (1-2 sentences), "
                        "investment thesis (1-2 sentences explaining why this space is hot), and founded year. "
                        "If you cannot find specific values, make a reasonable estimate based on the text."
                    )
                )
                company_data["name"] = request.name or extracted.name or request.id.capitalize()
                company_data["sector"] = request.sector or extracted.sector
                company_data["stage"] = request.stage or extracted.stage
                company_data["founders"] = request.founders or extracted.founders
                company_data["description"] = request.description or extracted.description
                company_data["investment_thesis"] = request.investment_thesis or extracted.investment_thesis
                company_data["founded"] = request.founded or extracted.founded
            except Exception as e:
                import logging
                logging.getLogger("Signal").error(f"Error scraping company profile: {e}")
                if not company_data["name"]:
                    company_data["name"] = request.id.capitalize()
        else:
            if not company_data["name"]:
                company_data["name"] = request.id.capitalize()
                
        db.save_company(company_data)
        
        return {
            "status": "success",
            "message": f"Startup '{company_data['name']}' has been successfully saved to the portfolio database.",
            "company": company_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BriefingRequest(BaseModel):
    week: int

@app.post("/api/briefing", response_model=PulseBriefingResponse)
def get_weekly_briefing(request: BriefingRequest):
    try:
        briefing = pulse_agent.generate_weekly_briefing(request.week)
        return briefing
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/briefing/stream")
def stream_weekly_briefing(request: BriefingRequest):
    q = queue.Queue()
    global_step_counter = 0
    def on_step(step):
        nonlocal global_step_counter
        global_step_counter += 1
        step_data = step.model_dump()
        step_data["step_num"] = global_step_counter
        q.put({"type": "step", "data": step_data})
    def run_agent():
        try:
            res = pulse_agent.generate_weekly_briefing(request.week, on_step=on_step)
            q.put({"type": "result", "data": res.model_dump()})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
    threading.Thread(target=run_agent, daemon=True).start()
    def generator():
        while True:
            try:
                item = q.get(timeout=30.0)
                yield f"data: {json.dumps(item)}\n\n"
                if item["type"] in ["result", "error"]:
                    break
            except queue.Empty:
                yield "data: {\"type\": \"ping\"}\n\n"
                break
    return StreamingResponse(generator(), media_type="text/event-stream")

@app.get("/api/companies")
def get_companies():
    try:
        return db.get_all_companies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/company/{company_id}/history")
def get_company_history(company_id: str):
    try:
        profile = db.get_company(company_id)
        updates = db.get_company_updates(company_id)
        signals = db.get_company_signals_history(company_id, max_weeks=6)
        
        if not profile:
            raise HTTPException(status_code=404, detail="Company not found")
            
        return {
            "profile": profile,
            "updates": updates,
            "signals": signals
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"Starting Signal server on http://localhost:{PORT}")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
