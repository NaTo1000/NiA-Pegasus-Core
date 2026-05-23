#!/usr/bin/env python3
"""Workflow orchestration with monitored fallback chains and arrest procedures."""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

LOGGER = logging.getLogger(__name__)


@dataclass
class CircuitArrestPolicy:
    """Arrest (circuit-breaker) policy for a single source channel."""

    max_failures: int = 3
    cooldown_seconds: float = 30.0
    failure_count: int = 0
    arrested_until: float = 0.0

    def is_arrested(self, now: Optional[float] = None) -> bool:
        timestamp = time.time() if now is None else now
        return timestamp < self.arrested_until

    def register_success(self) -> None:
        self.failure_count = 0
        self.arrested_until = 0.0

    def register_failure(self, now: Optional[float] = None) -> None:
        timestamp = time.time() if now is None else now
        self.failure_count += 1
        if self.failure_count >= self.max_failures:
            self.arrested_until = timestamp + self.cooldown_seconds


@dataclass
class OrchestrationTrace:
    """Trace of one orchestration attempt."""

    resource_key: str
    started_at: float
    ended_at: float = 0.0
    selected_channel: str = "none"
    selected_path: str = ""
    selected_path_score: float = 0.0
    latency_snapshot: Dict[str, float] = field(default_factory=dict)
    bandwidth_snapshot: Dict[str, float] = field(default_factory=dict)
    multiplexing_decisions: List[Dict[str, Any]] = field(default_factory=list)
    mesh_failover_events: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    success: bool = False

    def close(self, success: bool, channel: str = "none", path: str = "", score: float = 0.0) -> None:
        self.success = success
        self.selected_channel = channel
        self.selected_path = path
        self.selected_path_score = score
        self.ended_at = time.time()


@dataclass
class RouteCandidate:
    """Single selectable route candidate for adaptive multiplexing."""

    channel: str
    path: str
    resolver: Callable[[], Tuple[Any, str, Optional[str]]]
    mesh_hops: int = 0
    relay_from: str = ""


