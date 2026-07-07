import os
import json
import logging
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from shared.llm_client import TogetherLLMClient
from shared.models import AuditResponse, ActionItem, ReasoningStep, CriticAssessment
from shared.config import DATASETS_DIR

logger = logging.getLogger("AuditorOrchestrator")

# =====================================================================
# FETCHER COMPONENT
# =====================================================================
def fetch_and_clean_page(url: str) -> Dict[str, Any]:
    """
    Fetches a web page URL and extracts clean structured text details
    (headings, paragraphs, lists, pricing markers) for the audit agent.
    """
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
    
    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()

    # Extract headings
    headings = []
    for h in soup.find_all(["h1", "h2", "h3"]):
        text = h.get_text().strip()
        if len(text) > 4:
            headings.append(f"{h.name}: {text}")
            
    # Extract copy paragraphs
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text().strip()
        if len(text) > 20:
            paragraphs.append(text)

    # Extract list items (often features)
    lists = []
    for li in soup.find_all("li"):
        text = li.get_text().strip()
        if len(text) > 10:
            lists.append(text)

    # Reconstruct readable page text
    title = soup.title.string.strip() if soup.title else "Startup Landing Page"
    raw_text = soup.get_text()
    
    # Try to scan for specific pricing or security strings in raw text
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

# =====================================================================
# CRITICS COMPONENTS
# =====================================================================
MESSAGING_PROMPT = """
You are the GTM Messaging Critic Agent.
Your job is to audit a startup's landing page copy and evaluate if it matches the expectations of US enterprise buyers.

US buyers expect:
1. Pain-first value proposition: Clear description of the exact pain solved. Avoid abstract generic tech jargon.
2. Direct clarity: The headline must communicate exactly what the product is within 3 seconds.
3. Cultural fit: Tone must be professional, confident, and direct. Avoid service-oriented phrasing or overly passive descriptions.

Analyze the parsed website copy, compare it against modern US SaaS messaging patterns, and output a structured assessment matching the CriticAssessment schema:
- `dimension`: Must be 'messaging'.
- `score`: Float score out of 10.0.
- `findings`: Key strengths or mismatches.
- `recommendations`: Actionable improvements.
- `severity`: Triage severity ('high', 'medium', 'low').
"""

class MessagingCritic:
    def __init__(self, client: TogetherLLMClient):
        self.client = client

    def audit(self, page_data: Dict[str, Any], reference_corpus: List[Dict[str, Any]], reasoning_trace: List[ReasoningStep], on_step: Any = None) -> CriticAssessment:
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="MessagingCritic",
            action="Auditing messaging tone",
            thought="Reviewing headings and copy structure against US benchmark messaging profiles.",
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
            f"=== US ENTERPRISE BENCHMARK REFERENCES ===\n"
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

US buyers expect:
1. Pricing Transparency: A dedicated, public pricing page. Clear tiers (e.g., Free/Pro/Enterprise) rather than hiding behind 'Contact Sales' for basic tiers.
2. Value Metrics: Easy-to-understand seat, usage, or capacity pricing.
3. Packaging norms: Tiers mapping clearly to buyer stages.

Analyze the parsed website structure and look for pricing clues. Output a structured assessment matching the CriticAssessment schema:
- `dimension`: Must be 'pricing'.
- `score`: Float score out of 10.0.
- `findings`: Gaps like missing pricing pages, lack of self-serve, or complex rules.
- `recommendations`: Actionable improvements.
- `severity`: Triage severity ('high', 'medium', 'low').
"""

class PricingCritic:
    def __init__(self, client: TogetherLLMClient):
        self.client = client

    def audit(self, page_data: Dict[str, Any], reference_corpus: List[Dict[str, Any]], reasoning_trace: List[ReasoningStep], on_step: Any = None) -> CriticAssessment:
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="PricingCritic",
            action="Auditing pricing models",
            thought="Inspecting page copy for pricing tables, capacity tiers, and packaging metrics.",
            details={"has_pricing_signals": page_data.get("meta_signals", {}).get("has_pricing_page", False)}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        
        prompt = (
            f"Target Startup Website Title: {page_data.get('title')}\n"
            f"Pricing signals: {json.dumps(page_data.get('meta_signals', {}))}\n"
            f"--- Parse Copy Preview ---\n"
            + "\n".join(page_data.get("paragraphs", [])[:15]) + "\n"
            f"--- Feature Lists ---\n"
            + "\n".join(page_data.get("lists", [])[:20]) + "\n\n"
            f"=== US ENTERPRISE BENCHMARK REFERENCES ===\n"
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

US buyers expect:
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

    def audit(self, page_data: Dict[str, Any], reference_corpus: List[Dict[str, Any]], reasoning_trace: List[ReasoningStep], on_step: Any = None) -> CriticAssessment:
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="TrustSignalsCritic",
            action="Auditing trust signals",
            thought="Reviewing the copy for security seals, logo grids, legal references, and SOC2 mentions.",
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
            f"=== US ENTERPRISE BENCHMARK REFERENCES ===\n"
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

# =====================================================================
# ORCHESTRATOR COMPONENT
# =====================================================================
SYNTHESIS_INSTRUCTION = """
You are the Lead GTM Editor Agent for the Together Fund US Corridor Auditor.
Your job is to read individual reports from 3 expert critics (messaging, pricing, trust signals), resolve any conflicts or disagreements in their ratings, and construct a unified audit scorecard.

