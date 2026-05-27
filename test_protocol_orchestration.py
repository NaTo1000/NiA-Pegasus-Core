import json
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

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


def test_low_latency_path_preference_selects_faster_route():
    orchestrator = ProtocolWorkflowOrchestrator()

    def mcp_server(_: str):
        return {"source": "mcp"}

    payload, trace = orchestrator.resolve_resource(
        resource_key="resource_a",
        data_payloads={"resource_a": {"source": "data"}},
        mcp_servers=[mcp_server],
        path_metrics={
            "data:resource_a": {"latency": 0.9, "bandwidth": 100.0, "mesh_health": 1.0},
            "mcp:0": {"latency": 0.02, "bandwidth": 10.0, "mesh_health": 1.0},
        },
    )

    assert payload["source"] == "mcp"
    assert trace.selected_channel == "mcp"
    assert trace.multiplexing_decisions[0]["selected_path"] == "mcp:0"


def test_high_bandwidth_path_preference_selects_richer_route():
    orchestrator = ProtocolWorkflowOrchestrator()

    with patch.object(orchestrator, "_read_https_source", side_effect=lambda url: {"source": url}):
        payload, trace = orchestrator.resolve_resource(
            resource_key="resource_a",
            data_payloads={"resource_a": {"source": "data"}},
            https_urls=["https://mesh.node/a"],
            path_metrics={
                "data:resource_a": {"latency": 0.1, "bandwidth": 5.0, "mesh_health": 1.0},
                "https://mesh.node/a": {"latency": 0.1, "bandwidth": 10_000.0, "mesh_health": 1.0},
            },
        )

    assert payload["source"] == "https://mesh.node/a"
    assert trace.selected_channel == "https"
    assert trace.selected_path == "https://mesh.node/a"


def test_multiplexing_under_contention_reselects_less_loaded_channel():
    orchestrator = ProtocolWorkflowOrchestrator()
    orchestrator.channel_active_load["data"] = orchestrator.channel_capacity["data"]

    def mcp_server(_: str):
        return {"source": "mcp"}

    payload, trace = orchestrator.resolve_resource(
        resource_key="resource_a",
        data_payloads={"resource_a": {"source": "data"}},
        mcp_servers=[mcp_server],
        path_metrics={
            "data:resource_a": {"latency": 0.1, "bandwidth": 100.0, "mesh_health": 1.0},
            "mcp:0": {"latency": 0.1, "bandwidth": 100.0, "mesh_health": 1.0},
        },
    )

    assert payload["source"] == "mcp"
    assert trace.selected_channel == "mcp"
    assert trace.multiplexing_decisions[0]["multiplex_load"] < 1.0


def test_mesh_relay_failover_and_https_arrest_behavior():
    orchestrator = ProtocolWorkflowOrchestrator(max_failures=2, cooldown_seconds=10.0)
    now = time.time()
    orchestrator.policies["file"].arrested_until = now + 5.0
    orchestrator.policies["data"].arrested_until = now + 5.0
    orchestrator.policies["mcp"].arrested_until = now + 5.0

    def fake_https(url: str):
        if url == "https://primary.mesh/path":
            raise RuntimeError("link degraded")
        return {"source": url}

    with patch.object(orchestrator, "_read_https_source", side_effect=fake_https):
        payload, trace = orchestrator.resolve_resource(
            resource_key="resource_a",
            https_urls=["https://primary.mesh/path"],
            mesh_relays={"https://primary.mesh/path": ["https://relay.mesh/path"]},
            path_metrics={
                "https://primary.mesh/path": {"latency": 0.1, "bandwidth": 50.0, "mesh_health": 0.1},
                "https://relay.mesh/path": {"latency": 0.2, "bandwidth": 70.0, "mesh_health": 0.95},
            },
        )
        assert payload["source"] == "https://relay.mesh/path"
        assert trace.selected_path == "https://relay.mesh/path"
        assert trace.mesh_failover_events

        with pytest.raises(RuntimeError):
            orchestrator.resolve_resource(
                resource_key="resource_a",
                https_urls=["https://primary.mesh/path"],
            )
        with pytest.raises(RuntimeError):
            orchestrator.resolve_resource(
                resource_key="resource_a",
                https_urls=["https://primary.mesh/path"],
            )
    assert orchestrator.policies["https"].is_arrested()
