#!/usr/bin/env python3
"""Aierioub (AiRobI): error-driven research and innovation update batching."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
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


@dataclass
class AuditRecord:
    """Immutable blockchain-style audit record."""

    record_id: str
    event_type: str
    timestamp_unix: float
    timestamp_iso: str
    spec_instruction: str
    reason_why: str
    method_how: str
    details: Dict[str, Any]
    previous_hash: str
    record_hash: str
    digital_watermark_signature: str


class CloudBlockchainAuditEngine:
    """Append-only hash-chained audit records with digital watermark signatures."""

    def __init__(self, *, signer_id: str = "airobi-public-audit"):
        self.signer_id = signer_id
        self.records: List[AuditRecord] = []

    def append_record(
        self,
        *,
        event_type: str,
        spec_instruction: str,
        reason_why: str,
        method_how: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        if not spec_instruction.strip():
            raise ValueError("spec_instruction is required")
        if not reason_why.strip():
            raise ValueError("reason_why is required")
        if not method_how.strip():
            raise ValueError("method_how is required")

        details = details or {}
        timestamp_unix = time.time()
        timestamp_iso = datetime.fromtimestamp(timestamp_unix, tz=timezone.utc).isoformat()
        previous_hash = self.records[-1].record_hash if self.records else "GENESIS"
        payload = {
            "event_type": event_type,
            "timestamp_unix": timestamp_unix,
            "timestamp_iso": timestamp_iso,
            "spec_instruction": spec_instruction,
            "reason_why": reason_why,
            "method_how": method_how,
            "details": details,
            "previous_hash": previous_hash,
        }
        payload_blob = json.dumps(payload, sort_keys=True, default=str)
        record_hash = hashlib.sha256(payload_blob.encode()).hexdigest()
        watermark = hashlib.sha256(f"{record_hash}|{self.signer_id}|{timestamp_iso}".encode()).hexdigest()
        record_id = hashlib.sha256(f"{record_hash}|{len(self.records)}".encode()).hexdigest()[:20]

        record = AuditRecord(
            record_id=record_id,
            event_type=event_type,
            timestamp_unix=timestamp_unix,
            timestamp_iso=timestamp_iso,
            spec_instruction=spec_instruction,
            reason_why=reason_why,
            method_how=method_how,
            details=details,
            previous_hash=previous_hash,
            record_hash=record_hash,
            digital_watermark_signature=watermark,
        )
        self.records.append(record)
        return record

    def verify_chain(self) -> bool:
        previous_hash = "GENESIS"
        for record in self.records:
            payload = {
                "event_type": record.event_type,
                "timestamp_unix": record.timestamp_unix,
                "timestamp_iso": record.timestamp_iso,
                "spec_instruction": record.spec_instruction,
                "reason_why": record.reason_why,
                "method_how": record.method_how,
                "details": record.details,
                "previous_hash": record.previous_hash,
            }
            expected_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
            expected_watermark = hashlib.sha256(
                f"{expected_hash}|{self.signer_id}|{record.timestamp_iso}".encode()
            ).hexdigest()
            if record.previous_hash != previous_hash:
                return False
            if record.record_hash != expected_hash:
                return False
            if record.digital_watermark_signature != expected_watermark:
                return False
            previous_hash = record.record_hash
        return True

    def export_public_audit(self, output_path: Optional[str] = None) -> List[Dict[str, Any]]:
        serializable = [record.__dict__.copy() for record in self.records]
        if output_path:
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(serializable, handle, indent=2, sort_keys=True)
        return serializable


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
        self.audit_engine = CloudBlockchainAuditEngine()
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
            self.audit_engine.append_record(
                event_type="thought_change",
                spec_instruction="Generate innovation update from error return signal",
                reason_why="Maintain resilient, ethical, and continuously improved behavior under runtime errors",
                method_how="Classify error code, gather researched context via fallback channels, and emit a sandbox-first recommendation",
                details={
                    "error_code": error.code,
                    "component": error.component,
                    "research_topic": topic,
                    "source_channel": channel,
                    "source_path": path,
                    "recommendation": recommendation,
                },
            )

        batch_id = hashlib.sha256(f"{timestamp}-{len(updates)}".encode()).hexdigest()[:16]
        batch = {
            "batch_id": batch_id,
            "timestamp": timestamp,
            "updates": [u.__dict__ for u in updates],
            "count": len(updates),
        }
        self.audit_engine.append_record(
            event_type="creation",
            spec_instruction="Create AiRobI innovation output batch",
            reason_why="Preserve immutable traceability for externally auditable AI update decisions",
            method_how="Aggregate update proposals into a batch and chain a blockchain-style audit record",
            details={"batch_id": batch_id, "count": len(updates)},
        )
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
            LOGGER.exception("AiRobI sandbox test failed for code %s: %s", update.error_code, error)

        report = {
            "error_code": update.error_code,
            "research_topic": update.research_topic,
            "success": success,
            "result": result,
            "error": error,
            "started_at": started,
            "ended_at": time.time(),
        }
        self.audit_engine.append_record(
            event_type="alteration",
            spec_instruction="Execute AiRobI sandbox validation for update",
            reason_why="Ensure proposed innovations are validated before external deployment",
            method_how="Run test executor in sandbox context and persist outcome in immutable audit chain",
            details={
                "error_code": update.error_code,
                "research_topic": update.research_topic,
                "success": success,
                "error": error,
            },
        )
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

    def export_public_audit(self, output_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export immutable audit records for public and third-party review."""
        return self.audit_engine.export_public_audit(output_path=output_path)

    def verify_audit_chain(self) -> bool:
        """Verify immutable blockchain-style hash chain integrity."""
        return self.audit_engine.verify_chain()

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
