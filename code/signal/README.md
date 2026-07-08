# Signal — Portfolio Health Triage

Signal is a weekly health triage board built for venture capital partners. It monitors startups by analyzing weekly updates sent by founders, extracting key performance metrics, and prioritizing partners' attention to companies that need immediate assistance.

## Key Features
* **AI Signal Extraction**: Reads unstructured founder updates and extracts ARR trends, hiring status, blockers, red flags, and founder sentiment.
* **Longitudinal Deviation Engine**: Automatically scans weeks of history for negative anomalies (sentiment dips, persistent revenue decline, founder burnout signs).
* **Urgency Scoring**: Ranks startups from 0.0 (stable/growing) to 10.0 (crisis) to construct a priority attention dashboard.
* **Acquisition URL Diligence / Onboarding**: Supports pasting a new startup's website URL to auto-scrape landing copy and generate an initial profile using LLM diligence.

## Technical Architecture & AI Engine
Signal is built using a custom multi-stage structured extraction pipeline:
* **Structured Data Extraction**: Founder reports are parsed using structured JSON schemas passed to **Google Gemini 3.5 Flash** (via OpenRouter), obtaining clean sentiment and numerical metrics.
* **Telemetry & History Tracking**: Stores historical updates in an **SQLite** database. A custom Python engine scans past logs, calculates standard deviations for ARR, sentiment, and blockers, and computes the final Urgency Score.

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

The application will launch on **`http://localhost:8002`**.
