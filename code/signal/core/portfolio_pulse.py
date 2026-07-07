import logging
import json
import sqlite3
from typing import List, Dict, Any
from shared.llm_client import TogetherLLMClient
from shared.models import CompanyTriage, PulseBriefingResponse, ExtractedSignals, ReasoningStep
from database.db_manager import PulseMemory

logger = logging.getLogger("PulseAgent")

SIGNAL_EXTRACTION_INSTRUCTION = """
You are an expert venture capital analyst assistant.
Your job is to read weekly founder updates and extract core operational signals.

Structure your response PRECISELY to match the ExtractedSignals schema:
1. `revenue_trend`: Must be one of: 'up', 'flat', 'down', 'not_mentioned'.
2. `revenue_detail`: Any revenue figures, MRR, ARR, growth percentages mentioned, or 'Not mentioned' if none.
3. `hiring_status`: Key roles hired or active job openings.
4. `sentiment`: Numeric float representing the emotional sentiment of the founder (-1.0 for highly stressed/worried to 1.0 for highly optimistic/excited).
5. `blockers`: List of active business, product, or organizational barriers (e.g. ['Groq latency issues', 'Bangalore developer shortage']).
6. `explicit_asks`: Specific tasks, intros, or guidance the founder asks the firm to help with.
7. `red_flags`: Serious warnings (e.g., negative ARR growth, key team attrition, pilot cancellations, bank runway risks).
"""

def extract_signals_from_text(update_text: str, client: TogetherLLMClient, reasoning_trace: List[ReasoningStep], company_name: str) -> ExtractedSignals:
    """Uses LLM to parse and extract structured signals from update text"""
    prompt = (
        f"Update text to parse:\n"
        f"\"\"\"\n{update_text}\n\"\"\"\n\n"
        f"Extract all relevant signals using the ExtractedSignals schema."
    )
    
    step_num = len(reasoning_trace) + 1
    reasoning_trace.append(ReasoningStep(
        step_num=step_num,
        agent_name="SignalExtractor",
        action=f"Extracting signals for {company_name}",
        thought="Parsing the raw update text to extract revenue trends, blockers, and founder sentiment.",
        details={"text_length": len(update_text)}
    ))
    
    signals = client.generate_structured(
        prompt=prompt,
        schema_class=ExtractedSignals,
        system_instruction=SIGNAL_EXTRACTION_INSTRUCTION
    )
    return signals

def detect_longitudinal_deviations(current: ExtractedSignals, history: List[Dict[str, Any]]) -> List[str]:
    """Compares current signals against history to find trends or anomalies"""
    deviations = []
    if not history:
        return deviations

    history_sorted = sorted(history, key=lambda x: x["week"])
    
    # 1. Churn / Decline checking
    if current.revenue_trend == "down":
        past_trends = [h.get("revenue_trend") for h in history_sorted[-2:]]
        if "up" in past_trends or "flat" in past_trends:
            deviations.append("First time experiencing negative revenue trend after a period of stability/growth.")
            
        consecutive_decline = 1
        for h in reversed(history_sorted):
            if h.get("revenue_trend") == "down":
                consecutive_decline += 1
            else:
                break
        if consecutive_decline >= 2:
            deviations.append(f"Revenue trend is declining for {consecutive_decline} consecutive weeks.")

    # 2. Burnout / Team Risk checking
    current_blockers_str = " ".join(current.blockers).lower()
    current_flags_str = " ".join(current.red_flags).lower()
    
    if "burn" in current_blockers_str or "stress" in current_blockers_str or "quit" in current_flags_str or "attrition" in current_flags_str:
        had_burnout_before = False
        for h in history_sorted[-3:]:
            past_blockers = " ".join(h.get("blockers", [])).lower()
            past_flags = " ".join(h.get("red_flags", [])).lower()
            if "burn" in past_blockers or "stress" in past_blockers or "quit" in past_flags:
                had_burnout_before = True
                
        if had_burnout_before:
            deviations.append("Repeated mentions of team burnout or talent attrition.")
        else:
            deviations.append("New team burnout/attrition warning detected.")

    # 3. Sentiment dip
    past_sentiments = [h.get("sentiment", 0.0) for h in history_sorted[-3:]]
    if past_sentiments:
        avg_past_sentiment = sum(past_sentiments) / len(past_sentiments)
        if current.sentiment < avg_past_sentiment - 0.4:
            deviations.append(f"Significant drop in founder sentiment ({current.sentiment:.2f} vs past average of {avg_past_sentiment:.2f}).")

    return deviations


