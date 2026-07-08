# Together Fund: Operating Partner Intelligence Suite

This document outlines the core strategy of Together Fund, details six product ideas designed to scale operator expertise, justifies the prioritized suite (TogetherMind, Signal, and Corridor Compass), and highlights operational risks.

---

## Understanding Together Fund

Together Fund is an early-stage venture fund founded in 2021 by experienced startup builders **Girish Mathrubootham** (founder of Freshworks) and **Manav Garg** (founder of Eka Software). 

Unlike traditional VC firms, Together Fund provides hands-on operational support. The partners actively assist founders with:
* Hiring key team members
* Sales strategy
* Go-to-market (GTM) execution

They invest **$1M to $10M** in Seed and Series A AI-native startups, with a core focus on helping India-built companies scale in international markets (the **global expansion corridor**).

### The Primary Constraint
Because high-touch help is resource-intensive, partners stay highly selective about their investments. Their most limited resource is **time**. The tools below are designed to scale their expertise so they can help more founders without running out of hours in the day.

---

## Prioritized Product Suite

These three tools are prioritized because they directly protect partner time and help India-built startups succeed globally.

### 1. TogetherMind: Operator Knowledge Assistant
* **What it does:** Allows founders and team members to ask strategic business questions (e.g., *"How do I hire my first sales manager in the US?"*). It retrieves relevant answers from past strategy memos, playbooks, and blog posts, and links to the source documents.
* **How it scales partners:** Instead of partners repeating the same advice in meetings, their accumulated knowledge becomes searchable and reusable 24/7.
* **How it works:** Ingests strategy documents and essays into a semantic vector database (ChromaDB). When a user queries the system, a retrieval agent finds the top matches, generates an answer with citations, and automatically forwards the question to a real human partner if the question requires subjective VC judgment.

### 2. Signal: Portfolio Health Triage
* **What it does:** Reviews weekly progress updates submitted by founders, extracts key metrics and sentiment, and ranks the portfolio in a dashboard so partners know which companies need urgent attention.
* **How it scales partners:** Ensures partners spend their limited time proactively supporting struggling companies rather than reacting to the loudest founders.
* **How it works:** Automatically parses weekly text updates using an AI analyst to extract key signals (revenue trend, hiring status, blockers, sentiment, and red flags). It compares these metrics against the company's historical baseline to spot negative trends (e.g., sudden drop in sentiment, persistent flat revenue) and scores urgency from 0 to 10. Also allows onboarding new startups simply by pasting their website link.

### 3. Corridor Compass: Global Readiness Auditor
* **What it does:** Audits a startup’s landing page copy and structure to evaluate how well it communicates value to international enterprise buyers. It provides an overall readiness score and a prioritized checklist of concrete fixes.
* **How it scales partners:** Gives founders instant, repeatable feedback on their GTM messaging, pricing, and trust signals before they present to a partner or a global client.
* **How it works:** Clean text and structure are parsed from the startup's website. An optional **Target Country** field lets users run audits specific to local markets (e.g., UK, Germany, Japan). Three specialized AI critics audit the content:
  * **Messaging Critic:** Checks for clarity, jargon-free value propositions, and pain-first copy.
  * **Pricing Critic:** Evaluates price transparency, self-serve models, and packaging metrics. If pricing tables are missing on the landing page, it runs a programmatic DuckDuckGo search query to find external subscription plans, ensuring startups aren't penalized unfairly.
  * **Trust Critic:** Checks for security signals (SOC2, GDPR), customer proof, and legal links.
  An editor agent synthesizes the critic reports into a single readiness scorecard and actionable task list.

### 4. Dealflow Triage Copilot
* **What it does:** Automatically reads incoming pitch decks and startup profiles to filter and sort them based on Together Fund’s investment criteria.
* **Problem it solves:** Partners spend hours doing a "first pass" read on pitches that could easily be pre-screened.
* **How to build it:** Use an AI parser to extract sector, stage, team background, and target market from pitch PDFs, then compare them against a model of the fund's ideal profile to calculate a fit score.

### 5. Warm-Intro Talent Matcher
* **What it does:** Connects open jobs at portfolio companies with candidate profiles in the fund's network.
* **Problem it solves:** Portfolio hiring is currently manual and relies on the memory of individual partners.
* **How to build it:** Maintain structured lists of roles and candidates. Use semantic matching so search terms align by meaning (e.g., matching a "Growth Marketer" role with a candidate who has "Demand Generation" experience).

### 6. LP Reporting Autopilot
* **What it does:** Pulls key performance indicators from portfolio companies and drafts the periodic updates sent to Limited Partners (LPs).
* **Problem it solves:** Preparing fund reports manually is slow, administrative work.
* **How to build it:** Consolidate portfolio metrics in a database and use generative AI to draft short, professional summaries for each company. Partners review and edit the drafts before distribution.

---

## Tradeoffs and Risks

| Tool | Key Limitation / Risk | Mitigation Strategy |
| :--- | :--- | :--- |
| **TogetherMind** | The AI is only as smart as the playbooks uploaded. If data is outdated or missing, answers will be low quality. | Include a clear escalation protocol to route complex or judgment-heavy questions to human partners. |
| **Signal** | Relies on self-reported founder data. Founders might hesitate to report bad news early, leading to missed warnings. | Cross-reference updates with objective metrics (like Stripe integrations or hiring pipelines) over time. |
| **Corridor Compass** | GTM copy is subjective, and static rules cannot replace live user testing. | Treat the audit as a fast, directional benchmark to catch obvious gaps rather than a final verdict. |
| **Across All Tools** | Managing highly confidential startup metrics, partner notes, and emails requires strict security controls. | Keep access scoped by user role, run tools locally/securely, and implement precise data permissions. |
