# TogetherMind — Operator Knowledge Assistant

TogetherMind is an AI-powered operating partner assistant designed for early-stage startup founders. It acts as an automated RAG tool that ingests the fund's strategy playbooks, blog posts, and past Q&A emails, allowing founders to query business guidelines 24/7.

## Key Features
* **Semantic RAG Search**: Queries unstructured essays and VC playbooks.
* **Inline Document Citations**: Cites specific sources and relevance scores for trust.
* **GP Escalation Protocol**: Detects high-stakes/subjective questions (e.g. founder disputes, legal liability) and routes them to a human General Partner (GP).
* **Playbook File Ingestion**: Supports drag-and-drop or browsing to upload `.txt`, `.md`, and `.pdf` files on the fly.

## Technical Architecture & AI Engine
TogetherMind is designed for modular reliability and direct API access:
* **Semantic RAG**: Utilizes a local **Chroma DB** instance to store document segments and compute similarity matching via local embeddings.
* **Agentic ReAct Loop**: Operates on a custom agentic loop built directly on **Google Gemini 3.5 Flash** (via OpenRouter). It parses function-calling tool specifications (`search_knowledge_base`, `escalate_to_human_partner`) to dynamically update query status or trigger General Partner alerts.

## Running the Application

### 1. Configure API Credentials
Duplicate `.env.example` to `.env` if not already present. Provide your OpenRouter API Key:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### 2. Set Up Virtual Environment & Run
Run from this directory:
```bash
# Create and activate environment
python -m venv venv
.\\venv\\Scripts\\Activate.ps1   # Windows PowerShell
# source venv/bin/activate        # macOS/Linux

# Install packages
pip install -r requirements.txt

# Run server
python main.py
```

The application will launch on **`http://localhost:8001`**.