class ProtocolWorkflowOrchestrator:
    """Chains multiple data acquisition paths with monitoring and arrest safeguards."""

    def __init__(
        self,
        *,
        max_failures: int = 3,
        cooldown_seconds: float = 30.0,
        https_timeout_seconds: float = 3.0,
        latency_weight: float = 0.35,
        bandwidth_weight: float = 0.30,
        multiplex_weight: float = 0.20,
        mesh_health_weight: float = 0.15,
    ):
        self.https_timeout_seconds = https_timeout_seconds
        self.latency_weight = latency_weight
        self.bandwidth_weight = bandwidth_weight
        self.multiplex_weight = multiplex_weight
        self.mesh_health_weight = mesh_health_weight
        self.policies = {
            "file": CircuitArrestPolicy(max_failures=max_failures, cooldown_seconds=cooldown_seconds),
            "data": CircuitArrestPolicy(max_failures=max_failures, cooldown_seconds=cooldown_seconds),
            "mcp": CircuitArrestPolicy(max_failures=max_failures, cooldown_seconds=cooldown_seconds),
            "https": CircuitArrestPolicy(max_failures=max_failures, cooldown_seconds=cooldown_seconds),
        }
        self.channel_capacity = {"file": 4.0, "data": 8.0, "mcp": 2.0, "https": 4.0}
        self.channel_active_load = {"file": 0.0, "data": 0.0, "mcp": 0.0, "https": 0.0}
        self.channel_latency_ewma = {"file": 0.05, "data": 0.001, "mcp": 0.08, "https": 0.12}
        self.channel_bandwidth_estimate = {"file": 120.0, "data": 500.0, "mcp": 35.0, "https": 90.0}
        self.monitor_log: List[OrchestrationTrace] = []

    def resolve_resource(
        self,
        *,
        resource_key: str,
        file_paths: Optional[Iterable[str]] = None,
        data_payloads: Optional[Dict[str, Any]] = None,
        mcp_servers: Optional[Iterable[Callable[[str], Any]]] = None,
        https_urls: Optional[Iterable[str]] = None,
        path_metrics: Optional[Dict[str, Dict[str, float]]] = None,
        mesh_relays: Optional[Dict[str, List[str]]] = None,
        mesh_link_health: Optional[Dict[str, float]] = None,
    ) -> Tuple[Any, OrchestrationTrace]:
        """Resolve a resource through adaptive route multiplexing with arrest controls."""
        trace = OrchestrationTrace(resource_key=resource_key, started_at=time.time())
        data_payloads = data_payloads or {}
        path_metrics = path_metrics or {}
        mesh_relays = mesh_relays or {}
        mesh_link_health = mesh_link_health or {}

        candidates = self._build_candidates(
            resource_key=resource_key,
            file_paths=list(file_paths or []),
            data_payloads=data_payloads,
            mcp_servers=list(mcp_servers or []),
            https_urls=list(https_urls or []),
        )

        attempt = 0
        while candidates:
            attempt += 1
            selectable = [
                candidate
                for candidate in candidates
                if not self.policies[candidate.channel].is_arrested()
            ]
            if not selectable:
                for channel, policy in self.policies.items():
                    if policy.is_arrested():
                        trace.steps.append({"channel": channel, "path": "", "ok": False, "error": "arrested"})
                break

            scored_candidates = []
            for candidate in selectable:
                metrics = self._candidate_metrics(
                    candidate=candidate,
                    path_metrics=path_metrics,
                    mesh_link_health=mesh_link_health,
                )
                score = self._score_candidate(metrics)
                scored_candidates.append((candidate, score, metrics))

            scored_candidates.sort(key=lambda item: item[1], reverse=True)
            candidate, score, metrics = scored_candidates[0]
            trace.latency_snapshot[candidate.path] = metrics["latency"]
            trace.bandwidth_snapshot[candidate.path] = metrics["bandwidth"]
            trace.multiplexing_decisions.append(
                {
                    "attempt": attempt,
                    "selected_channel": candidate.channel,
                    "selected_path": candidate.path,
                    "score": score,
                    "latency": metrics["latency"],
                    "bandwidth": metrics["bandwidth"],
                    "multiplex_load": metrics["multiplex_load"],
                    "mesh_health": metrics["mesh_health"],
                    "mesh_hops": candidate.mesh_hops,
                }
            )

            started = time.time()
            self.channel_active_load[candidate.channel] += 1.0
            payload, path, err = candidate.resolver()
            elapsed = max(time.time() - started, 0.0001)
            self.channel_active_load[candidate.channel] = max(self.channel_active_load[candidate.channel] - 1.0, 0.0)
            self.channel_latency_ewma[candidate.channel] = (
                0.7 * self.channel_latency_ewma[candidate.channel] + 0.3 * elapsed
            )

            trace.steps.append(
                {
                    "channel": candidate.channel,
                    "path": path or candidate.path,
                    "ok": err is None,
                    "error": err,
                    "score": score,
                    "mesh_hops": candidate.mesh_hops,
                    "latency_seconds": elapsed,
                }
            )

            candidates = [item for item in candidates if item is not candidate]
            if err is None:
                self.policies[candidate.channel].register_success()
                self.channel_bandwidth_estimate[candidate.channel] = max(
                    self.channel_bandwidth_estimate[candidate.channel],
                    1.0 / elapsed,
                )
                trace.close(success=True, channel=candidate.channel, path=path or candidate.path, score=score)
                self.monitor_log.append(trace)
                return payload, trace

            self.policies[candidate.channel].register_failure()
            trace.errors.append(err)
            self.channel_bandwidth_estimate[candidate.channel] = max(
                self.channel_bandwidth_estimate[candidate.channel] * 0.9,
                1.0,
            )
            relay_candidates = self._relay_candidates(candidate, mesh_relays)
            if relay_candidates:
                trace.mesh_failover_events.append(
                    {
                        "attempt": attempt,
                        "failed_channel": candidate.channel,
                        "failed_path": candidate.path,
                        "error": err,
                        "relays": [relay.path for relay in relay_candidates],
                    }
                )
                existing_paths = {item.path for item in candidates}
                candidates.extend([relay for relay in relay_candidates if relay.path not in existing_paths])

        trace.close(success=False)
        self.monitor_log.append(trace)
        raise RuntimeError(f"Failed to resolve {resource_key}; channels exhausted: {trace.errors}")

    def _build_candidates(
        self,
        *,
        resource_key: str,
        file_paths: List[str],
        data_payloads: Dict[str, Any],
        mcp_servers: List[Callable[[str], Any]],
        https_urls: List[str],
    ) -> List[RouteCandidate]:
        candidates: List[RouteCandidate] = []
        for candidate in file_paths:
            path_text = str(candidate)
            candidates.append(
                RouteCandidate(
                    channel="file",
                    path=path_text,
                    resolver=lambda candidate_path=path_text: self._from_single_file(resource_key, candidate_path),
                )
            )
        candidates.append(
            RouteCandidate(
                channel="data",
                path=f"data:{resource_key}",
                resolver=lambda: self._from_data_map(resource_key, data_payloads),
            )
        )
        for index, server in enumerate(mcp_servers):
            candidates.append(
                RouteCandidate(
                    channel="mcp",
                    path=f"mcp:{index}",
                    resolver=lambda mcp_server=server, idx=index: self._from_single_mcp(resource_key, mcp_server, idx),
                )
            )
        for url in https_urls:
            candidates.append(
                RouteCandidate(
                    channel="https",
                    path=url,
                    resolver=lambda source=url: self._from_single_https(source),
                )
            )
        return candidates

    def _candidate_metrics(
        self,
        *,
        candidate: RouteCandidate,
        path_metrics: Dict[str, Dict[str, float]],
        mesh_link_health: Dict[str, float],
    ) -> Dict[str, float]:
        candidate_metrics = path_metrics.get(candidate.path, {})
        channel = candidate.channel
        latency = float(candidate_metrics.get("latency", self.channel_latency_ewma[channel]))
        bandwidth = float(candidate_metrics.get("bandwidth", self.channel_bandwidth_estimate[channel]))
        capacity = max(self.channel_capacity[channel], 1.0)
        multiplex_load = float(
            candidate_metrics.get("multiplex_load", min(self.channel_active_load[channel] / capacity, 1.0))
        )
        mesh_health = float(
            candidate_metrics.get(
                "mesh_health",
                mesh_link_health.get(candidate.path, max(0.0, 1.0 - 0.15 * candidate.mesh_hops)),
            )
        )
        mesh_health = max(0.0, min(mesh_health, 1.0))
        return {
            "latency": max(latency, 0.0001),
            "bandwidth": max(bandwidth, 0.0001),
            "multiplex_load": max(0.0, min(multiplex_load, 1.0)),
            "mesh_health": mesh_health,
        }

    def _score_candidate(self, metrics: Dict[str, float]) -> float:
        latency_score = 1.0 / (1.0 + metrics["latency"])
        bandwidth_score = metrics["bandwidth"] / (metrics["bandwidth"] + 1.0)
        multiplex_score = 1.0 - metrics["multiplex_load"]
        mesh_score = metrics["mesh_health"]
        return (
            self.latency_weight * latency_score
            + self.bandwidth_weight * bandwidth_score
            + self.multiplex_weight * multiplex_score
            + self.mesh_health_weight * mesh_score
        )

    def _relay_candidates(self, failed_candidate: RouteCandidate, mesh_relays: Dict[str, List[str]]) -> List[RouteCandidate]:
        relays = mesh_relays.get(failed_candidate.path, [])
        candidates: List[RouteCandidate] = []
        for relay_url in relays:
            candidates.append(
                RouteCandidate(
                    channel=failed_candidate.channel,
                    path=relay_url,
                    resolver=lambda source=relay_url: self._from_single_https(source),
                    mesh_hops=failed_candidate.mesh_hops + 1,
                    relay_from=failed_candidate.path,
                )
            )
        return candidates

    def _from_single_file(self, resource_key: str, candidate_path: str) -> Tuple[Any, str, Optional[str]]:
        path = Path(candidate_path)
        if not path.is_file():
            return None, str(path), "file_not_found"
        try:
            text = path.read_text(encoding="utf-8")
            return self._decode_payload(resource_key, text), str(path), None
        except OSError as exc:
            return None, str(path), f"file_error:{exc}"

    def _from_data_map(self, resource_key: str, payloads: Dict[str, Any]) -> Tuple[Any, str, Optional[str]]:
        if resource_key not in payloads:
            return None, "", "data_key_missing"
        return payloads[resource_key], f"data:{resource_key}", None

    def _from_single_mcp(
        self,
        resource_key: str,
        server: Callable[[str], Any],
        index: int,
    ) -> Tuple[Any, str, Optional[str]]:
        try:
            payload = server(resource_key)
            if payload is not None:
                return payload, f"mcp:{index}", None
            return None, f"mcp:{index}", "mcp_unavailable"
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("MCP server %s failed for resource %s", index, resource_key)
            return None, f"mcp:{index}", f"mcp_error:{type(exc).__name__}: {exc}"

    def _from_single_https(self, url: str) -> Tuple[Any, str, Optional[str]]:
        try:
            payload = self._read_https_source(url)
            return payload, url, None
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("HTTPS source failed for url %s", url)
            return None, url, f"https_error:{type(exc).__name__}: {exc}"

    def _read_https_source(self, url: str) -> Any:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            raise ValueError(f"unsupported_url_scheme:{parsed.scheme}")
        with urllib.request.urlopen(url, timeout=self.https_timeout_seconds) as response:
            text = response.read().decode("utf-8")
        return self._decode_payload(url, text)

    def _decode_payload(self, resource_key: str, text: str) -> Any:
        if resource_key.endswith(".json"):
            return json.loads(text)
        return text
