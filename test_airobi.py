import asyncio

from aieroub_airobi import AiRobI, ErrorReturnSignal, InnovationUpdate


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
    assert "sandbox failure" in report["error"]


def test_airobi_continuous_mode_produces_batches():
    engine = AiRobI(update_interval_seconds=0.0)

    async def error_source():
        return [ErrorReturnSignal(code=1001, message="mcp connection reset", component="mcp")]

    batches = asyncio.run(engine.run_continuous(error_source=error_source, iterations=2))
    assert len(batches) == 2
    assert batches[0]["count"] == 1