Your output must precisely match the AuditResponse schema.
- `overall_score`: Float between 0.0 and 100.0 (average of critics scores multiplied by 10).
- `readiness_tier`: Choose from:
  - 'US-Ready' (score >= 85)
  - 'Almost There' (70 <= score < 85)
  - 'Needs Work' (50 <= score < 70)
  - 'Not Ready' (score < 50)
- `synthesis`: Editorial narrative summarizing the startup's readiness and core challenges.
- `disagreements`: List any instances where critics differed (e.g. one critic scoring pricing as high due to transparency, but another flagging enterprise pricing opaque rules) and how you resolved the conflict.
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

    def run_audit(self, url: str = None, fallback_text: str = None, on_step: Any = None) -> AuditResponse:
        reasoning_trace = []
        
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="GTMOrchestrator",
            action="Starting GTM audit run",
            thought="Determining input format (live URL or raw text copy). Preparing scraping pipeline.",
            details={"url": url, "has_fallback": fallback_text is not None}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        print(f"\n[Reasoning Trace - Step {step_num}] GTMOrchestrator -> Action: Starting GTM audit run")

        # 1. Fetch website text
        if url:
            try:
                page_data = fetch_and_clean_page(url)
                step_num = len(reasoning_trace) + 1
                step = ReasoningStep(
                    step_num=step_num,
                    agent_name="GTMOrchestrator",
                    action="Web page scraping complete",
                    thought="Clean HTML parsed, metadata tags extracted. Triggering critics in parallel.",
                    details={"title": page_data["title"]}
                )
                reasoning_trace.append(step)
                if on_step:
                    on_step(step)
            except Exception as e:
                logger.warning(f"URL fetch failed, falling back to text copy: {e}")
                if fallback_text:
                    page_data = self._parse_raw_text(fallback_text, url or "Pasted Document")
                else:
                    raise e
        elif fallback_text:
            page_data = self._parse_raw_text(fallback_text, "Pasted Document")
        else:
            raise ValueError("Must provide either a website URL or fallback copy text to audit.")

        # 2. Run Critics
        m_trace = []
        m_assessment = self.messaging_critic.audit(page_data, self.reference_corpus, m_trace, on_step)
        
        p_trace = []
        p_assessment = self.pricing_critic.audit(page_data, self.reference_corpus, p_trace, on_step)
        
        t_trace = []
        t_assessment = self.trust_critic.audit(page_data, self.reference_corpus, t_trace, on_step)

        # 3. Consolidate and editorialize
        consolidation_prompt = (
            f"Audit Target: {page_data.get('title')}\n"
            f"URL: {page_data.get('url')}\n\n"
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
            f"   Recommendations: {json.dumps(t_assessment.recommendations)}\n"
            f"============================\n\n"
            f"Please synthesize these reviews, resolve conflicts, calculate the overall score, and write the priority actions."
        )

        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="GTMOrchestrator",
            action="Consolidating critic reviews",
            thought="Analyzing messaging, pricing, and trust score vectors. Resolving conflicts and prioritizing fix tickets.",
            details={"critics_scores": {"messaging": m_assessment.score, "pricing": p_assessment.score, "trust": t_assessment.score}}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        print(f"[Reasoning Trace - Step {step_num}] GTMOrchestrator -> Action: Consolidating critic reviews")

        audit_response = self.llm_client.generate_structured(
            prompt=consolidation_prompt,
            schema_class=AuditResponse,
            system_instruction=SYNTHESIS_INSTRUCTION,
            on_step=on_step
        )
        
        # Merge critic reasoning steps into main orchestrator trace for unified UI display
        for step in m_assessment.reasoning_trace:
            step_num = len(reasoning_trace) + 1
            step.step_num = step_num
            reasoning_trace.append(step)
            
        for step in p_assessment.reasoning_trace:
            step_num = len(reasoning_trace) + 1
            step.step_num = step_num
            reasoning_trace.append(step)
            
        for step in t_assessment.reasoning_trace:
            step_num = len(reasoning_trace) + 1
            step.step_num = step_num
            reasoning_trace.append(step)

        # Inject trace details
        audit_response.company_name = page_data.get("title").split('|')[0].strip()
        audit_response.critic_reports = {
            "messaging": m_assessment,
            "pricing": p_assessment,
            "trust_signals": t_assessment
        }
        audit_response.reasoning_trace = reasoning_trace
        
        return audit_response

    def _parse_raw_text(self, text: str, source_label: str) -> Dict[str, Any]:
        """Utility parser when text upload/fallback is used instead of active scraping"""
        text_lower = text.lower()
        has_soc2 = "soc" in text_lower or "soc2" in text_lower or "compliance" in text_lower
        has_gdpr = "gdpr" in text_lower
        has_pricing = "price" in text_lower or "pricing" in text_lower or "plan" in text_lower
        
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 5]
        
        return {
            "url": source_label,
            "title": source_label,
            "headings": lines[:10],
            "paragraphs": lines[:30],
            "lists": [],
            "meta_signals": {
                "has_soc2": has_soc2,
                "has_gdpr": has_gdpr,
                "has_pricing_page": has_pricing
            },
            "full_text_preview": text[:2000]
        }
