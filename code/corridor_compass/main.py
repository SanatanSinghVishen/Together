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

from shared.config import US_CORRIDOR_AUDITOR_PORT as PORT, DATASETS_DIR
from shared.models import AuditResponse, AuditRequest

from core.corridor_auditor import AuditOrchestrator

app = FastAPI(title="Corridor Compass — US Readiness Auditor")

# Initialize Agent components
auditor_orchestrator = AuditOrchestrator()

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

@app.post("/api/audit", response_model=AuditResponse)
def audit_website(request: AuditRequest):
    if not request.url and not request.fallback_text:
        raise HTTPException(
            status_code=400,
            detail="You must provide either an active website 'url' or paste copy 'fallback_text' to run the audit."
        )
    try:
        response = auditor_orchestrator.run_audit(url=request.url, fallback_text=request.fallback_text, target_country=request.target_country)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/audit/stream")
def stream_audit_website(request: AuditRequest):
    if not request.url and not request.fallback_text:
        raise HTTPException(
            status_code=400,
            detail="You must provide either an active website 'url' or paste copy 'fallback_text' to run the audit."
        )
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
            res = auditor_orchestrator.run_audit(url=request.url, fallback_text=request.fallback_text, target_country=request.target_country, on_step=on_step)
            q.put({"type": "result", "data": res.model_dump()})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
    threading.Thread(target=run_agent, daemon=True).start()
    def generator():
        while True:
            try:
                item = q.get(timeout=45.0)
                yield f"data: {json.dumps(item)}\n\n"
                if item["type"] in ["result", "error"]:
                    break
            except queue.Empty:
                yield "data: {\"type\": \"ping\"}\n\n"
                break
    return StreamingResponse(generator(), media_type="text/event-stream")

@app.get("/api/urls")
def get_sample_urls():
    """Returns the pre-configured URLs from sample_urls.txt"""
    urls_file = os.path.join(DATASETS_DIR, "sample_urls.txt")
    if not os.path.exists(urls_file):
        return {"companies": [], "benchmarks": []}
        
    companies = []
    benchmarks = []
    
    with open(urls_file, "r") as f:
        lines = f.readlines()
        
    current_section = None
    for line in lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("# "):
            if "Indian SaaS" in cleaned:
                current_section = "companies"
            elif "US Enterprise" in cleaned:
                current_section = "benchmarks"
            continue
            
        if cleaned.startswith("http"):
            if current_section == "companies":
                companies.append(cleaned)
            elif current_section == "benchmarks":
                benchmarks.append(cleaned)
                
    return {
        "companies": companies,
        "benchmarks": benchmarks
    }

if __name__ == "__main__":
    print(f"Starting Corridor Compass server on http://localhost:{PORT}")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
