#!/usr/bin/env python3
"""Aierioub (AiRobI): error-driven research and innovation update batching."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

from protocol_orchestration import ProtocolWorkflowOrchestrator

LOGGER = logging.getLogger(__name__)


@dataclass
class ErrorReturnSignal:
    """Structured error return code input."""

    code: int
    message: str
    component: str = "runtime"
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InnovationUpdate:
    """Single innovation update proposal generated from error signals."""

    error_code: int
    research_topic: str
    source_channel: str
    source_path: str
    recommendation: str
    sandbox_test_required: bool = True
    trace: Dict[str, Any] = field(default_factory=dict)


class AiRobI:
    """
    AiRobI continuously transforms error return codes into researched innovation batches.

    Workflow:
    1) classify error code -> research topic
    2) gather research via orchestrated file/data/MCP/HTTPS chain
    3) emit update batch
    4) execute sandbox tests for proposed updates
    """

    def __init__(
        self,
        *,
        orchestrator: Optional[ProtocolWorkflowOrchestrator] = None,
        update_interval_seconds: float = 30.0,
    ):
        self.orchestrator = orchestrator or ProtocolWorkflowOrchestrator()
        self.update_interval_seconds = update_interval_seconds
        self.batch_log: List[Dict[str, Any]] = []
        self.sandbox_log: List[Dict[str, Any]] = []

    def classify_error_code(self, error: ErrorReturnSignal) -> str:
        """Map return codes to innovation research topics."""
        code = int(error.code)
        if code in {408, 429, 504}:
            return "latency_resilience"
        if 400 <= code < 500:
            return "input_contract_hardening"
        if 500 <= code < 600:
            return "service_fault_tolerance"
        if code in {1001, 1002, 1003}:
            return "mcp_connectivity_stability"
        return "adaptive_runtime_optimization"

    def generate_update_batch(
        self,
        *,
        errors: Iterable[ErrorReturnSignal],
        file_paths: Optional[List[str]] = None,
        data_payloads: Optional[Dict[str, Any]] = None,
        mcp_servers: Optional[List[Callable[[str], Any]]] = None,
        https_urls: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create one innovation output batch from the current error set."""
        timestamp = time.time()
        updates: List[InnovationUpdate] = []
        for error in errors:
            topic = self.classify_error_code(error)
            resource_key = f"{topic}.json"
            try:
                research_payload, trace = self.orchestrator.resolve_resource(
                    resource_key=resource_key,
                    file_paths=file_paths,
                    data_payloads=data_payloads,
                    mcp_servers=mcp_servers,
                    https_urls=https_urls,
                )
                channel = trace.selected_channel
                path = trace.selected_path
                rationale = f"use_research_from_{channel}"
            except RuntimeError:
                research_payload = {}
                channel = "none"
                path = ""
                rationale = "fallback_to_internal_heuristics"

            recommendation = self._build_recommendation(error, topic, research_payload, rationale)
            updates.append(
                InnovationUpdate(
                    error_code=error.code,
                    research_topic=topic,
                    source_channel=channel,
                    source_path=path,
                    recommendation=recommendation,
                    trace={
                        "error_message": error.message,
                        "component": error.component,
                        "context": error.context,
                        "rationale": rationale,
                    },
                )
            )

        batch_id = hashlib.sha256(f"{timestamp}-{len(updates)}".encode()).hexdigest()[:16]
        batch = {
            "batch_id": batch_id,
            "timestamp": timestamp,
            "updates": [u.__dict__ for u in updates],
            "count": len(updates),
        }
        self.batch_log.append(batch)
        return batch

    def sandbox_test_update(
        self,
        update: InnovationUpdate,
        test_executor: Callable[[InnovationUpdate], Any],
    ) -> Dict[str, Any]:
        """Execute a single update in a testing sandbox and capture the result."""
        started = time.time()
        try:
            result = test_executor(update)
            success = True
            error = ""
        except Exception as exc:  # noqa: BLE001
            result = None
            success = False
            error = f"{type(exc).__name__}: {exc}"
            LOGGER.warning("AiRobI sandbox test failed for code %s: %s", update.error_code, error)

        report = {
            "error_code": update.error_code,
            "research_topic": update.research_topic,
            "success": success,
            "result": result,
            "error": error,
            "started_at": started,
            "ended_at": time.time(),
        }
        self.sandbox_log.append(report)
        return report

    async def run_continuous(
        self,
        *,
        error_source: Callable[[], Awaitable[List[ErrorReturnSignal]]],
        iterations: int = 1,
        file_paths: Optional[List[str]] = None,
        data_payloads: Optional[Dict[str, Any]] = None,
        mcp_servers: Optional[List[Callable[[str], Any]]] = None,
        https_urls: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Continuously produce update batches from live error signals."""
        batches: List[Dict[str, Any]] = []
        for index in range(max(iterations, 0)):
            errors = await error_source()
            batch = self.generate_update_batch(
                errors=errors,
                file_paths=file_paths,
                data_payloads=data_payloads,
                mcp_servers=mcp_servers,
                https_urls=https_urls,
            )
            batch["sequence"] = index
            batches.append(batch)
            if index < iterations - 1:
                await asyncio.sleep(self.update_interval_seconds)
        return batches

    def _build_recommendation(
        self,
        error: ErrorReturnSignal,
        topic: str,
        research_payload: Any,
        rationale: str,
    ) -> str:
        payload_hint = ""
        if isinstance(research_payload, dict) and research_payload:
            payload_hint = f" with external evidence keys={list(research_payload.keys())[:3]}"
        return (
            f"[AiRobI] topic={topic} code={error.code} component={error.component} "
            f"action=prototype_and_validate{payload_hint} rationale={rationale}"
        )
