"""Agent reasoning cycle with structured decision-making."""
from __future__ import annotations

import time
from typing import Callable, Any

from core.agent_types import (
    Intent, IntentKind, ToolCall, ToolResult, SourceReference,
    ExecutionContext, AgentPlan, AgentResponse
)
from core.context import Context as LegacyContext
from discovery.capability_registry import registry
from intelligence.llm_integration import LLMIntegration
from intelligence.system_prompt import get_system_prompt


class AgentCycle:
    """Implements the reasoning cycle: interpret -> plan -> execute -> verify -> respond."""

    def __init__(
        self,
        llm: LLMIntegration | None = None,
        max_iterations: int = 5,
        max_execution_time: float = 60.0,
        max_output_size: int = 1_000_000,
    ):
        self.llm = llm
        self.max_iterations = max_iterations
        self.max_execution_time = max_execution_time
        self.max_output_size = max_output_size
        self._iteration_count = 0
        self._start_time = 0.0

    def run(
        self,
        request: str,
        context: LegacyContext,
        tool_executor: Callable[[list[ToolCall]], list[ToolResult]],
        offline_mode: bool = False,
    ) -> AgentResponse:
        """Execute the full agent cycle for a request."""
        self._iteration_count = 0
        self._start_time = time.time()

        try:
            # Build execution context
            exec_context = self._build_context(request, context, offline_mode)

            # Step 1: Interpret intent
            intent = self._interpret_intent(request, exec_context)

            # Step 2: Determine if tools are needed
            plan = self._create_plan(intent, exec_context)

            # Step 3: Execute tools if needed
            tool_results = []
            if plan.tool_calls:
                tool_results = self._execute_tools(plan.tool_calls, tool_executor, exec_context)

            # Step 4: Verify and synthesize response
            response = self._synthesize_response(request, intent, plan, tool_results, exec_context)

            return response

        except Exception as exc:
            return AgentResponse(
                request=request,
                intent=Intent(IntentKind.UNKNOWN, 0.0, "Error during reasoning"),
                message=f"Error durante el razonamiento: {exc}",
                error=str(exc),
                error_category="internal_error",
                reasoning_method="error",
            )

    def _build_context(self, request: str, legacy_context: LegacyContext, offline_mode: bool) -> ExecutionContext:
        """Build ExecutionContext from legacy Context."""
        from pathlib import Path

        # Extract conversation history
        history = []
        for event in list(legacy_context.events)[-10:]:
            history.append({
                "request": event.get("request", ""),
                "message": event.get("message", ""),
                "operations": event.get("operations", []),
            })

        # Check if in git repository
        try:
            git_repo = bool(Path.cwd().joinpath(".git").exists())
        except Exception:
            git_repo = False

        return ExecutionContext(
            request=request,
            conversation_history=history,
            entities=legacy_context.entities,
            offline_mode=offline_mode,
            llm_available=self.llm is not None and self.llm.is_available(),
            current_directory=str(Path.cwd()),
            git_repository=git_repo,
            metadata={
                "last_question": legacy_context.last_question,
                "last_search": legacy_context.last_search,
                "last_answer": legacy_context.last_answer,
            },
        )

    def _interpret_intent(self, request: str, context: ExecutionContext | LegacyContext) -> Intent:
        """Classify the user's intent."""
        # Check if offline mode is enabled
        offline_mode = getattr(context, 'offline_mode', False)
        
        # Use LLM for semantic classification if available
        if self.llm and self.llm.is_available() and not offline_mode:
            try:
                return self._classify_with_llm(request, context)
            except Exception:
                # Fallback to rule-based classification
                pass

        # Rule-based classification
        return self._classify_with_rules(request, context)

    def _classify_with_llm(self, request: str, context: ExecutionContext) -> Intent:
        """Use LLM to classify intent."""
        import json

        prompt = f'''{get_system_prompt()}

Clasifica la siguiente petición del usuario en una de estas categorías:
{", ".join([k.value for k in IntentKind])}

Devuelve solo un objeto JSON con este formato:
{{"kind": "categoria", "confidence": 0.9, "reasoning": "breve explicación"}}

PETICIÓN: {request[:500]}
CONTEXTO: {json.dumps(context.metadata, ensure_ascii=False)[:300]}'''

        try:
            response = self.llm.generate_response(prompt, json_mode=True)
            result = json.loads(response)

            kind_str = result.get("kind", "unknown")
            kind = IntentKind(kind_str) if kind_str in [k.value for k in IntentKind] else IntentKind.UNKNOWN

            return Intent(
                kind=kind,
                confidence=float(result.get("confidence", 0.5)),
                reasoning=result.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            # Fallback to rules on error
            return self._classify_with_rules(request, context)

    def _classify_with_rules(self, request: str, context: ExecutionContext) -> Intent:
        """Rule-based intent classification."""
        from core.parser import normalize
        normalized = normalize(request).strip()

        # Simple keyword-based classification
        if any(word in normalized for word in ["proceso", "pid", "matar", "terminar"]):
            return Intent(IntentKind.PROCESS_QUERY, 0.8, "Keywords suggest process query")
        if any(word in normalized for word in ["archivo", "carpeta", "directorio", "borrar", "crear"]):
            return Intent(IntentKind.FILE_OPERATION, 0.8, "Keywords suggest file operation")
        if any(word in normalized for word in ["red", "ip", "puerto", "conexión"]):
            return Intent(IntentKind.NETWORK_QUERY, 0.8, "Keywords suggest network query")
        if any(word in normalized for word in ["git", "commit", "branch", "merge"]):
            return Intent(IntentKind.GIT_LOCAL, 0.9, "Keywords suggest Git operation")
        if "github" in normalized:
            return Intent(IntentKind.GITHUB_SEARCH, 0.9, "Keywords suggest GitHub search")
        if any(word in normalized for word in ["stack overflow", "stackoverflow", "error"]):
            return Intent(IntentKind.STACK_OVERFLOW, 0.7, "Keywords suggest Stack Overflow search")
        if any(word in normalized for word in ["calcula", "calculadora", "raíz", "potencia"]):
            return Intent(IntentKind.CALCULATION, 0.9, "Keywords suggest calculation")
        if any(word in normalized for word in ["sistema", "ram", "cpu", "hardware"]):
            return Intent(IntentKind.SYSTEM_INFO, 0.8, "Keywords suggest system info")
        if any(word in normalized for word in ["python", "código", "script", "programa"]):
            return Intent(IntentKind.DEVELOPMENT, 0.7, "Keywords suggest development")
        if any(word in normalized for word in ["traduce", "traducción"]):
            return Intent(IntentKind.TRANSLATION, 0.9, "Keywords suggest translation")
        if any(word in normalized for word in ["busca", "buscar", "google"]):
            return Intent(IntentKind.WEB_SEARCH, 0.7, "Keywords suggest web search")

        # Check for conversational patterns
        if len(normalized.split()) <= 3:
            return Intent(IntentKind.CONVERSATION, 0.6, "Short input suggests conversation")

        # Check for explanation requests
        if any(word in normalized for word in ["explica", "qué es", "cómo funciona"]):
            return Intent(IntentKind.EXPLANATION, 0.7, "Keywords suggest explanation request")

        return Intent(IntentKind.AMBIGUOUS, 0.4, "No clear intent detected")

    def _create_plan(self, intent: Intent, context: ExecutionContext) -> AgentPlan:
        """Create an execution plan based on intent."""
        plan = AgentPlan(intent=intent)

        # For direct answers without tools
        if intent.kind in {IntentKind.CONVERSATION, IntentKind.EXPLANATION}:
            if self.llm and self.llm.is_available():
                plan.direct_answer = self._generate_direct_answer(context.request, intent, context)
                plan.reasoning_method = "local_model"
            else:
                plan.needs_clarification = "Para responder necesito un modelo de lenguaje activo."
                plan.reasoning_method = "rules"
            return plan

        # For calculations, use calculator tool
        if intent.kind == IntentKind.CALCULATION:
            plan.tool_calls = self._plan_calculation(context.request)
            return plan

        # For GitHub search
        if intent.kind == IntentKind.GITHUB_SEARCH:
            plan.requires_internet = True
            if context.offline_mode:
                plan.needs_clarification = "La búsqueda en GitHub requiere conexión a Internet."
            else:
                plan.tool_calls = self._plan_github_search(context.request)
            return plan

        # For Stack Overflow search
        if intent.kind == IntentKind.STACK_OVERFLOW:
            plan.requires_internet = True
            if context.offline_mode:
                plan.needs_clarification = "La búsqueda en Stack Overflow requiere conexión a Internet."
            else:
                plan.tool_calls = self._plan_stack_overflow_search(context.request)
            return plan

        # For other intents, delegate to existing parser
        # This bridges the new agent cycle with the existing rule-based system
        plan.reasoning = "Delegating to existing parser for this intent"
        return plan

    def _generate_direct_answer(self, request: str, intent: Intent, context: ExecutionContext) -> str:
        """Generate a direct answer using LLM."""
        prompt = f'''{get_system_prompt()}

Responde a la siguiente petición de manera directa y útil.
Máximo 150 palabras.

PETICIÓN: {request[:700]}'''

        try:
            return self.llm.generate_response(prompt).strip()[:1500]
        except Exception:
            return "No pude generar una respuesta con el modelo disponible."

    def _plan_calculation(self, request: str) -> list[ToolCall]:
        """Plan calculator tool call."""
        from core.parser import normalize

        # Extract expression from request
        normalized = normalize(request)
        # Simple extraction - in production, use more sophisticated parsing
        expression = normalized.replace("calcula", "").replace("calculadora", "").replace("raíz", "sqrt").strip()

        if not expression:
            return []

        return [
            ToolCall(
                tool_name="evaluate",
                capability="calculator",
                arguments={"expression": expression},
                risk_level="read_only",
            )
        ]

    def _plan_github_search(self, request: str) -> list[ToolCall]:
        """Plan GitHub search tool call."""
        # Extract search query from request
        from core.parser import normalize
        normalized = normalize(request)
        query = normalized.replace("github", "").replace("busca", "").replace("buscar", "").strip()

        if not query:
            return []

        return [
            ToolCall(
                tool_name="search_repositories",
                capability="github",
                arguments={"query": query},
                risk_level="read_only",
                requires_confirmation=False,
            )
        ]

    def _plan_stack_overflow_search(self, request: str) -> list[ToolCall]:
        """Plan Stack Overflow search tool call."""
        from core.parser import normalize
        normalized = normalize(request)
        query = normalized.replace("stack overflow", "").replace("stackoverflow", "").replace("error", "").strip()

        if not query:
            return []

        return [
            ToolCall(
                tool_name="search_questions",
                capability="stack_exchange",
                arguments={"query": query, "site": "stackoverflow"},
                risk_level="read_only",
                requires_confirmation=False,
            )
        ]

    def _execute_tools(
        self,
        tool_calls: list[ToolCall],
        tool_executor: Callable[[list[ToolCall]], list[ToolResult]],
        context: ExecutionContext,
    ) -> list[ToolResult]:
        """Execute tool calls with safety checks."""
        self._iteration_count += 1

        if self._iteration_count > self.max_iterations:
            raise RuntimeError("Maximum iteration limit exceeded")

        if time.time() - self._start_time > self.max_execution_time:
            raise RuntimeError("Maximum execution time exceeded")

        # Execute tools via the provided executor
        results = tool_executor(tool_calls)

        # Check output size
        total_size = sum(len(r.stdout) + len(r.stderr) for r in results)
        if total_size > self.max_output_size:
            for r in results:
                r.stdout = r.stdout[:self.max_output_size // len(results)]
                r.stderr = r.stderr[:self.max_output_size // len(results)]

        return results

    def _synthesize_response(
        self,
        request: str,
        intent: Intent,
        plan: AgentPlan,
        tool_results: list[ToolResult],
        context: ExecutionContext,
    ) -> AgentResponse:
        """Synthesize final response from plan and results."""
        # If plan has direct answer, use it
        if plan.direct_answer:
            return AgentResponse(
                request=request,
                intent=intent,
                message=plan.direct_answer,
                reasoning_method=plan.reasoning_method or "local_model",
            )

        # If plan needs clarification
        if plan.needs_clarification:
            return AgentResponse(
                request=request,
                intent=intent,
                message=plan.needs_clarification,
                reasoning_method="rules",
            )

        # If tools were executed, synthesize from results
        if tool_results:
            message = self._format_tool_results(tool_results, intent)
            return AgentResponse(
                request=request,
                intent=intent,
                message=message,
                tool_results=tool_results,
                reasoning_method="hybrid" if self.llm else "rules",
            )

        # Fallback: delegate to existing system
        return AgentResponse(
            request=request,
            intent=intent,
            message="Procesando con el sistema existente...",
            reasoning_method="delegated",
        )

    def _format_tool_results(self, results: list[ToolResult], intent: Intent) -> str:
        """Format tool results into a human-readable message."""
        if not results:
            return "No se obtuvieron resultados."

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        if failed and not successful:
            return f"Error: {failed[0].error or 'La operación falló.'}"

        # Format based on intent
        if intent.kind == IntentKind.CALCULATION:
            if successful and successful[0].data.get("value") is not None:
                return f"Resultado: {successful[0].data['value']}"
            return "No pude calcular la expresión."

        if intent.kind == IntentKind.GITHUB_SEARCH:
            if successful and successful[0].data.get("results"):
                repos = successful[0].data["results"]
                return f"Se encontraron {len(repos)} repositorios:\n" + "\n".join(
                    f"- {r.get('name', 'N/A')}: {r.get('description', '')[:80]}" for r in repos[:5]
                )
            return "No se encontraron repositorios."

        if intent.kind == IntentKind.STACK_OVERFLOW:
            if successful and successful[0].data.get("results"):
                questions = successful[0].data["results"]
                return f"Se encontraron {len(questions)} preguntas:\n" + "\n".join(
                    f"- {q.get('title', 'N/A')}: {q.get('snippet', '')[:100]}" for q in questions[:3]
                )
            return "No se encontraron preguntas."

        # Generic formatting
        parts = []
        for r in successful:
            if r.stdout:
                parts.append(r.stdout[:500])
        return "\n".join(parts) if parts else "Operación completada."
