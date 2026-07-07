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

from shared.config import OPERATOR_MEMORY_PORT as PORT, DATASETS_DIR
from shared.models import OperatorQueryRequest, OperatorQueryResponse

from core.operator_memory import OperatorMemoryAgent, get_store
from database.ingest import ingest_all_knowledge

app = FastAPI(title="TogetherMind — Operator Knowledge Assistant")

# Initialize Agent components
operator_agent = OperatorMemoryAgent()

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

class IngestResponse(BaseModel):
    status: str
    message: str

@app.post("/api/query", response_model=OperatorQueryResponse)
def query_operator_memory(request: OperatorQueryRequest):
    try:
        response = operator_agent.run_query(request.query, request.session_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query/stream")
def stream_query_operator_memory(request: OperatorQueryRequest):
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
            res = operator_agent.run_query(request.query, request.session_id, on_step=on_step)
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

@app.post("/api/ingest", response_model=IngestResponse)
def trigger_ingest():
    try:
        ingest_all_knowledge()
        return IngestResponse(status="success", message="Knowledge base successfully ingested.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
def get_status():
    """Returns the current document count in the knowledge base"""
    try:
        store = get_store(force_reload=True)
        count = store.collection.count()
        return {
            "status": "active" if count > 0 else "empty",
            "document_count": count
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "document_count": 0
        }

class CustomDocumentRequest(BaseModel):
    title: str
    content: str
    author: str = "Partner"
    url: str = "https://together.fund/custom"
    is_base64: bool = False
    file_type: str = "txt"

@app.post("/api/documents/add")
def add_custom_document(request: CustomDocumentRequest):
    if not request.title or not request.content:
        raise HTTPException(status_code=400, detail="Title and content are required.")
    try:
        store = get_store(force_reload=True)
        doc_content = request.content
        if request.is_base64:
            import base64
            decoded_bytes = base64.b64decode(request.content)
            if request.file_type == "pdf":
                import io
                import pypdf
                pdf_file = io.BytesIO(decoded_bytes)
                reader = pypdf.PdfReader(pdf_file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                doc_content = text
            else:
                doc_content = decoded_bytes.decode("utf-8", errors="ignore")
                
        if not doc_content.strip():
            raise HTTPException(status_code=400, detail="Document content is empty or could not be parsed.")
            
        chunks = []
        chunk_size = 800
        overlap = 150
        start = 0
        while start < len(doc_content):
            end = start + chunk_size
            chunks.append(doc_content[start:end])
            start += chunk_size - overlap
            
        import uuid
        doc_uuid = str(uuid.uuid4())[:8]
        
        ids = [f"custom_{doc_uuid}_chunk_{idx}" for idx in range(len(chunks))]
        metadatas = [{
            "title": request.title,
            "author": request.author,
            "url": request.url,
            "date": "Added Just Now",
            "source": "custom_upload"
        } for _ in range(len(chunks))]
        
        store.add_documents(chunks, metadatas, ids)
        
        return {
            "status": "success",
            "message": f"Successfully embedded and stored {len(chunks)} chunks in the vector database.",
            "chunk_count": len(chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"Starting TogetherMind server on http://localhost:{PORT}")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
