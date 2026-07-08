# Corridor Compass — US Readiness Auditor

Corridor Compass is an automated GTM dilgence critic designed to prepare India-built software startups for US market entry. It scrapes any landing page, reviews it against benchmark US SaaS layouts, and generates developer-friendly fix ticket checklists.

## Key Features
* **Multi-Agent GTM Audit**: Coordinates three AI critics checking distinct business signals:
  * **Messaging Critic**: Pain-first GTM focus, jargon reduction, direct headline clarity.
  * **Pricing Critic**: Transparent self-serve tiers, pricing tables, value packaging.
  * **Trust Critic**: Security badges (SOC2, GDPR), customer logos, social proof, legal links.
* **Conflict Resolution**: An editor agent reviews critics' ratings, resolves score contradictions, and writes an editorial narrative.
* **Prioritized Checklist**: Recommends action items sorted by business impact and development effort.

## Technical Architecture & AI Engine
Corridor Compass is built on a custom collaborative multi-agent critic framework:
* **Multi-Agent Critiquing**: Executes three parallel auditor agents (Messaging, Pricing, and Trust Critics) built directly on **Google Gemini 3.5 Flash** (via OpenRouter) to evaluate scraped landing page content against industry guidelines.
* **Conflict Resolution & Aggregation**: An Editor Reconciler agent reviews critic score discrepancies, synthesizes an editorial summary, and compiles a prioritized list of fix checklist tickets.

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

The application will launch on **`http://localhost:8003`**.
