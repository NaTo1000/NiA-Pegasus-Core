#!/usr/bin/env python3
"""Vision creation orchestration for TWINBRAIN hemispherical matrix workflows."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass, field
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


@dataclass
class GeometryPayload:
    """CAD/scene geometry payload contract."""

    asset_id: str
    vertices: List[List[float]]
    faces: List[List[int]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorGPSPacket:
    """Vector + GPS + sensory packet contract."""

    vector_id: str
    vector: List[float]
    gps: Dict[str, float]
    sensory: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BehaviorTelemetryPacket:
    """Emotional telemetry contract for behavior perception and introspection."""

    sample_id: str
    emotion_signals: Dict[str, float]
    social_isolation_index: float
    atypical_environment: bool
    chemistry_markers: Dict[str, float] = field(default_factory=dict)
    interaction_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SnapshotBatch:
    """Chunked snapshot sequencing contract."""

    sequence_id: str
    task_id: str
    chunk_index: int
    total_chunks: int
    snapshot_ids: List[str]
    checkpoint_token: str


@dataclass
class ReportAttachment:
    """Report reattach metadata contract."""

    file_name: str
    content_type: str
    payload: Any
    checksum_sha256: str


@dataclass
class TwinbrainExportBundle:
    """Final export contract for TWINBRAIN matrix workflows."""

    bundle_id: str
    created_at: float
    topology_analysis: Dict[str, Any]
    report: Dict[str, Any]
    attachments: List[ReportAttachment]
    outbound_payload: Dict[str, Any]
    audit_chain_hash: str


@dataclass
class Assignment:
    """Assignment for one work item."""

    task_id: str
    squad_id: str
    lane: int
    cell: int


@dataclass
class StageRun:
    """Stage execution record."""

    stage_name: str
    success_count: int
    failure_count: int
    retries: int
    failovers: int
    duration_seconds: float


@dataclass
class ImmutableAuditRecord:
    """Append-only immutable audit record."""

    record_id: str
    event_type: str
    timestamp_unix: float
    details: Dict[str, Any]
    previous_hash: str
    record_hash: str


class ImmutableAuditTrail:
    """Hash-chained immutable audit trail."""

    def __init__(self):
        self.records: List[ImmutableAuditRecord] = []

    def append(self, event_type: str, details: Dict[str, Any]) -> ImmutableAuditRecord:
        timestamp = time.time()
        previous_hash = self.records[-1].record_hash if self.records else "GENESIS"
        payload = {
            "event_type": event_type,
            "timestamp_unix": timestamp,
            "details": details,
            "previous_hash": previous_hash,
        }
        blob = json.dumps(payload, sort_keys=True, default=str)
        record_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        record_id = hashlib.sha256(f"{record_hash}|{len(self.records)}".encode("utf-8")).hexdigest()[:20]
        record = ImmutableAuditRecord(
            record_id=record_id,
            event_type=event_type,
            timestamp_unix=timestamp,
            details=details,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )
        self.records.append(record)
        return record

    def verify(self) -> bool:
        previous_hash = "GENESIS"
        for record in self.records:
            payload = {
                "event_type": record.event_type,
                "timestamp_unix": record.timestamp_unix,
                "details": record.details,
                "previous_hash": record.previous_hash,
            }
            expected_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            if record.previous_hash != previous_hash or record.record_hash != expected_hash:
                return False
            previous_hash = record.record_hash
        return True

    def chain_hash(self) -> str:
        if not self.records:
            return "GENESIS"
        return self.records[-1].record_hash


@dataclass
class CircuitBreaker:
    """Per-stage circuit breaker."""

    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    failures: int = 0
    open_until: float = 0.0

    def is_open(self) -> bool:
        return time.time() < self.open_until

    def success(self) -> None:
        self.failures = 0
        self.open_until = 0.0

    def fail(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.open_until = time.time() + self.cooldown_seconds


class SnapshotSequencingEngine:
    """Deterministic chunking and checkpoint sequencing."""

    def __init__(self, *, default_chunk_size: int = 1000):
        self.default_chunk_size = max(1, default_chunk_size)

    def deterministic_sequence_id(self, task_id: str, chunk_index: int, total_chunks: int, snapshot_ids: Sequence[str]) -> str:
        seed = f"{task_id}|{chunk_index}|{total_chunks}|{','.join(snapshot_ids)}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]

    def create_batches(
        self,
        *,
        task_id: str,
        snapshot_ids: Sequence[str],
        chunk_size: Optional[int] = None,
        checkpoint: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[SnapshotBatch], Dict[str, Any]]:
        size = max(1, chunk_size or self.default_chunk_size)
        chunks = [list(snapshot_ids[i : i + size]) for i in range(0, len(snapshot_ids), size)]
        total_chunks = len(chunks)
        start_chunk = int((checkpoint or {}).get("next_chunk", 0))

        batches: List[SnapshotBatch] = []
        for chunk_index in range(start_chunk, total_chunks):
            chunk = chunks[chunk_index]
            sequence_id = self.deterministic_sequence_id(task_id, chunk_index, total_chunks, chunk)
            token = f"{task_id}:{chunk_index + 1}/{total_chunks}"
            batches.append(
                SnapshotBatch(
                    sequence_id=sequence_id,
                    task_id=task_id,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                    snapshot_ids=chunk,
                    checkpoint_token=token,
                )
            )

        next_checkpoint = {"task_id": task_id, "next_chunk": total_chunks, "completed": total_chunks == 0}
        return batches, next_checkpoint


class ParallelExecutionScheduler:
    """Parallel work queue execution with retries, failover, and circuit-breakers."""

    def __init__(
        self,
        *,
        max_workers: int = 12,
        retry_limit: int = 2,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
    ):
        self.max_workers = max(1, max_workers)
        self.retry_limit = max(0, retry_limit)
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = cooldown_seconds
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

    def run_stage(
        self,
        *,
        stage_name: str,
        work_items: Sequence[Any],
        worker: Callable[[Any], Any],
        failover_worker: Optional[Callable[[Any], Any]] = None,
    ) -> Tuple[List[Any], StageRun, List[Dict[str, Any]]]:
        if stage_name not in self.circuit_breakers:
            self.circuit_breakers[stage_name] = CircuitBreaker(
                failure_threshold=self.failure_threshold,
                cooldown_seconds=self.cooldown_seconds,
            )
        breaker = self.circuit_breakers[stage_name]
        if breaker.is_open():
            raise RuntimeError(f"stage_circuit_open:{stage_name}")

        start = time.time()
        task_queue: Queue[Tuple[int, Any]] = Queue()
        for index, item in enumerate(work_items):
            task_queue.put((index, item))

        results: List[Any] = [None] * len(work_items)
        failures = 0
        retries = 0
        failovers = 0
        event_log: List[Dict[str, Any]] = []
        lock = threading.Lock()

        def run_worker() -> None:
            nonlocal failures, retries, failovers
            while True:
                try:
                    idx, payload = task_queue.get_nowait()
                except Empty:
                    return
                try:
                    attempts = 0
                    while True:
                        try:
                            results[idx] = worker(payload)
                            with lock:
                                event_log.append({"event": "stage_item_success", "stage": stage_name, "index": idx})
                            break
                        except Exception as exc:  # noqa: BLE001
                            attempts += 1
                            if attempts <= self.retry_limit:
                                with lock:
                                    retries += 1
                                    event_log.append(
                                        {
                                            "event": "stage_item_retry",
                                            "stage": stage_name,
                                            "index": idx,
                                            "attempt": attempts,
                                            "error": type(exc).__name__,
                                        }
                                    )
                                continue
                            if failover_worker is not None:
                                try:
                                    results[idx] = failover_worker(payload)
                                    with lock:
                                        failovers += 1
                                        event_log.append(
                                            {
                                                "event": "stage_item_failover",
                                                "stage": stage_name,
                                                "index": idx,
                                                "error": type(exc).__name__,
                                            }
                                        )
                                    break
                                except Exception as failover_exc:  # noqa: BLE001
                                    with lock:
                                        failures += 1
                                        event_log.append(
                                            {
                                                "event": "stage_item_failure",
                                                "stage": stage_name,
                                                "index": idx,
                                                "error": type(failover_exc).__name__,
                                            }
                                        )
                                    break
                            with lock:
                                failures += 1
                                event_log.append(
                                    {
                                        "event": "stage_item_failure",
                                        "stage": stage_name,
                                        "index": idx,
                                        "error": type(exc).__name__,
                                    }
                                )
                            break
                finally:
                    task_queue.task_done()

        workers = min(self.max_workers, max(1, len(work_items)))
        threads = [threading.Thread(target=run_worker, daemon=True) for _ in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        if failures > 0:
            breaker.fail()
        else:
            breaker.success()

        stage_run = StageRun(
            stage_name=stage_name,
            success_count=len(work_items) - failures,
            failure_count=failures,
            retries=retries,
            failovers=failovers,
            duration_seconds=max(time.time() - start, 0.0),
        )
        return results, stage_run, event_log


class VisionCreationOrchestrator:
    """End-to-end orchestration for 3D/4D TWINBRAIN vision creation workflows."""

    def __init__(
        self,
        *,
        squad_shape: Tuple[int, int, int] = (3, 6, 9),
        scheduler: Optional[ParallelExecutionScheduler] = None,
        sequencing_engine: Optional[SnapshotSequencingEngine] = None,
        audit_trail: Optional[ImmutableAuditTrail] = None,
    ):
        self.squad_shape = squad_shape
        self.scheduler = scheduler or ParallelExecutionScheduler()
        self.sequencing_engine = sequencing_engine or SnapshotSequencingEngine()
        self.audit_trail = audit_trail or ImmutableAuditTrail()
        self.monitor_events: List[Dict[str, Any]] = []

    def investigate(self, *, mission_id: str, cad_assets: Sequence[Dict[str, Any]], snapshot_count: int) -> Dict[str, Any]:
        tasks = [f"{mission_id}-task-{idx}" for idx in range(max(1, len(cad_assets)))]
        details = {
            "mission_id": mission_id,
            "cad_asset_count": len(cad_assets),
            "snapshot_count": snapshot_count,
            "task_count": len(tasks),
            "tasks": tasks,
        }
        self._record("investigate", details)
        return details

    def split(self, *, mission_id: str, tasks: Sequence[str]) -> List[str]:
        split_tasks = [f"{mission_id}:{task}" for task in tasks]
        self._record("split", {"mission_id": mission_id, "count": len(split_tasks)})
        return split_tasks

    def assign(self, *, tasks: Sequence[str]) -> List[Assignment]:
        lanes = self.squad_shape[0] * self.squad_shape[1]
        cells = self.squad_shape[2]
        assignments: List[Assignment] = []
        for idx, task_id in enumerate(tasks):
            lane = idx % lanes
            cell = idx % cells
            assignments.append(
                Assignment(
                    task_id=task_id,
                    squad_id=f"SQ-{lane // self.squad_shape[1]}-{lane % self.squad_shape[1]}-{cell}",
                    lane=lane,
                    cell=cell,
                )
            )
        self._record(
            "assign",
            {
                "task_count": len(tasks),
                "lane_count": lanes,
                "cell_count": cells,
                "assigned": len(assignments),
            },
        )
        return assignments

    def allocate(self, *, assignments: Sequence[Assignment]) -> Dict[str, Any]:
        by_squad: Dict[str, int] = {}
        for assignment in assignments:
            by_squad[assignment.squad_id] = by_squad.get(assignment.squad_id, 0) + 1
        allocation = {
            "assignment_count": len(assignments),
            "unique_squads": len(by_squad),
            "distribution": by_squad,
        }
        self._record("allocate", allocation)
        return allocation

    def report(
        self,
        *,
        mission_id: str,
        topology_analysis: Dict[str, Any],
        allocation: Dict[str, Any],
        stage_runs: Sequence[StageRun],
    ) -> Dict[str, Any]:
        report = {
            "mission_id": mission_id,
            "generated_at": time.time(),
            "topology_analysis": topology_analysis,
            "allocation": allocation,
            "stages": [asdict(stage) for stage in stage_runs],
        }
        self._record("report", {"mission_id": mission_id, "stage_count": len(stage_runs)})
        return report

    def reattach_files(self, *, files: Dict[str, Any]) -> List[ReportAttachment]:
        attachments: List[ReportAttachment] = []
        for name, payload in files.items():
            blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            attachments.append(
                ReportAttachment(
                    file_name=name,
                    content_type="application/json",
                    payload=payload,
                    checksum_sha256=hashlib.sha256(blob).hexdigest(),
                )
            )
        self._record("reattach", {"attachment_count": len(attachments)})
        return attachments

    def send_data(self, *, mission_id: str, bundle: TwinbrainExportBundle) -> Dict[str, Any]:
        outbound = {
            "destination": "TWINBRAIN_HEMISPHERICAL_MATRIX",
            "mission_id": mission_id,
            "bundle_id": bundle.bundle_id,
            "audit_chain_hash": bundle.audit_chain_hash,
            "attachment_count": len(bundle.attachments),
        }
        self._record("send_data", outbound)
        return outbound

    def run_vision_creation_pipeline(
        self,
        *,
        mission_id: str,
        cad_assets: Sequence[Dict[str, Any]],
        snapshots: Sequence[str],
        vector_packets: Sequence[VectorGPSPacket],
        telemetry_packets: Optional[Sequence[BehaviorTelemetryPacket]] = None,
        failover_routes: Optional[Dict[str, Callable[[Any], Any]]] = None,
    ) -> TwinbrainExportBundle:
        failover_routes = failover_routes or {}
        stage_runs: List[StageRun] = []

        geometry_payloads, stage, events = self.scheduler.run_stage(
            stage_name="cad_ingestion",
            work_items=list(cad_assets),
            worker=lambda item: GeometryPayload(
                asset_id=str(item.get("asset_id", "unknown")),
                vertices=list(item.get("vertices", [])),
                faces=list(item.get("faces", [])),
                metadata={k: v for k, v in item.items() if k not in {"asset_id", "vertices", "faces"}},
            ),
            failover_worker=failover_routes.get("cad_ingestion"),
        )
        stage_runs.append(stage)
        self._record_stage(stage, events)

        snapshot_batches, checkpoint = self.sequencing_engine.create_batches(
            task_id=f"{mission_id}-snapshots",
            snapshot_ids=list(snapshots),
        )
        self._record(
            "snapshot_sequence",
            {
                "mission_id": mission_id,
                "batch_count": len(snapshot_batches),
                "checkpoint": checkpoint,
            },
        )

        fused_vectors, stage, events = self.scheduler.run_stage(
            stage_name="gps_vector_fusion",
            work_items=list(vector_packets),
            worker=lambda packet: {
                "vector_id": packet.vector_id,
                "norm": sum(abs(x) for x in packet.vector),
                "gps": packet.gps,
                "sensory_keys": sorted(packet.sensory.keys()),
            },
            failover_worker=failover_routes.get("gps_vector_fusion"),
        )
        stage_runs.append(stage)
        self._record_stage(stage, events)

        sensory_fusion, stage, events = self.scheduler.run_stage(
            stage_name="sensory_fusion",
            work_items=list(fused_vectors),
            worker=lambda packet: {
                "vector_id": packet["vector_id"],
                "signal_density": packet["norm"] / max(1, len(packet["sensory_keys"]) + 1),
                "gps": packet["gps"],
            },
            failover_worker=failover_routes.get("sensory_fusion"),
        )
        stage_runs.append(stage)
        self._record_stage(stage, events)

        behavior_introspection: Dict[str, Any] = {}
        if telemetry_packets:
            behavior_introspection = self.analyze_behavior_introspection(telemetry_packets=telemetry_packets)

        topology = {
            "dimension_3d": {
                "geometry_assets": len([g for g in geometry_payloads if g is not None]),
                "vector_packets": len([v for v in fused_vectors if v is not None]),
                "snapshot_batches": len(snapshot_batches),
            },
            "dimension_4d": {
                "temporal_layers": len(snapshot_batches),
                "sequencing_checkpoint": checkpoint,
                "sensory_fusion_points": len([s for s in sensory_fusion if s is not None]),
                "behavior_introspection": behavior_introspection,
            },
        }
        self._record("topology_analysis", topology)

        investigation = self.investigate(
            mission_id=mission_id,
            cad_assets=cad_assets,
            snapshot_count=len(snapshots),
        )
        split_tasks = self.split(mission_id=mission_id, tasks=investigation["tasks"])
        assignments = self.assign(tasks=split_tasks)
        allocation = self.allocate(assignments=assignments)

        report = self.report(
            mission_id=mission_id,
            topology_analysis=topology,
            allocation=allocation,
            stage_runs=stage_runs,
        )
        attachments = self.reattach_files(
            files={
                "topology_analysis.json": topology,
                "allocation.json": allocation,
                "snapshot_checkpoint.json": checkpoint,
            }
        )

        provisional_bundle = TwinbrainExportBundle(
            bundle_id=hashlib.sha256(f"{mission_id}|{time.time()}".encode("utf-8")).hexdigest()[:24],
            created_at=time.time(),
            topology_analysis=topology,
            report=report,
            attachments=attachments,
            outbound_payload={},
            audit_chain_hash=self.audit_trail.chain_hash(),
        )
        outbound = self.send_data(mission_id=mission_id, bundle=provisional_bundle)

        self._record("bundle_finalize", {"bundle_id": provisional_bundle.bundle_id, "mission_id": mission_id})
        bundle = TwinbrainExportBundle(
            bundle_id=provisional_bundle.bundle_id,
            created_at=provisional_bundle.created_at,
            topology_analysis=topology,
            report=report,
            attachments=attachments,
            outbound_payload=outbound,
            audit_chain_hash=self.audit_trail.chain_hash(),
        )
        return bundle

    def _record_stage(self, stage_run: StageRun, events: Sequence[Dict[str, Any]]) -> None:
        self.monitor_events.append({"event": "stage_run", **asdict(stage_run)})
        for event in events:
            self.monitor_events.append(event)
            if event["event"] == "stage_item_failover":
                self.audit_trail.append("failover", event)
            elif event["event"] == "stage_item_retry":
                self.audit_trail.append("retry", event)
        self.audit_trail.append(
            "stage_transition",
            {
                "stage": stage_run.stage_name,
                "success_count": stage_run.success_count,
                "failure_count": stage_run.failure_count,
                "retries": stage_run.retries,
                "failovers": stage_run.failovers,
            },
        )

    def _record(self, event_type: str, details: Dict[str, Any]) -> None:
        self.monitor_events.append({"event": event_type, **details})
        self.audit_trail.append(event_type, details)

    def analyze_behavior_introspection(
        self, *, telemetry_packets: Sequence[BehaviorTelemetryPacket]
    ) -> Dict[str, Any]:
        if not telemetry_packets:
            return {}

        count = len(telemetry_packets)
        isolation = sum(max(0.0, packet.social_isolation_index) for packet in telemetry_packets) / count
        atypical_ratio = (
            sum(1 for packet in telemetry_packets if packet.atypical_environment) / count
        )
        emotion_totals: Dict[str, float] = {}
        chemistry_totals: Dict[str, float] = {}
        for packet in telemetry_packets:
            for emotion, value in packet.emotion_signals.items():
                emotion_totals[emotion] = emotion_totals.get(emotion, 0.0) + float(value)
            for marker, value in packet.chemistry_markers.items():
                chemistry_totals[marker] = chemistry_totals.get(marker, 0.0) + float(value)

        emotion_profile = {
            key: value / count
            for key, value in sorted(emotion_totals.items())
        }
        chemistry_profile = {
            key: value / count
            for key, value in sorted(chemistry_totals.items())
        }

        stress_signal = (
            emotion_profile.get("fear", 0.0)
            + emotion_profile.get("anger", 0.0)
            + chemistry_profile.get("cortisol", 0.0)
        )
        trust_signal = (
            emotion_profile.get("trust", 0.0)
            + chemistry_profile.get("oxytocin", 0.0)
            + chemistry_profile.get("serotonin", 0.0)
        )
        if stress_signal > trust_signal * 1.2:
            inferred_intention = "defensive_withdrawal"
            mimic_strategy = "low_stimulus_empathy_and_space_preservation"
        elif trust_signal > stress_signal * 1.2:
            inferred_intention = "cooperative_engagement"
            mimic_strategy = "collaborative_guidance_with_affirmation"
        else:
            inferred_intention = "uncertain_transition"
            mimic_strategy = "observe_then_gradual_alignment"

        outcome_conclusion = (
            "stabilize_behavioral_outcome"
            if atypical_ratio >= 0.5 or isolation >= 0.6
            else "optimize_behavioral_outcome"
        )

        introspection = {
            "sample_count": count,
            "average_isolation_index": isolation,
            "atypical_environment_ratio": atypical_ratio,
            "emotion_profile": emotion_profile,
            "chemistry_profile": chemistry_profile,
            "inferred_intention": inferred_intention,
            "mimic_design": mimic_strategy,
            "outcome_conclusion": outcome_conclusion,
        }
        self._record("behavior_introspection", introspection)
        return introspection


__all__ = [
    "Assignment",
    "BehaviorTelemetryPacket",
    "GeometryPayload",
    "ImmutableAuditTrail",
    "ParallelExecutionScheduler",
    "ReportAttachment",
    "SnapshotBatch",
    "SnapshotSequencingEngine",
    "TwinbrainExportBundle",
    "VectorGPSPacket",
    "VisionCreationOrchestrator",
]
