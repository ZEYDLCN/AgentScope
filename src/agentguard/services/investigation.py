"""Soruşturma orkestrasyonu — §2.2 adım 5-11.

QueryBuilder → HybridRetriever → PromptBuilder → LLMClient → guard zinciri.
En fazla 2 retry; tükenirse kural motorundan deterministik fallback rapor.
"""

from __future__ import annotations

import time
from typing import Protocol

from agentguard.anomaly.rules import RuleEvaluation
from agentguard.llm.base import LLMClient
from agentguard.llm.guards import (
    GuardOutcome,
    OutputParseError,
    assemble_investigation,
    build_fallback_investigation,
    parse_and_validate,
)
from agentguard.llm.ollama_client import LLMUnavailableError
from agentguard.llm.prompt_builder import PROMPT_VERSION, build_system_prompt, build_user_prompt
from agentguard.llm.schema import investigation_json_schema
from agentguard.logging import get_logger
from agentguard.rag.query_builder import build_investigation_query
from agentguard.schemas.anomaly import AnomalyResult, AnomalyType
from agentguard.schemas.knowledge import RetrievedChunk
from agentguard.schemas.trace import AgentTrace

MAX_ATTEMPTS = 3  # ilk deneme + 2 retry (§14.3)

logger = get_logger("services.investigation")


class RAGRetriever(Protocol):
    """`RAGPipeline.retrieve` için minimal Protocol — `services` katmanının
    `rag` alt sistemine somut değil soyut bağımlılığı olsun diye."""

    def retrieve(self, query: str) -> list[RetrievedChunk]: ...


class InvestigationService:
    def __init__(
        self,
        llm: LLMClient,
        *,
        rag: RAGRetriever | None,
        model_name: str,
    ) -> None:
        self._llm = llm
        self._rag = rag
        self._model_name = model_name

    async def investigate(
        self,
        trace: AgentTrace,
        raw_features: dict[str, float],
        anomaly_result: AnomalyResult,
        rule_eval: RuleEvaluation,
    ) -> GuardOutcome:
        tool_names = [c.tool_name for c in sorted(trace.tool_calls, key=lambda c: c.index)]
        query, candidate_types = build_investigation_query(
            agent_id=trace.agent_id,
            tool_call_count=int(raw_features["tool_call_count"]),
            repeated_call_count=int(raw_features["repeated_call_count"]),
            unique_tool_count=int(raw_features["unique_tool_count"]),
            error_count=int(raw_features["error_count"]),
            total_tokens=int(raw_features["total_tokens"]),
            duration_sec=raw_features["duration_sec"],
            tool_names=tool_names,
            triggered_rules=rule_eval.triggered_rules,
        )
        detector_type = AnomalyType(candidate_types[0])

        retrieved = self._rag.retrieve(query) if self._rag is not None else []
        system_prompt = build_system_prompt()
        user_prompt, valid_tags = build_user_prompt(
            raw_features=raw_features,
            triggered_rules=rule_eval.triggered_rules,
            anomaly_score=anomaly_result.score,
            severity=anomaly_result.severity.value,
            candidate_types=candidate_types,
            retrieved_chunks=retrieved,
        )
        schema = investigation_json_schema()
        retrieved_doc_ids = [r.chunk.chunk_id for r in retrieved]

        last_error: str | None = None
        for attempt in range(MAX_ATTEMPTS):
            prompt_for_attempt = user_prompt
            if last_error:
                prompt_for_attempt += (
                    f"\n\n## ÖNCEKİ DENEME HATASI\nBir önceki yanıtın şu nedenle "
                    f"reddedildi: {last_error}. Lütfen yalnızca geçerli JSON döndür."
                )

            start = time.perf_counter()
            try:
                raw_text = await self._llm.generate(
                    system_prompt=system_prompt, user_prompt=prompt_for_attempt, json_schema=schema
                )
            except LLMUnavailableError as exc:
                logger.warning("investigation.llm_unavailable", attempt=attempt, error=str(exc))
                break
            latency_ms = int((time.perf_counter() - start) * 1000)

            try:
                output = parse_and_validate(raw_text)
            except OutputParseError as exc:
                last_error = str(exc)
                logger.warning("investigation.parse_failed", attempt=attempt, error=last_error)
                continue

            return assemble_investigation(
                llm_output=output,
                valid_tags=valid_tags,
                trace_id=trace.trace_id,
                detector_severity=anomaly_result.severity,
                detector_type=detector_type,
                retrieved_doc_ids=retrieved_doc_ids,
                model_name=self._model_name,
                prompt_version=PROMPT_VERSION,
                latency_ms=latency_ms,
                schema_valid_first_try=(attempt == 0),
            )

        fallback = build_fallback_investigation(
            trace_id=trace.trace_id,
            detector_severity=anomaly_result.severity,
            detector_type=detector_type,
            triggered_rules=rule_eval.triggered_rules,
            model_name=self._model_name,
            prompt_version=PROMPT_VERSION,
            latency_ms=0,
        )
        return GuardOutcome(
            investigation=fallback,
            schema_valid_first_try=False,
            grounding_dropped=0,
            detector_llm_disagreement=False,
            generated_by="fallback",
        )
