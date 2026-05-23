import hashlib
import json

from vision_creation_orchestration import (
    BehaviorTelemetryPacket,
    SnapshotSequencingEngine,
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
