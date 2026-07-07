from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# =====================================================================
# VISIBLE REASONING MODELS
# =====================================================================
class ReasoningStep(BaseModel):
    step_num: int = Field(..., description="Chronological step number")
    agent_name: str = Field(..., description="Name of the agent or component performing the action")
    action: str = Field(..., description="What the agent is doing (e.g., 'Classifying query', 'Calling retrieval tool')")
    thought: str = Field(..., description="The internal reasoning/justification for this action")
    details: Dict[str, Any] = Field(default_factory=dict, description="Metadata or parameters (e.g., query params, results count)")

# =====================================================================
# TOOL 1: OPERATOR MEMORY MODELS
# =====================================================================
class SourceCitation(BaseModel):
    title: str = Field(..., description="Title of the source document")
    url: str = Field(..., description="Source URL or file path reference")
    snippet: str = Field(..., description="Relevant excerpt used for the synthesis")
    relevance_score: float = Field(..., description="Semantic match confidence score (0.0 to 1.0)")

class OperatorQueryRequest(BaseModel):
    query: str = Field(..., description="Founders' or partners' question")
    session_id: str = Field(default="default_session", description="Session ID for conversation history memory")

class OperatorQueryResponse(BaseModel):
    answer: str = Field(..., description="Synthesized answer citing sources")
    citations: List[SourceCitation] = Field(default_factory=list, description="Citations used in synthesis")
    confidence: float = Field(..., description="Confidence score of the answer (0.0 to 1.0)")
    escalate: bool = Field(..., description="True if query requires human partner judgment")
    escalation_reason: Optional[str] = Field(None, description="Reason for escalating to human GP")
    reasoning_trace: List[ReasoningStep] = Field(default_factory=list, description="Chronological log of agent reasoning steps")

# =====================================================================
# TOOL 2: PORTFOLIO PULSE MODELS
# =====================================================================
class Company(BaseModel):
    id: str
    name: str
    sector: str
    stage: str
    founded: str
    founders: List[str]
    description: str
    investment_thesis: str
    key_metrics_at_investment: Dict[str, Any]

class FounderUpdate(BaseModel):
    company_id: str
    company_name: str
    week: int
    date: str
    update_text: str
    author: str

class ExtractedSignals(BaseModel):
    revenue_trend: str = Field(..., description="Direction of revenue ('up', 'flat', 'down', 'not_mentioned')")
    revenue_detail: str = Field(..., description="Metrics or context regarding revenue")
    hiring_status: str = Field(..., description="Key hiring updates or open roles")
    sentiment: float = Field(..., description="Founder sentiment score (-1.0 to 1.0)")
    blockers: List[str] = Field(default_factory=list, description="Identified challenges or bottlenecks")
    explicit_asks: List[str] = Field(default_factory=list, description="Asks for help directed to the partner/firm")
    red_flags: List[str] = Field(default_factory=list, description="Urgent operational warnings")

class CompanyTriage(BaseModel):
    company_id: str
    company_name: str
    urgency_score: float = Field(..., description="Triage urgency score (0.0 to 10.0)")
    urgency_label: str = Field(..., description="Triage priority ('CRITICAL', 'WARNING', 'STABLE')")
    reason: str = Field(..., description="Detailed rationale behind the triage rating")
    signals: ExtractedSignals = Field(..., description="Signals extracted from this week's update")
    deviations: List[str] = Field(default_factory=list, description="Deviations from company's historical baseline")
    suggested_action: str = Field(..., description="Recommended action item for the partner")
    reasoning_trace: List[ReasoningStep] = Field(default_factory=list, description="Agent reasoning trace for this company")

class PulseBriefingResponse(BaseModel):
    date: str = Field(..., description="Date of the briefing")
    summary: str = Field(..., description="Executive summary of portfolio health this week")
    ranked_portfolio: List[CompanyTriage] = Field(..., description="Ranked list of companies requiring attention")
    reasoning_trace: List[ReasoningStep] = Field(default_factory=list, description="Agent briefing consolidation reasoning")

# =====================================================================
# TOOL 3: US CORRIDOR READINESS AUDITOR MODELS
# =====================================================================
class CriticAssessment(BaseModel):
    dimension: str = Field(..., description="Dimension audited ('messaging', 'pricing', 'trust_signals')")
    score: float = Field(..., description="Audit score for this dimension (0.0 to 10.0)")
    findings: List[str] = Field(..., description="Strengths or gaps identified")
    recommendations: List[str] = Field(..., description="Actionable recommendations")
    severity: str = Field(..., description="Urgency of fixes ('high', 'medium', 'low')")
    reasoning_trace: List[ReasoningStep] = Field(default_factory=list, description="Critic's internal reasoning steps")

class AuditRequest(BaseModel):
    url: Optional[str] = Field(None, description="Startup landing page URL to fetch live")
    fallback_text: Optional[str] = Field(None, description="Pasted website/deck text if fetch fails or URL not provided")
    target_country: Optional[str] = Field(None, description="Target country for international market diligence (optional)")

class ActionItem(BaseModel):
    action: str = Field(..., description="Specific fix or task")
    impact: str = Field(..., description="Expected GTM impact ('high', 'medium', 'low')")
    effort: str = Field(..., description="Expected dev/sales effort ('high', 'medium', 'low')")
    critic_source: str = Field(..., description="Which critic suggested this fix")

class AuditResponse(BaseModel):
    company_name: str = Field(..., description="Name of the audited startup")
    overall_score: float = Field(..., description="Overall GTM US corridor readiness score (0.0 to 100.0)")
    readiness_tier: str = Field(..., description="Readiness category ('US-Ready', 'Almost There', 'Needs Work', 'Not Ready')")
    synthesis: str = Field(..., description="Editor's summary synthesis of the audit")
    critic_reports: Dict[str, CriticAssessment] = Field(..., description="Individual critic audits")
    disagreements: List[str] = Field(default_factory=list, description="Where critics differed and how the editor resolved it")
    prioritized_actions: List[ActionItem] = Field(default_factory=list, description="Prioritized recommendations checklist")
    reasoning_trace: List[ReasoningStep] = Field(default_factory=list, description="Orchestrator's editorial reasoning trace")
