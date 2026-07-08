# Submission Overview: Together Horizon

This document provides a summary of the unified venture partner intelligence suite, details the configuration settings, and outlines how the codebase is structured and run.

---

## 🛠️ One-Line Summary per Tool

1. **TogetherMind** (`code/togethermind`): An AI operating partner assistant that searches fund playbooks and essays using semantic RAG to provide cited scaling advice, with automatic General Partner escalation for subjective queries.
2. **Signal** (`code/signal`): A portfolio health triage dashboard that extracts founder metrics/sentiment and compares them against historical baselines to rank startups by urgency.
3. **Corridor Compass** (`code/corridor_compass`): An automated landing page auditor that coordinates three specialized AI critics (Messaging, Pricing, Trust Signals) to generate GTM readiness scores and fix tickets.

---

## 🏗️ Architecture & Technology Stack

Each tool in Together Horizon is engineered using **custom agentic loops and structured pipelines** built directly on top of the **Google Gemini 3.5 Flash** model (via OpenRouter):

1. **TogetherMind (RAG & ReAct Agent)**:
   - **Architecture**: **Semantic RAG (Retrieval-Augmented Generation)** + **Agentic ReAct (Reasoning and Action) Loop**.
   - **Framework Details**: Built custom using the raw OpenRouter completions API and native tool schemas.
   - **Vectordb**: Chroma DB stores and indexes document segments using local embeddings.
   - **Logic**: A custom execution loop intercepts and parses tool calls (`search_knowledge_base`, `escalate_to_human_partner`), updating the reasoning trace dynamically before resolving the final response.

2. **Signal (Structured Analytics Pipeline)**:
   - **Architecture**: **Structured Data Extraction & Deviation Mapping Pipeline**.
   - **Framework Details**: Custom telemetry pipeline communicating with an SQLite database.
   - **Logic**: Founder updates are ingested, structured signals (sentiment, finance metrics, burners) are extracted using structured JSON generation, and a historical checker calculates metric drops/burnout rates over past weeks to build the Triage priority score.

3. **Corridor Compass (Multi-Agent Audit & Reconciliation)**:
   - **Architecture**: **Collaborative Multi-Agent Critic Framework**.
   - **Framework Details**: Custom multi-agent hierarchy.
   - **Logic**: Three parallel critic agents (Messaging Critic, Pricing Critic, Trust Signals Critic) run structural audits on the scraped layout copy. A central Editor Reconciler agent merges their ratings, resolves contradictions, writes a narrative, and generates a prioritized fix list.

---

## 🔑 Environment Variables Needed

Create a `.env` file in the root of the project, or in each tool's subfolder, with the following credentials:

```env
# Required API Key for LLM execution via OpenRouter
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional: Shared Database Space Configuration (Default values shown)
SQLITE_DB_PATH=../../portfolio.db
CHROMA_DB_DIR=../../chroma_db
```

---

## 📂 Codebase Structure & Segregation

To satisfy the submission requirement of **one subfolder per tool**, the monolithic project has been segregated under the `code/` folder:

```
Together/
├── code/
│   ├── togethermind/      # Tool 1: Operator Knowledge Assistant (Port 8001)
│   ├── signal/            # Tool 2: Portfolio Health Triage (Port 8002)
│   └── corridor_compass/  # Tool 3: US Readiness Auditor (Port 8003)
├── portfolio.db           # Shared SQLite Database
├── chroma_db/             # Shared ChromaDB Vector Store
└── SUBMISSION.md          # Submission log details
```

### Shared Data Space
As permitted by the guidelines, data is shared between all three tools through a unified space:
* Each independent tool's `.env` is configured with `SQLITE_DB_PATH=../../portfolio.db` and `CHROMA_DB_DIR=../../chroma_db`.
* This allows **Signal** (triage) to access portfolio information, **TogetherMind** (playbooks) to query vector stores, and **Corridor Compass** (scraper metadata) to operate from a single, consistent source of truth.

---

## 🌐 Live Deployed Application Links

You can access and test the live, fully functional cloud portals here:
* **TogetherMind**: [https://togethermind.onrender.com](https://togethermind.onrender.com)
* **Signal**: [https://signal-5u0b.onrender.com](https://signal-5u0b.onrender.com)
* **Corridor Compass**: [https://compass-rsbi.onrender.com](https://compass-rsbi.onrender.com)

## 🚀 How to Run the Tools

Each subfolder is a fully self-contained application with its own python backend (`main.py`) and dedicated UI client (`static/`).

### Quick Start:

1. **Navigate to the tool's directory**:
   ```bash
   cd code/togethermind    # Or code/signal, or code/corridor_compass
   ```

2. **Set up the virtual environment & install dependencies**:
   ```bash
   python -m venv venv
   .\\venv\\Scripts\\Activate.ps1   # Windows PowerShell
   # source venv/bin/activate        # macOS/Linux

   pip install -r requirements.txt
   ```

3. **Provide API Key in `.env`**:
   Ensure `.env` contains your active `OPENROUTER_API_KEY`.

4. **Launch the backend server**:
   ```bash
   python main.py
   ```

5. **Access the application**:
   * **TogetherMind**: `http://localhost:8001`
   * **Signal**: `http://localhost:8002`
   * **Corridor Compass**: `http://localhost:8003`

---

