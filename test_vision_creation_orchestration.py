import hashlib
import json

import pytest

from vision_creation_orchestration import (
    BehaviorTelemetryPacket,
    DecisionPrompt,
    SnapshotSequencingEngine,
    TouchPressurePacket,
    VectorGPSPacket,
    VisionCreationOrchestrator,
)


def test_split_assign_allocation_matches_3x6x9_model():
    orchestrator = VisionCreationOrchestrator(squad_shape=(3, 6, 9))
    tasks = [f"task-{index}" for index in range(200)]

    split_tasks = orchestrator.split(mission_id="mission-a", tasks=tasks)
    assignments = orchestrator.assign(tasks=split_tasks)
    allocation = orchestrator.allocate(assignments=assignments)

    assert len(split_tasks) == len(tasks)
    assert len(assignments) == len(tasks)
    assert len({assignment.task_id for assignment in assignments}) == len(tasks)
    assert allocation["assignment_count"] == len(tasks)
    assert sum(allocation["distribution"].values()) == len(tasks)


def test_snapshot_sequence_batches_are_deterministic_and_resumable():
    engine = SnapshotSequencingEngine(default_chunk_size=3)
    snapshots = [f"snap-{index}" for index in range(10)]

    first_batches, checkpoint = engine.create_batches(task_id="seq-mission", snapshot_ids=snapshots)
    second_batches, _ = engine.create_batches(task_id="seq-mission", snapshot_ids=snapshots)

    assert len(first_batches) == 4
    assert checkpoint["next_chunk"] == 4
    assert [batch.sequence_id for batch in first_batches] == [batch.sequence_id for batch in second_batches]

    resumed_batches, resumed_checkpoint = engine.create_batches(
        task_id="seq-mission",
        snapshot_ids=snapshots,
        checkpoint={"next_chunk": 2},
    )
    assert resumed_batches[0].chunk_index == 2
    assert resumed_checkpoint["next_chunk"] == 4


def test_pipeline_failover_records_events_and_keeps_bundle_generation():
    orchestrator = VisionCreationOrchestrator()

    packets = [
        VectorGPSPacket(vector_id="vec-1", vector=None, gps={"lat": 37.0, "lon": -122.0}, sensory={"audio": 0.4}),
    ]

    bundle = orchestrator.run_vision_creation_pipeline(
        mission_id="mission-failover",
        cad_assets=[{"asset_id": "cad-1", "vertices": [[0, 0, 0]], "faces": [[0, 0, 0]]}],
        snapshots=[f"snap-{idx}" for idx in range(6)],
        vector_packets=packets,
        failover_routes={
            "gps_vector_fusion": lambda packet: {
                "vector_id": packet.vector_id,
                "norm": 0.0,
                "gps": packet.gps,
                "sensory_keys": sorted(packet.sensory.keys()),
            }
        },
    )

    assert bundle.outbound_payload["destination"] == "TWINBRAIN_HEMISPHERICAL_MATRIX"
    assert any(event["event"] == "stage_item_failover" for event in orchestrator.monitor_events)
    assert any(record.event_type == "failover" for record in orchestrator.audit_trail.records)
    assert orchestrator.audit_trail.verify()


def test_report_reattach_and_export_bundle_integrity():
    orchestrator = VisionCreationOrchestrator()

    bundle = orchestrator.run_vision_creation_pipeline(
        mission_id="mission-integrity",
        cad_assets=[{"asset_id": "cad-1", "vertices": [[0, 0, 0], [1, 0, 0]], "faces": [[0, 1, 1]]}],
        snapshots=[f"snap-{idx}" for idx in range(9)],
        vector_packets=[
            VectorGPSPacket(
                vector_id="vec-1",
                vector=[1.0, 2.0, 3.0],
                gps={"lat": 51.5, "lon": -0.1},
                sensory={"audio": 0.8, "temp": 22.5},
            )
        ],
    )

    assert bundle.report["mission_id"] == "mission-integrity"
    assert bundle.outbound_payload["bundle_id"] == bundle.bundle_id
    assert bundle.audit_chain_hash == orchestrator.audit_trail.chain_hash()

    for attachment in bundle.attachments:
        encoded = json.dumps(attachment.payload, sort_keys=True, default=str).encode("utf-8")
        checksum = hashlib.sha256(encoded).hexdigest()
        assert attachment.checksum_sha256 == checksum


def test_behavior_introspection_emotional_telemetry_for_atypical_environments():
    orchestrator = VisionCreationOrchestrator()
    telemetry = [
        BehaviorTelemetryPacket(
            sample_id="s1",
            emotion_signals={"fear": 0.8, "trust": 0.2},
            social_isolation_index=0.9,
            atypical_environment=True,
            chemistry_markers={"cortisol": 0.7, "serotonin": 0.2},
            interaction_context={"setting": "high-noise"},
        ),
        BehaviorTelemetryPacket(
            sample_id="s2",
            emotion_signals={"fear": 0.7, "anger": 0.6, "trust": 0.1},
            social_isolation_index=0.8,
            atypical_environment=True,
            chemistry_markers={"cortisol": 0.8, "oxytocin": 0.1},
            interaction_context={"setting": "crowded"},
        ),
    ]

    bundle = orchestrator.run_vision_creation_pipeline(
        mission_id="mission-telemetry",
        cad_assets=[{"asset_id": "cad-1", "vertices": [[0, 0, 0]], "faces": [[0, 0, 0]]}],
        snapshots=[f"snap-{idx}" for idx in range(5)],
        vector_packets=[
            VectorGPSPacket(
                vector_id="vec-1",
                vector=[0.1, 0.2, 0.3],
                gps={"lat": 1.0, "lon": 2.0},
                sensory={"audio": 0.6},
            )
        ],
        telemetry_packets=telemetry,
    )

    introspection = bundle.topology_analysis["dimension_4d"]["behavior_introspection"]
    assert introspection["inferred_intention"] == "defensive_withdrawal"
    assert introspection["outcome_conclusion"] == "stabilize_behavioral_outcome"
    assert introspection["atypical_environment_ratio"] == 1.0
    assert any(record.event_type == "behavior_introspection" for record in orchestrator.audit_trail.records)


