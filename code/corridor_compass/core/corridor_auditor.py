import os
import json
import logging
# pyrefly: ignore [missing-import]
import httpx
# pyrefly: ignore [missing-import]
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from shared.llm_client import TogetherLLMClient
from shared.models import AuditResponse, ActionItem, ReasoningStep, CriticAssessment
from shared.config import DATASETS_DIR

logger = logging.getLogger("AuditorOrchestrator")

def fetch_and_clean_page(url: str) -> Dict[str, Any]:
    logger.info(f"Auditor Fetcher -> Ingesting: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
    except Exception as e:
        logger.error(f"Error fetching page {url}: {e}")
        raise ValueError(f"Failed to fetch website copy from {url}. Check if the URL is active and accessible.")

    soup = BeautifulSoup(html, "lxml" if "lxml" in html else "html.parser")
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()

    headings = []
    for h in soup.find_all(["h1", "h2", "h3"]):
        text = h.get_text().strip()
        if len(text) > 4:
            headings.append(f"{h.name}: {text}")
            
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text().strip()
        if len(text) > 20:
            paragraphs.append(text)

    lists = []
    for li in soup.find_all("li"):
        text = li.get_text().strip()
        if len(text) > 10:
            lists.append(text)

    title = soup.title.string.strip() if soup.title else "Startup Landing Page"
    raw_text = soup.get_text()
    raw_text_lower = raw_text.lower()
    has_soc2 = "soc" in raw_text_lower or "soc2" in raw_text_lower or "compliance" in raw_text_lower
    has_gdpr = "gdpr" in raw_text_lower
    has_pricing_page = "price" in raw_text_lower or "pricing" in raw_text_lower or "plans" in raw_text_lower
    
    return {
        "url": url,
        "title": title,
        "headings": headings[:20],
        "paragraphs": paragraphs[:30],
        "lists": lists[:40],
        "meta_signals": {
            "has_soc2": has_soc2,
            "has_gdpr": has_gdpr,
            "has_pricing_page": has_pricing_page
        },
        "full_text_preview": "\n".join(headings[:10] + paragraphs[:15])[:5000]
    }

def search_ddg_pricing(company_name: str, target_country: str = None) -> str:
    logger.info(f"Auditor Search -> Triggering DuckDuckGo pricing lookup for: {company_name} in {target_country or 'Global'}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    country_suffix = f" {target_country}" if target_country else ""
    query = f"{company_name} pricing subscription plans seat cost{country_suffix}"
    url = "https://html.duckduckgo.com/html/"
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            res = client.post(url, data={"q": query}, headers=headers)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                results = []
                for a in soup.find_all("a", class_="result__snippet"):
                    results.append(a.get_text().strip())
                if results:
                    summary = "\n".join([f"- {r}" for r in results[:4]])
                    logger.info("Auditor Search -> Found pricing clues via DuckDuckGo!")
                    return summary
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
    return ""

MESSAGING_PROMPT = """
You are the GTM Messaging Critic Agent.
Your job is to audit a startup's landing page copy and evaluate if it matches the expectations of Global and International market enterprise buyers.

Global buyers expect:
1. Pain-first value proposition: Clear description of the exact pain solved. Avoid abstract generic tech jargon.
2. Direct clarity: The headline must communicate exactly what the product is within 3 seconds.
3. Cultural fit: Tone must be professional, confident, and direct. Avoid service-oriented phrasing or overly passive descriptions.

Analyze the parsed website copy, compare it against modern global SaaS messaging patterns, and output a structured assessment matching the CriticAssessment schema:
- `dimension`: Must be 'messaging'.
- `score`: Float score out of 10.0.
- `findings`: Key strengths or mismatches.
- `recommendations`: Actionable improvements.
- `severity`: Triage severity ('high', 'medium', 'low').
"""

class MessagingCritic:
    def __init__(self, client: TogetherLLMClient):
        self.client = client

    def audit(self, page_data: Dict[str, Any], reference_corpus: List[Dict[str, Any]], reasoning_trace: List[ReasoningStep], target_country: str = None, on_step: Any = None) -> CriticAssessment:
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="MessagingCritic",
            action="Auditing messaging tone",
            thought=f"Reviewing headings and copy structure against global benchmarks for target country: {target_country or 'Global'}.",
            details={"headings_count": len(page_data.get("headings", []))}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        
        prompt = (
            f"Target Startup Website Title: {page_data.get('title')}\n"
            f"Website URL: {page_data.get('url')}\n"
            f"--- Parse Copy Headings ---\n"
            + "\n".join(page_data.get("headings", [])) + "\n"
            f"--- Parse Paragraphs Preview ---\n"
            + "\n".join(page_data.get("paragraphs", [])[:10]) + "\n\n"
        )
        if target_country:
            prompt += f"=== TARGET COUNTRY FOR EXPANSION: {target_country} ===\n"
            prompt += f"Evaluate messaging clarity and cultural tone specifically matching enterprise buyers in {target_country}.\n\n"

        prompt += (
            f"=== GLOBAL ENTERPRISE BENCHMARK REFERENCES ===\n"
            + json.dumps(reference_corpus, indent=2) + "\n\n"
            f"Execute GTM messaging audit."
        )

        assessment = self.client.generate_structured(
            prompt=prompt,
            schema_class=CriticAssessment,
            system_instruction=MESSAGING_PROMPT,
            on_step=on_step
        )
        assessment.reasoning_trace = reasoning_trace
        return assessment

PRICING_PROMPT = """
You are the GTM Pricing Critic Agent.
Your job is to audit a startup's pricing structure and packaging clarity.

Global/International buyers expect:
1. Pricing Transparency: A dedicated, public pricing page. Clear tiers (e.g., Free/Pro/Enterprise) rather than hiding behind 'Contact Sales' for basic tiers.
2. Value Metrics: Easy-to-understand seat, usage, or capacity pricing.
3. Packaging norms: Tiers mapping clearly to buyer stages.

Analyze the parsed website structure and look for pricing clues. Also check the provided EXTERNAL WEB SEARCH PRICING CLUES if direct pricing copy is missing on the main page.
IMPORTANT: If direct pricing is missing on the main landing page but found in the EXTERNAL WEB SEARCH PRICING CLUES, evaluate the pricing based on those external findings rather than scoring the startup poorly.

Output a structured assessment matching the CriticAssessment schema:
- `dimension`: Must be 'pricing'.
- `score`: Float score out of 10.0.
- `findings`: Gaps like missing pricing pages, lack of self-serve, or complex rules.
- `recommendations`: Actionable improvements.
- `severity`: Triage severity ('high', 'medium', 'low').
"""

class PricingCritic:
    def __init__(self, client: TogetherLLMClient):
        self.client = client

    def audit(self, page_data: Dict[str, Any], reference_corpus: List[Dict[str, Any]], reasoning_trace: List[ReasoningStep], target_country: str = None, on_step: Any = None) -> CriticAssessment:
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="PricingCritic",
            action="Auditing pricing models",
            thought=f"Inspecting page copy and search snippets for pricing tiers in target country: {target_country or 'Global'}.",
            details={"has_pricing_signals": page_data.get("meta_signals", {}).get("has_pricing_page", False)}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        
        external_pricing = ""
        if not page_data.get("meta_signals", {}).get("has_pricing_page", False):
            company_title = page_data.get("title", "SaaS")
            if " - " in company_title:
                company_title = company_title.split(" - ")[0]
            external_pricing = search_ddg_pricing(company_title, target_country)

        prompt = (
            f"Target Startup Website Title: {page_data.get('title')}\n"
            f"Pricing signals: {json.dumps(page_data.get('meta_signals', {}))}\n"
            f"--- Parse Copy Preview ---\n"
            + "\n".join(page_data.get("paragraphs", [])[:15]) + "\n"
            f"--- Feature Lists ---\n"
            + "\n".join(page_data.get("lists", [])[:20]) + "\n\n"
        )
        if external_pricing:
            prompt += f"=== EXTERNAL WEB SEARCH PRICING CLUES ===\n{external_pricing}\n\n"
            
        if target_country:
            prompt += f"=== TARGET COUNTRY FOR EXPANSION: {target_country} ===\n"
            prompt += f"Evaluate pricing tiers, currency conversion norms, and local packing tiers specific to enterprise buyers in {target_country}.\n\n"

        prompt += (
            f"=== GLOBAL ENTERPRISE BENCHMARK REFERENCES ===\n"
            + json.dumps(reference_corpus, indent=2) + "\n\n"
            f"Execute GTM pricing and packaging audit."
        )

        assessment = self.client.generate_structured(
            prompt=prompt,
            schema_class=CriticAssessment,
            system_instruction=PRICING_PROMPT,
            on_step=on_step
        )
        assessment.reasoning_trace = reasoning_trace
        return assessment

TRUST_PROMPT = """
You are the GTM Trust Signals Critic Agent.
Your job is to audit a startup's landing page for trust markers, security compliance, and validation.

Global buyers expect:
1. Security Certifications: Explicit mentions of SOC2 Type II, ISO 27001, GDPR, HIPAA, or encryption baselines.
2. Social Proof: Customer logos, testimonial quotes, case study previews, or rating badges (G2, Gartner).
3. Legal footprint: Easily accessible links to Privacy Policy, Terms of Service, DPA, and Security guidelines.

Analyze the parsed website copy, check compliance meta signals, and output a structured assessment matching the CriticAssessment schema:
- `dimension`: Must be 'trust_signals'.
- `score`: Float score out of 10.0.
- `findings`: Gaps like missing compliance certifications, lack of recognizable client logos, or hidden legal footnotes.
- `recommendations`: Actionable improvements.
- `severity`: Triage severity ('high', 'medium', 'low').
"""

class TrustSignalsCritic:
    def __init__(self, client: TogetherLLMClient):
        self.client = client

    def audit(self, page_data: Dict[str, Any], reference_corpus: List[Dict[str, Any]], reasoning_trace: List[ReasoningStep], target_country: str = None, on_step: Any = None) -> CriticAssessment:
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="TrustSignalsCritic",
            action="Auditing trust signals",
            thought=f"Reviewing the copy for compliance seals and testimonials for target country: {target_country or 'Global'}.",
            details={"meta_signals": page_data.get("meta_signals", {})}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        
        prompt = (
            f"Target Startup Website Title: {page_data.get('title')}\n"
            f"Compliance meta signals: {json.dumps(page_data.get('meta_signals', {}))}\n"
            f"--- Paragraphs Copy ---\n"
            + "\n".join(page_data.get("paragraphs", [])[:20]) + "\n"
            f"--- List items ---\n"
            + "\n".join(page_data.get("lists", [])[:20]) + "\n\n"
        )
        if target_country:
            prompt += f"=== TARGET COUNTRY FOR EXPANSION: {target_country} ===\n"
            prompt += f"Evaluate compliance expectations (e.g. GDPR for Europe, SOC2 for US) and customer proof points relative to {target_country} buyers.\n\n"

        prompt += (
            f"=== GLOBAL ENTERPRISE BENCHMARK REFERENCES ===\n"
            + json.dumps(reference_corpus, indent=2) + "\n\n"
            f"Execute GTM trust signals audit."
        )

        assessment = self.client.generate_structured(
            prompt=prompt,
            schema_class=CriticAssessment,
            system_instruction=TRUST_PROMPT,
            on_step=on_step
        )
        assessment.reasoning_trace = reasoning_trace
        return assessment

SYNTHESIS_INSTRUCTION = """
You are the Lead GTM Editor Agent for the Together Fund Global Corridor Auditor.
Your job is to read individual reports from 3 expert critics (messaging, pricing, trust signals), resolve any conflicts or disagreements in their ratings, and construct a unified audit scorecard.

Your output must precisely match the AuditResponse schema.
- `overall_score`: Float between 0.0 and 100.0 (average of critics scores multiplied by 10).
- `readiness_tier`: Choose from:
  - 'Global-Ready' (score >= 85)
  - 'Almost There' (70 <= score < 85)
  - 'Needs Work' (50 <= score < 70)
  - 'Not Ready' (score < 50)
- `synthesis`: Editorial narrative summarizing the startup's readiness and core challenges.
- `disagreements`: List any instances where critics differed and how you resolved the conflict.
- `prioritized_actions`: Consolidated list of action items sorted by GTM impact and priority.
"""

class AuditOrchestrator:
    def __init__(self):
        self.llm_client = TogetherLLMClient()
        self.messaging_critic = MessagingCritic(self.llm_client)
        self.pricing_critic = PricingCritic(self.llm_client)
        self.trust_critic = TrustSignalsCritic(self.llm_client)
        self.reference_corpus = self._load_reference_corpus()

    def _load_reference_corpus(self) -> List[Dict[str, Any]]:
        ref_file = os.path.join(DATASETS_DIR, "reference_landing_pages.json")
        if os.path.exists(ref_file):
            try:
                with open(ref_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading reference landing pages: {e}")
        return []

    def _parse_raw_text(self, text: str, url: str) -> Dict[str, Any]:
        lines = text.split("\n")
        headings = [f"h1: {l.strip()}" for l in lines[:5] if len(l.strip()) > 3]
        paragraphs = [l.strip() for l in lines[5:20] if len(l.strip()) > 15]
        return {
            "url": url,
            "title": url,
            "headings": headings,
            "paragraphs": paragraphs,
            "lists": [],
            "meta_signals": {
                "has_soc2": "soc" in text.lower(),
                "has_gdpr": "gdpr" in text.lower(),
                "has_pricing_page": "price" in text.lower() or "plans" in text.lower()
            }
        }

    def run_audit(self, url: str = None, fallback_text: str = None, target_country: str = None, on_step: Any = None) -> AuditResponse:
        reasoning_trace = []
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="GTMOrchestrator",
            action="Starting GTM audit run",
            thought=f"Diligence target: {url or 'Pasted copy'}. Target country: {target_country or 'Global'}.",
            details={"url": url, "has_fallback": fallback_text is not None, "target_country": target_country}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)

        if url:
            try:
                page_data = fetch_and_clean_page(url)
                step_num = len(reasoning_trace) + 1
                step = ReasoningStep(
                    step_num=step_num,
                    agent_name="GTMOrchestrator",
                    action="Web page scraping complete",
                    thought="Clean HTML parsed, metadata signals extracted. Triggering audit checks.",
                    details={"title": page_data["title"]}
                )
                reasoning_trace.append(step)
                if on_step:
                    on_step(step)
            except Exception as e:
                logger.warning(f"URL fetch failed, falling back to text copy: {e}")
                if fallback_text:
                    page_data = self._parse_raw_text(fallback_text, url)
                else:
                    raise e
        elif fallback_text:
            page_data = self._parse_raw_text(fallback_text, "Pasted Document")
        else:
            raise ValueError("Must provide either a website URL or fallback copy text to audit.")

        m_trace = []
        m_assessment = self.messaging_critic.audit(page_data, self.reference_corpus, m_trace, target_country, on_step)
        
        p_trace = []
        p_assessment = self.pricing_critic.audit(page_data, self.reference_corpus, p_trace, target_country, on_step)
        
        t_trace = []
        t_assessment = self.trust_critic.audit(page_data, self.reference_corpus, t_trace, target_country, on_step)

        consolidation_prompt = (
            f"Audit Target: {page_data.get('title')}\n"
            f"URL: {page_data.get('url')}\n"
            f"Target Country: {target_country or 'Global'}\n\n"
            f"=== CRITICS ASSESSMENTS ===\n"
            f"1. MESSAGING CRITIC:\n"
            f"   Score: {m_assessment.score}/10.0\n"
            f"   Findings: {json.dumps(m_assessment.findings)}\n"
            f"   Recommendations: {json.dumps(m_assessment.recommendations)}\n\n"
            f"2. PRICING CRITIC:\n"
            f"   Score: {p_assessment.score}/10.0\n"
            f"   Findings: {json.dumps(p_assessment.findings)}\n"
            f"   Recommendations: {json.dumps(p_assessment.recommendations)}\n\n"
            f"3. TRUST SIGNALS CRITIC:\n"
            f"   Score: {t_assessment.score}/10.0\n"
            f"   Findings: {json.dumps(t_assessment.findings)}\n"
            f"   Recommendations: {json.dumps(t_assessment.recommendations)}\n\n"
            f"Resolve critic scores, average them (x10) to obtain overall_score out of 100, "
            f"select correct Global-Ready tier, and synthesis feedback recommendations."
        )

        response = self.llm_client.generate_structured(
            prompt=consolidation_prompt,
            schema_class=AuditResponse,
            system_instruction=SYNTHESIS_INSTRUCTION,
            on_step=on_step
        )
        
        # Link critic reports
        response.critic_reports = {
            "messaging": m_assessment,
            "pricing": p_assessment,
            "trust_signals": t_assessment
        }
        
        # Include orchestrator trace
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="GTMOrchestrator",
            action="Consolidating critic reviews",
            thought="Reviews consolidated, score synthesized, prioritized checklist generated.",
            details={"overall_score": response.overall_score, "tier": response.readiness_tier}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
            
        response.reasoning_trace = reasoning_trace
        return response