# Lazy loaded db client
_memory_db = None

def get_db():
    global _memory_db
    if _memory_db is None:
        _memory_db = PulseMemory()
    return _memory_db

def lookup_company_history(company_id: str) -> str:
    """
    Retrieves the complete historical operational profile and extracted weekly signals
    for a specific portfolio company.
    Use this tool when a company update shows ambiguous signals, or you need to inspect 
    whether a red flag (like team stress or revenue decline) has occurred in past weeks.
    
    Args:
        company_id: The unique identifier of the company (e.g. 'spendflo', 'metaforms').
        
    Returns:
        A JSON string containing the company's baseline profile, investment thesis,
        and chronological weekly signals history.
    """
    db = get_db()
    profile = db.get_company(company_id)
    history = db.get_company_signals_history(company_id, max_weeks=6)
    
    result = {
        "company_profile": profile,
        "historical_signals": history
    }
    return json.dumps(result, indent=2)

def check_thesis_fit(company_id: str) -> str:
    """
    Retrieves the original investment thesis and initial metrics recorded at funding
    for a portfolio company.
    Use this tool to evaluate if current operational trends (such as pivot plans, flat growth,
    or key hiring bottlenecks) represent a structural deviation from why the firm backed them.
    
    Args:
        company_id: The unique identifier of the company.
        
    Returns:
        A JSON string containing the original investment thesis and key metrics at investment.
    """
    db = get_db()
    profile = db.get_company(company_id)
    if profile:
        result = {
            "name": profile.get("name"),
            "sector": profile.get("sector"),
            "stage": profile.get("stage"),
            "investment_thesis": profile.get("investment_thesis"),
            "key_metrics_at_investment": profile.get("key_metrics")
        }
        return json.dumps(result, indent=2)
    return json.dumps({"error": f"Company ID {company_id} not found."}, indent=2)


TRIAGE_INSTRUCTION = """
You are the Together Fund Portfolio Pulse Triage Agent.
Your job is to consolidate weekly portfolio updates and evaluate which companies require urgent partner support.

You have access to two tools to pull historical context if a weekly update has ambiguous/warning signals:
1. `lookup_company_history`: Inspects the company's past weekly updates and extracted signals.
2. `check_thesis_fit`: Inspects the original investment thesis and metrics at investment.

Evaluate each company's update, and output a detailed analysis matching the CompanyTriage schema:
- `urgency_score`: Float between 0.0 (perfectly stable, growing, no asks) to 10.0 (business shutdown, key founder attrition, sudden major client loss).
- `urgency_label`: One of: 'CRITICAL' (score >= 7.0), 'WARNING' (4.0 <= score < 7.0), 'STABLE' (score < 4.0).
- `reason`: Explanation of the score.
- `suggested_action`: Action item for the partner (e.g. 'Call founder immediately to resolve Epic integration blockers').
"""

CONSOLIDATION_INSTRUCTION = """
You are the Portfolio Pulse briefing editor. 
Your job is to read individual company triage reports, rank them by urgency score, and write a high-level executive summary for the partner briefing.

Output your response precisely matching the PulseBriefingResponse schema.
Rank the companies in descending order of urgency score.
"""