def test_decision_processing_returns_color_validation_and_precedence():
    orchestrator = VisionCreationOrchestrator()
    summary = orchestrator.process_decision_prompts(
        prompts=[
            DecisionPrompt(
                prompt_id="d1",
                text="We should act with love empathy and care to support the human outcome.",
            ),
            DecisionPrompt(
                prompt_id="d2",
                text="This is malicious and abusive behavior designed to exploit and be cruel.",
            ),
            DecisionPrompt(
                prompt_id="d3",
                text="A moderate compromise is acceptable with limited tolerable constraints.",
            ),
        ]
    )

    assert summary["prompt_count"] == 3
    assert len(summary["evaluations"]) == 3
    assert summary["evaluations"][0]["precedence_score"] >= summary["evaluations"][1]["precedence_score"]
    assert summary["evaluations"][1]["precedence_score"] >= summary["evaluations"][2]["precedence_score"]

    by_id = {item["prompt_id"]: item for item in summary["evaluations"]}
    assert by_id["d1"]["classification"] == "loving"
    assert by_id["d1"]["color_code"] == "#00C853"
    assert by_id["d2"]["classification"] == "despicable"
    assert by_id["d2"]["color_code"] == "#C62828"
    assert by_id["d3"]["classification"] == "tolerable"
    assert by_id["d3"]["color_code"] == "#FBC02D"

    for evaluation in summary["evaluations"]:
        assert 0.0 <= evaluation["probability_percent"] <= 100.0
        assert 0.0 <= evaluation["intention_accuracy_percent"] <= 100.0
        assert 0.0 <= evaluation["perception_accuracy_percent"] <= 100.0
        assert evaluation["research_explanation"]


def test_decision_processing_writes_blockchain_audit_and_research_summary():
    orchestrator = VisionCreationOrchestrator()
    summary = orchestrator.process_decision_prompts(
        prompts=[
            DecisionPrompt(prompt_id="d1", text="good ethical fair and safe innovation"),
            DecisionPrompt(prompt_id="d2", text="bad unsafe harmful unfair output"),
        ]
    )

    assert summary["audit_chain_hash"] == orchestrator.audit_trail.chain_hash()
    assert orchestrator.audit_trail.verify()
    assert any(record.event_type == "decision_processing" for record in orchestrator.audit_trail.records)
    assert any(record.event_type == "decision_research_summary" for record in orchestrator.audit_trail.records)


def test_dexterity_pressure_touch_control_with_2048_tesseract_block():
    orchestrator = VisionCreationOrchestrator()
    summary = orchestrator.process_dexterity_touch_control(
        packets=[
            TouchPressurePacket(
                packet_id="tp-1",
                touch_points=[
                    {"x": 10, "y": 20, "pressure": 0.62, "velocity": 0.4},
                    {"x": 24, "y": 40, "pressure": 0.58, "velocity": 0.5},
                    {"x": 31, "y": 55, "pressure": 0.64, "velocity": 0.3},
                ],
            ),
            TouchPressurePacket(
                packet_id="tp-2",
                touch_points=[
                    {"x": 120, "y": 320, "pressure": 0.87, "velocity": 0.7},
                    {"x": 140, "y": 340, "pressure": 0.81, "velocity": 0.6},
                    {"x": 160, "y": 360, "pressure": 0.84, "velocity": 0.8},
                ],
            ),
        ]
    )

    assert summary["packet_count"] == 2
    assert summary["required_block_shape"] == [2048, 2048]
    assert len(summary["evaluations"]) == 2
    assert summary["evaluations"][0]["dexterity_score"] >= summary["evaluations"][1]["dexterity_score"]
    assert summary["audit_chain_hash"] == orchestrator.audit_trail.chain_hash()
    assert orchestrator.audit_trail.verify()

    for item in summary["evaluations"]:
        assert item["block_shape"] == [2048, 2048]
        assert item["pressure_touch_class"] in {"firm_precision", "balanced_control", "light_touch"}
        assert item["dexterity_level"] in {"expert", "advanced", "intermediate", "basic"}
        assert 0.0 <= item["dexterity_percent"] <= 100.0

    assert any(record.event_type == "dexterity_touch_control" for record in orchestrator.audit_trail.records)
    assert any(record.event_type == "dexterity_touch_summary" for record in orchestrator.audit_trail.records)


def test_dexterity_pressure_touch_control_rejects_non_2048_block():
    orchestrator = VisionCreationOrchestrator()
    with pytest.raises(ValueError, match="invalid_tesseract_block_shape"):
        orchestrator.process_dexterity_touch_control(
            packets=[
                TouchPressurePacket(
                    packet_id="tp-invalid",
                    touch_points=[{"x": 0, "y": 0, "pressure": 0.5, "velocity": 0.1}],
                    tesseract_block_width=1024,
                    tesseract_block_height=1024,
                )
            ]
        )
