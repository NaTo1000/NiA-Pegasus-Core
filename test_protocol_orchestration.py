import json
import sys
import time
import types
from pathlib import Path

import pytest

from protocol_orchestration import ProtocolWorkflowOrchestrator


def test_file_path_fallback_uses_first_available_file(tmp_path):
    orchestrator = ProtocolWorkflowOrchestrator()
    valid = tmp_path / "payload.json"
    valid.write_text(json.dumps({"ok": True}), encoding="utf-8")

    payload, trace = orchestrator.resolve_resource(
        resource_key="payload.json",
        file_paths=[str(tmp_path / "missing.json"), str(valid)],
    )

    assert payload["ok"] is True
    assert trace.success is True
    assert trace.selected_channel == "file"
    assert trace.selected_path.endswith("payload.json")


def test_data_then_mcp_fallback_chain():
    orchestrator = ProtocolWorkflowOrchestrator()

    def mcp_server(_: str):
        return {"source": "mcp"}

    payload, trace = orchestrator.resolve_resource(
        resource_key="resource_a",
        data_payloads={},
        mcp_servers=[mcp_server],
    )

    assert payload["source"] == "mcp"
    assert trace.selected_channel == "mcp"
    assert any(step["channel"] == "data" and not step["ok"] for step in trace.steps)


def test_arrest_procedure_blocks_failing_channel_then_recovers():
    orchestrator = ProtocolWorkflowOrchestrator(max_failures=2, cooldown_seconds=0.2)
    now = time.time()
    orchestrator.policies["file"].arrested_until = now + 0.5
    orchestrator.policies["data"].arrested_until = now + 0.5
    orchestrator.policies["https"].arrested_until = now + 0.5

    def broken_server(_: str):
        raise RuntimeError("offline")

    with pytest.raises(RuntimeError):
        orchestrator.resolve_resource(resource_key="x", mcp_servers=[broken_server])
    with pytest.raises(RuntimeError):
        orchestrator.resolve_resource(resource_key="x", mcp_servers=[broken_server])
    assert orchestrator.policies["mcp"].is_arrested()

    # During arrest, mcp should be skipped.
    with pytest.raises(RuntimeError):
        orchestrator.resolve_resource(resource_key="x", mcp_servers=[broken_server])
    mcp_step = [step for step in orchestrator.monitor_log[-1].steps if step["channel"] == "mcp"][0]
    assert mcp_step["error"] == "arrested"

    # While mcp remains arrested, data fallback should still succeed.
    orchestrator.policies["data"].arrested_until = 0.0
    payload, trace = orchestrator.resolve_resource(
        resource_key="x",
        data_payloads={"x": {"source": "data"}},
        mcp_servers=[broken_server],
    )
    assert payload["source"] == "data"

    # After cooldown, mcp is attempted again.
    time.sleep(0.25)
    with pytest.raises(RuntimeError):
        orchestrator.resolve_resource(resource_key="x", mcp_servers=[broken_server])


def test_controller_workflow_monitoring_integration(tmp_path):
    if "quantum_computing" not in sys.modules:
        sys.modules["quantum_computing"] = types.SimpleNamespace()
    from quantum_consciousness_core import QuantumRoboticController

    target = tmp_path / "resource.txt"
    target.write_text("hello", encoding="utf-8")
    controller = QuantumRoboticController()
    payload = controller.orchestrate_protocol_resource(
        resource_key="resource.txt",
        file_paths=[str(target)],
    )
    assert payload == "hello"
    assert controller.workflow_monitor_log
    assert controller.workflow_monitor_log[-1]["selected_channel"] == "file"
