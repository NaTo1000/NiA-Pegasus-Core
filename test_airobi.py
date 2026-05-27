import asyncio
import json
import time
from unittest.mock import patch

from aieroub_airobi import AiRobI, ErrorReturnSignal, InnovationUpdate
from protocol_orchestration import ProtocolWorkflowOrchestrator


def test_airobi_classifies_error_codes():
    engine = AiRobI()
    assert engine.classify_error_code(ErrorReturnSignal(code=429, message="rate limit")) == "latency_resilience"
    assert engine.classify_error_code(ErrorReturnSignal(code=404, message="missing")) == "input_contract_hardening"
    assert engine.classify_error_code(ErrorReturnSignal(code=503, message="unavailable")) == "service_fault_tolerance"


def test_airobi_uses_mcp_fallback_for_research_payload():
    engine = AiRobI()

    def mcp_server(_: str):
        return {"pattern": "retry_with_backoff"}

    batch = engine.generate_update_batch(
        errors=[ErrorReturnSignal(code=503, message="service down", component="gateway")],
        mcp_servers=[mcp_server],
    )
    assert batch["count"] == 1
    update = batch["updates"][0]
    assert update["source_channel"] == "mcp"
    assert "external evidence" in update["recommendation"]


def test_airobi_sandbox_test_captures_failures():
    engine = AiRobI()
    update = InnovationUpdate(
        error_code=500,
        research_topic="service_fault_tolerance",
        source_channel="none",
        source_path="",
        recommendation="run rollback",
    )

    def failing_executor(_: InnovationUpdate):
        raise RuntimeError("sandbox failure")

    report = engine.sandbox_test_update(update, failing_executor)
    assert report["success"] is False
    assert report["error"] == "execution_failed:RuntimeError"


def test_airobi_continuous_mode_produces_batches():
    engine = AiRobI(update_interval_seconds=0.0)

    async def error_source():
        return [ErrorReturnSignal(code=1001, message="mcp connection reset", component="mcp")]

    batches = asyncio.run(engine.run_continuous(error_source=error_source, iterations=2))
    assert len(batches) == 2
    assert batches[0]["count"] == 1


def test_airobi_audit_chain_contains_required_metadata_and_verifies():
    engine = AiRobI()
    engine.generate_update_batch(errors=[ErrorReturnSignal(code=500, message="service crash", component="api")])
    records = engine.export_public_audit()
    assert records
    first = records[0]
    assert first["spec_instruction"]
    assert first["reason_why"]
    assert first["method_how"]
    assert first["timestamp_iso"]
    assert first["digital_watermark_signature"]
    assert engine.verify_audit_chain() is True


def test_airobi_public_audit_export_is_available_for_third_party_review(tmp_path):
    engine = AiRobI()
    engine.generate_update_batch(errors=[ErrorReturnSignal(code=404, message="not found", component="gateway")])
    output = tmp_path / "public_audit.json"
    exported = engine.export_public_audit(output_path=str(output))
    assert output.is_file()
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert len(exported) == len(persisted)
    assert persisted[0]["record_hash"]


def test_airobi_audits_multiplexing_and_mesh_failover_events():
    orchestrator = ProtocolWorkflowOrchestrator(max_failures=3)
    now = time.time()
    orchestrator.policies["file"].arrested_until = now + 10
    orchestrator.policies["data"].arrested_until = now + 10
    orchestrator.policies["mcp"].arrested_until = now + 10

    def fake_https(url: str):
        if "primary" in url:
            raise RuntimeError("primary down")
        return {"pattern": "mesh relay"}

    engine = AiRobI(orchestrator=orchestrator)
    with patch.object(orchestrator, "_read_https_source", side_effect=fake_https):
        batch = engine.generate_update_batch(
            errors=[ErrorReturnSignal(code=503, message="service down", component="gateway")],
            https_urls=["https://primary.mesh/topic.json"],
            mesh_relays={"https://primary.mesh/topic.json": ["https://relay.mesh/topic.json"]},
            path_metrics={
                "https://primary.mesh/topic.json": {"latency": 0.2, "bandwidth": 25.0, "mesh_health": 0.1},
                "https://relay.mesh/topic.json": {"latency": 0.3, "bandwidth": 50.0, "mesh_health": 0.9},
            },
        )

    assert batch["count"] == 1
    events = [record.event_type for record in engine.audit_engine.records]
    assert "thought" in events
    assert "change" in events
    assert "creation" in events
