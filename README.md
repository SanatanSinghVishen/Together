# Together Horizon — Unified Venture Intelligence Command Center

Together Horizon acts as an automated **Operating Partner** that aggregates institutional fund playbooks, triages weekly portfolio logs, and audits landing pages for global market expansion.

## 🌟 The Story of Together Horizon

### Why it is needed
Building a startup is hard, but managing a growing portfolio of them is equally challenging. Venture Capital (VC) partners want to provide hands-on help to every single founder they invest in, but there are only 24 hours in a day. 
* Founders need instant, expert guidance on Go-To-Market (GTM) strategy, sales hiring, and pricing.
* Investors get bombarded with unstructured weekly updates. Critically struggling startups get lost in the noise because partners are reading long emails and Slack updates.
* Indian SaaS startups struggle to sell to global enterprise buyers because their landing pages lack local trust triggers, transparent pricing structures, and clear value messaging.

### Who it benefits
* **Venture Partners (Investors)**: They get a prioritized triage board highlighting exactly which startup needs attention, historical update logs, and an automated diligence tool to onboard and audit new startups.
* **Startup Founders**: They get 24/7 access to the fund's strategic guides (via a simple drag-and-drop playbook uploader and Q&A search console) and a clear, prioritized checklist of fix tickets to make their landing page ready for global buyers.

---

## 📂 Project Structure & Independent Portals

Together Horizon has been split into three dedicated applications, allowing founders and partners to access each tool independently:

1. **TogetherMind** (Port `8001`): Q&A and Knowledge playbook search.
2. **Signal** (Port `8002`): Weekly portfolio health triage dashboard.
3. **Corridor Compass** (Port `8003`): Global readiness and landing page audit workstation.

---

## 🛠️ Step-by-Step Installation & Setup

### 1. Set Up Virtual Environment
```bash
# Create the virtual environment
python -m venv venv

# Activate on Windows (PowerShell):
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Keys
1. Create a `.env` file in the project root folder.
2. Configure your OpenRouter credentials:
   ```env
   OPENROUTER_API_KEY=your_openrouter_api_key
   ```

### 4. Running the Services
Since the services run independently, start each backend in its own shell window:

```bash
# Run TogetherMind (Port 8001)
cd code/togethermind
python main.py

# Run Signal (Port 8002)
cd code/signal
python main.py

# Run Corridor Compass (Port 8003)
cd code/corridor_compass
python main.py
```

---

## 🛰️ Port & Workspace Reference

* **TogetherMind**: Q&A playbooks search console at [http://localhost:8001](http://localhost:8001).
* **Signal**: Portfolio triage alerts board at [http://localhost:8002](http://localhost:8002).
* **Corridor Compass**: Global readiness audit workstation at [http://localhost:8003](http://localhost:8003). Features target country diligence routing and automated DuckDuckGo pricing searches.
