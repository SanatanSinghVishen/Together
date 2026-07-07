import json
import logging
from typing import List, Dict, Any
from shared.llm_client import TogetherLLMClient
from shared.models import OperatorQueryResponse, SourceCitation, ReasoningStep
from shared.embeddings import ChromaVectorStore

logger = logging.getLogger("OperatorAgent")

# Lazy initialization of the Vector Store
_vector_store = None

def get_store(force_reload: bool = False):
    global _vector_store
    if _vector_store is None or force_reload:
        _vector_store = ChromaVectorStore(collection_name="operator_knowledge")
    return _vector_store

def search_knowledge_base(query: str) -> str:
    """
    Searches the partner operating playbook and Paul Graham essays knowledge base.
    Use this tool when the query asks about advice, startup strategy, VC precedents,
    hiring guidelines, pricing frameworks, or product scaling advice.
    
    Args:
        query: Semantic query text for the search.
        
    Returns:
        A JSON string containing matching excerpts and source document metadata.
    """
    store = get_store()
    try:
        results = store.search(query_text=query, n_results=5)
    except Exception as e:
        logger.warning(f"Search failed, forcing vector store collection reload: {e}")
        store = get_store(force_reload=True)
        results = store.search(query_text=query, n_results=5)
    
    # Format results to return to the model
    formatted_results = []
    for r in results:
        formatted_results.append({
            "document_preview": r["document"],
            "title": r["metadata"].get("title", "Unknown"),
            "url": r["metadata"].get("url", ""),
            "author": r["metadata"].get("author", "Unknown"),
            "date": r["metadata"].get("date", ""),
            "relevance_score": r["relevance_score"]
        })
        
    return json.dumps(formatted_results, indent=2)

def escalate_to_human_partner(reason: str) -> str:
    """
    Escalates the founder's query to a human General Partner (GP).
    Call this tool ONLY when:
    1. The question requires subjective or context-heavy VC judgment (e.g. evaluating specific startup founders, negotiation tactics, legal conflicts, or custom valuation advice).
    2. The query is highly sensitive or confidential.
    3. The query asks for an opinion on a competitor's portfolio or specific firm-private valuations.
    
    Args:
        reason: Rationale detailing why this query is too judgment-heavy or sensitive for an AI to answer.
        
    Returns:
        A confirmation message indicating escalation has been triggered.
    """
    result = {
        "status": "Escalated to General Partner",
        "reason": reason,
        "action_required": "GP manual review and reply"
    }
    return json.dumps(result, indent=2)


SYSTEM_INSTRUCTION = """
You are the Together Fund Partner Memory Agent. Your job is to ingest and query the scattered operating knowledge of our venture capital partners (strategy memos, blog posts, past founder Q&As) to answer founders' questions.

You have access to two tools:
1. `search_knowledge_base`: Use this tool to retrieve relevant guidelines and precedents from the vector database. You should decide whether to call this tool based on the user's query. If you can answer directly without RAG (e.g. simple greetings), you don't have to call it.
2. `escalate_to_human_partner`: Call this tool ONLY when the user's query involves high-stakes subjective judgment (e.g., custom equity division disputes, sensitive board conflicts, firing key team members, legal liabilities, or direct competitor reviews).

If you call `escalate_to_human_partner`, confirm the escalation in your final response.
If you call `search_knowledge_base`, synthesize the answer using the retrieved facts and make sure to mention the sources you drew upon.
"""

class OperatorMemoryAgent:
    def __init__(self):
        self.llm_client = TogetherLLMClient()
        self.sessions = {} # Simple in-memory session store for conversation context

    def run_query(
        self,
        query: str,
        session_id: str = "default_session",
        on_step: Any = None
    ) -> OperatorQueryResponse:
        # Load conversation history for session
        if session_id not in self.sessions:
            self.sessions[session_id] = []
            
        history = self.sessions[session_id]
        
        # Build prompt with history
        history_context = ""
        if history:
            history_context = "=== CONVERSATION HISTORY ===\n"
            for role, text in history[-4:]: # Keep last 4 turns
                history_context += f"{role}: {text}\n"
            history_context += "============================\n\n"
            
        full_prompt = (
            f"{history_context}"
            f"Founder/Partner Query: {query}\n\n"
            f"Please execute your tool calls or answer directly if no tools are required."
        )
        
        # 1. Execute agentic loop with tools
        tools = [search_knowledge_base, escalate_to_human_partner]
        reasoning_trace = []
        
        agent_raw_response, reasoning_trace = self.llm_client.call_with_tools(
            prompt=full_prompt,
            tools=tools,
            system_instruction=SYSTEM_INSTRUCTION,
            reasoning_trace=reasoning_trace,
            agent_name="OperatorMemoryAgent",
            on_step=on_step
        )
        
        # Save user query and agent response to session history
        history.append(("user", query))
        history.append(("assistant", agent_raw_response))
        
        # 2. Extract structured response and citations
        # We parse the trace to check if escalation was triggered or RAG results were returned
        escalate = False
        escalation_reason = None
        citations = []
        
        for step in reasoning_trace:
            if step.action.startswith("Executing tool call: escalate_to_human_partner"):
                escalate = True
                args = step.details.get("args", {})
                escalation_reason = args.get("reason", "Subjective judgment required.")
            elif step.action.startswith("Tool execution complete: search_knowledge_base"):
                try:
                    # Parse the result preview or direct result
                    results = json.loads(step.details.get("result_preview", "[]").replace("...", ""))
                except Exception:
                    # Fallback to run a quick search to reconstruct citations if parsing fails
                    results = json.loads(search_knowledge_base(query))
                    
                for idx, r in enumerate(results[:3]): # Max 3 citations
                    citations.append(SourceCitation(
                        title=r.get("title", "Reference Doc"),
                        url=r.get("url", ""),
                        snippet=r.get("document_preview", "")[:200] + "...",
                        relevance_score=r.get("relevance_score", 0.8)
                    ))

        # 3. Structure the final response using a Gemini schema call to guarantee model compatibility
        structure_prompt = (
            f"Convert the following agent response into the final structured output.\n\n"
            f"=== AGENT RESPONSE ===\n"
            f"{agent_raw_response}\n"
            f"======================\n\n"
            f"Escalation Flag: {escalate}\n"
            f"Escalation Reason: {escalation_reason}\n"
            f"Citations count: {len(citations)}"
        )
        
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name="OperatorMemoryAgent",
            action="Structuring response",
            thought="Formatting final output strictly according to the Pydantic schema.",
            details={}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        
        try:
            structured_response = self.llm_client.generate_structured(
                prompt=structure_prompt,
                schema_class=OperatorQueryResponse,
                system_instruction=(
                    "You are a strict JSON formatter. Parse the agent response and set it as the 'answer' field. "
                    "Under all circumstances, the 'answer' field MUST contain the text of the AGENT RESPONSE provided, "
                    "even if the Escalation Flag is True or Citations count is zero. Do not alter, shorten, or write 'none' for the 'answer' field."
                ),
                on_step=on_step
            )
            # Inject dynamic values
            structured_response.citations = citations
            structured_response.escalate = escalate
            structured_response.escalation_reason = escalation_reason
            structured_response.reasoning_trace = reasoning_trace
            return structured_response
        except Exception as err:
            logger.error(f"Failed to generate structured response: {err}")
            # Fallback
            return OperatorQueryResponse(
                answer=agent_raw_response,
                citations=citations,
                confidence=0.8 if not escalate else 0.5,
                escalate=escalate,
                escalation_reason=escalation_reason,
                reasoning_trace=reasoning_trace
            )