class PortfolioPulseAgent:
    def __init__(self):
        self.llm_client = TogetherLLMClient()
        self.db = get_db()

    def triage_company(
        self,
        company_id: str,
        update: Dict[str, Any],
        reasoning_trace: List[ReasoningStep] = None,
        on_step: Any = None
    ) -> CompanyTriage:
        if reasoning_trace is None:
            reasoning_trace = []
            
        c_name = update["company_name"]
        update_text = update["update_text"]
        week = update["week"]
        date = update["date"]
        
        # 1. Extract signals using LLM
        signals = extract_signals_from_text(update_text, self.llm_client, reasoning_trace, c_name)
        
        # Save signals to SQLite DB
        self.db.save_signals(company_id, week, date, signals.model_dump())
        
        # 2. Get past history for deviations
        history = self.db.get_company_signals_history(company_id, max_weeks=6)
        past_history = [h for h in history if h["week"] < week]
        deviations = detect_longitudinal_deviations(signals, past_history)
        
        # 3. Agentic Evaluation with history tools
        agent_instruction = (
            f"Triage evaluation for company: {c_name}\n"
            f"Sector: {update.get('sector', 'SaaS')}\n"
            f"Weekly Update text: {update_text}\n"
            f"Extracted Signals: {signals.model_dump_json()}\n"
            f"Detected Deviations from history: {json.dumps(deviations)}\n\n"
            f"Please run history lookups if the signals are alarming, then output your final triage evaluation."
        )
        
        tools = [lookup_company_history, check_thesis_fit]
        
        triage_raw, reasoning_trace = self.llm_client.call_with_tools(
            prompt=agent_instruction,
            tools=tools,
            system_instruction=TRIAGE_INSTRUCTION,
            reasoning_trace=reasoning_trace,
            agent_name=f"TriageAgent-{c_name}",
            on_step=on_step
        )
        
        # 4. Format structured output for this company
        structure_prompt = (
            f"Convert the following triage assessment for {c_name} into a structured CompanyTriage JSON object.\n\n"
            f"=== TRIAGE ASSESSMENT ===\n"
            f"{triage_raw}\n"
            f"=========================\n\n"
            f"Signals context: {signals.model_dump_json()}\n"
            f"Deviations context: {json.dumps(deviations)}"
        )
        
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name=f"TriageAgent-{c_name}",
            action="Structuring company triage",
            thought="Converting text triage output into structured CompanyTriage model.",
            details={}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        
        structured_triage = self.llm_client.generate_structured(
            prompt=structure_prompt,
            schema_class=CompanyTriage,
            system_instruction="You are a strict JSON formatter. Parse the triage assessment precisely.",
            on_step=on_step
        )
        
        # Inject calculations back
        structured_triage.company_id = company_id
        structured_triage.company_name = c_name
        structured_triage.signals = signals
        structured_triage.deviations = deviations
        structured_triage.reasoning_trace = reasoning_trace
        
        return structured_triage

    def generate_weekly_briefing(self, week_num: int, on_step: Any = None) -> PulseBriefingResponse:
        reasoning_trace = []
        
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="PortfolioPulseOrchestrator",
            action=f"Starting briefing generation for Week {week_num}",
            thought="Fetching all updates for this week and evaluating triage per company in parallel.",
            details={"week": week_num}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        print(f"\n[Reasoning Trace - Step {step_num}] PortfolioPulseOrchestrator -> Action: Starting briefing generation")

        # Load updates from SQLite
        with self.db._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.company_id, u.week, u.date, u.update_text, u.author,
                       c.name as company_name, c.sector, c.stage, c.investment_thesis
                FROM updates u
                JOIN companies c ON u.company_id = c.id
                WHERE u.week = ?
            """, (week_num,))
            updates = [dict(r) for r in cursor.fetchall()]

        if not updates:
            raise ValueError(f"No weekly updates found in database for week {week_num}.")

        triage_reports = []
        for update in updates:
            cid = update["company_id"]
            c_trace = []
            company_triage = self.triage_company(cid, update, c_trace, on_step)
            triage_reports.append(company_triage)

        consolidation_prompt = (
            f"Here are the weekly triage reports for our portfolio companies:\n\n"
            f"=== TRIAGE REPORTS ===\n"
            + "\n---\n".join([
                f"Company: {t.company_name}\n"
                f"Urgency Score: {t.urgency_score}/10.0 ({t.urgency_label})\n"
                f"Reason: {t.reason}\n"
                f"Signals: {t.signals.model_dump_json()}\n"
                f"Deviations: {json.dumps(t.deviations)}\n"
                f"Suggested Action: {t.suggested_action}"
                for t in triage_reports
            ]) + "\n======================\n\n"
            f"Please generate the executive briefing summary and rank the companies by urgency."
        )

        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="PortfolioPulseOrchestrator",
            action="Consolidating briefing summary",
            thought="Summarizing portfolio health status, top concerns, and ranking reports by urgency.",
            details={"company_count": len(triage_reports)}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        print(f"[Reasoning Trace - Step {step_num}] PortfolioPulseOrchestrator -> Action: Consolidating briefing summary")

        briefing = self.llm_client.generate_structured(
            prompt=consolidation_prompt,
            schema_class=PulseBriefingResponse,
            system_instruction=CONSOLIDATION_INSTRUCTION,
            on_step=on_step
        )
        
        briefing.reasoning_trace = reasoning_trace
        briefing.ranked_portfolio = sorted(triage_reports, key=lambda x: x.urgency_score, reverse=True)
        
        # Save briefing to database
        self.db.save_briefing(briefing.date, briefing.summary, [t.model_dump() for t in briefing.ranked_portfolio])
        
        return briefing
