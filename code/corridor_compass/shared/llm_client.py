import json
import logging
import inspect
import httpx
from typing import List, Dict, Any, Type, Callable, Optional
from shared.config import OPENROUTER_API_KEY, DEFAULT_LLM_MODEL
from shared.models import ReasoningStep

logger = logging.getLogger("TogetherLLMClient")

def function_to_tool_schema(func: Callable) -> Dict[str, Any]:
    """Helper to convert a Python function into OpenAI/OpenRouter tool calling format"""
    sig = inspect.signature(func)
    doc = func.__doc__ or "No description provided."
    
    properties = {}
    required = []
    
    for name, param in sig.parameters.items():
        # Map python annotations to JSON schema types
        ptype = param.annotation
        jtype = "string"
        
        if ptype == int:
            jtype = "integer"
        elif ptype == float:
            jtype = "number"
        elif ptype == bool:
            jtype = "boolean"
        elif ptype == list or getattr(ptype, "__origin__", None) == list:
            jtype = "array"
            
        properties[name] = {
            "type": jtype,
            "description": f"The {name} input parameter."
        }
        
        if param.default == inspect.Parameter.empty:
            required.append(name)
            
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": doc.strip(),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }

class TogetherLLMClient:
    def __init__(self, model_name: str = DEFAULT_LLM_MODEL):
        self.model_name = model_name
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        if not OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is not set. "
                "Please configure OPENROUTER_API_KEY in your .env file."
            )
            
        self.headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/SanatanSinghVishen",
            "X-Title": "Together Fund Agentic Workspace"
        }
        logger.info(f"Initialized OpenRouter Client using model: {self.model_name}")

    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for calling the OpenRouter endpoint"""
        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(self.api_url, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"OpenRouter API call failed: {e}")
            if 'response' in locals() and response is not None:
                logger.error(f"API Error Response: {response.text}")
            raise

    def generate(self, prompt: str, system_instruction: str = None) -> str:
        """Simple text generation helper"""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.2
        }
        
        res = self._call_api(payload)
        return res["choices"][0]["message"]["content"]

    def generate_structured(
        self,
        prompt: str,
        schema_class: Type,
        system_instruction: str = None,
        on_step: Optional[Callable[[ReasoningStep], None]] = None
    ) -> Any:
        """Generates content structured according to a Pydantic model schema"""
        messages = []
        
        # We append instructions to force JSON matching the schema
        schema_fields = schema_class.model_json_schema()
        
        json_instruction = (
            f"You MUST return a JSON object that strictly adheres to this JSON Schema:\n"
            f"{json.dumps(schema_fields, indent=2)}\n\n"
            f"Do not wrap your output in markdown formatting (like ```json ... ```). Return raw JSON only."
        )
        
        sys_message = system_instruction or "You are a precise JSON formatting assistant."
        messages.append({"role": "system", "content": f"{sys_message}\n\n{json_instruction}"})
        messages.append({"role": "user", "content": prompt})

        if on_step:
            on_step(ReasoningStep(
                step_num=1,
                agent_name="SchemaFormatter",
                action="Starting schema-structured generation",
                thought="Preparing constraints and sending structured JSON payload to OpenRouter.",
                details={"schema": schema_class.__name__}
            ))

        payload = {
            "model": self.model_name,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }
        
        res = self._call_api(payload)
        res_text = res["choices"][0]["message"]["content"].strip()
        
        # Clean any markdown artifacts
        if res_text.startswith("```json"):
            res_text = res_text[7:]
        if res_text.endswith("```"):
            res_text = res_text[:-3]
            
        try:
            parsed_data = json.loads(res_text.strip())
            return schema_class(**parsed_data)
        except Exception as e:
            logger.error(f"Error parsing structured response: {e}")
            logger.error(f"Raw content was: {res_text}")
            raise

    def call_with_tools(
        self,
        prompt: str,
        tools: List[Callable],
        system_instruction: str = None,
        reasoning_trace: List[ReasoningStep] = None,
        agent_name: str = "Agent",
        on_step: Optional[Callable[[ReasoningStep], None]] = None
    ) -> tuple[str, List[ReasoningStep]]:
        """
        Executes a single turn model generation with Python functions registered as tools.
        """
        if reasoning_trace is None:
            reasoning_trace = []
            
        tool_schemas = [function_to_tool_schema(t) for t in tools]
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "tools": tool_schemas,
            "tool_choice": "auto",
            "temperature": 0.2
        }

        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name=agent_name,
            action="Initializing model execution",
            thought="Sending prompt to OpenRouter with tool schema mapping.",
            details={"prompt_len": len(prompt), "tools": [t.__name__ for t in tools]}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        print(f"\n[Reasoning Trace - Step {step_num}] {agent_name} -> Action: Initializing model execution")

        res_data = self._call_api(payload)
        message = res_data["choices"][0]["message"]
        
        # Check if the model triggered tool calls
        if "tool_calls" in message and message["tool_calls"]:
            for tool_call in message["tool_calls"]:
                func_name = tool_call["function"]["name"]
                func_args = json.loads(tool_call["function"]["arguments"])
                
                # Find matching python tool
                tool_func = next((t for t in tools if t.__name__ == func_name), None)
                
                step_num = len(reasoning_trace) + 1
                step = ReasoningStep(
                    step_num=step_num,
                    agent_name=agent_name,
                    action=f"Executing tool call: {func_name}",
                    thought=f"OpenRouter model decided to retrieve information using tool '{func_name}'.",
                    details={"args": func_args}
                )
                reasoning_trace.append(step)
                if on_step:
                    on_step(step)
                print(f"[Reasoning Trace - Step {step_num}] {agent_name} -> Action: Executing tool call: {func_name} with args {func_args}")

                if tool_func:
                    try:
                        # Execute local python tool
                        tool_result = tool_func(**func_args)
                        
                        step_num = len(reasoning_trace) + 1
                        step = ReasoningStep(
                            step_num=step_num,
                            agent_name=agent_name,
                            action=f"Tool execution complete: {func_name}",
                            thought="Recalling model with tool results context to synthesize final output.",
                            details={"result_preview": str(tool_result)[:200] + "..." if len(str(tool_result)) > 200 else str(tool_result)}
                        )
                        reasoning_trace.append(step)
                        if on_step:
                            on_step(step)
                        print(f"[Reasoning Trace - Step {step_num}] {agent_name} -> Action: Tool complete, recalling model.")

                        # Create follow-up turn context
                        follow_up_prompt = (
                            f"{prompt}\n\n"
                            f"=== TOOL CALL EXECUTION RESULT ===\n"
                            f"Tool: {func_name}\n"
                            f"Arguments: {func_args}\n"
                            f"Result:\n{json.dumps(tool_result, indent=2) if isinstance(tool_result, (dict, list)) else str(tool_result)}\n"
                            f"==================================\n\n"
                            f"Please synthesize the final answer based on the tool results above."
                        )
                        
                        # Generate final answer from second turn
                        final_res_text = self.generate(follow_up_prompt, system_instruction)
                        return final_res_text, reasoning_trace
                    except Exception as tool_err:
                        logger.error(f"Error executing tool: {tool_err}")
                        raise
                else:
                    logger.error(f"Model tried to call function {func_name} but it was not registered.")

        # Direct text response (no tool calling needed)
        step_num = len(reasoning_trace) + 1
        step = ReasoningStep(
            step_num=step_num,
            agent_name=agent_name,
            action="Synthesizing directly",
            thought="No tool calls were needed. Summarizing response directly from parametric knowledge.",
            details={}
        )
        reasoning_trace.append(step)
        if on_step:
            on_step(step)
        print(f"[Reasoning Trace - Step {step_num}] {agent_name} -> Action: Direct synthesis complete.")
        return message["content"], reasoning_trace
