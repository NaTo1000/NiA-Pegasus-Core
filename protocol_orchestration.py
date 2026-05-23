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
    steps: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    success: bool = False

    def close(self, success: bool, channel: str = "none", path: str = "") -> None:
        self.success = success
        self.selected_channel = channel
        self.selected_path = path
        self.ended_at = time.time()


class ProtocolWorkflowOrchestrator:
    """Chains multiple data acquisition paths with monitoring and arrest safeguards."""

    def __init__(
        self,
        *,
        max_failures: int = 3,
        cooldown_seconds: float = 30.0,
        https_timeout_seconds: float = 3.0,
    ):
        self.https_timeout_seconds = https_timeout_seconds
        self.policies = {
            "file": CircuitArrestPolicy(max_failures=max_failures, cooldown_seconds=cooldown_seconds),
            "data": CircuitArrestPolicy(max_failures=max_failures, cooldown_seconds=cooldown_seconds),
            "mcp": CircuitArrestPolicy(max_failures=max_failures, cooldown_seconds=cooldown_seconds),
            "https": CircuitArrestPolicy(max_failures=max_failures, cooldown_seconds=cooldown_seconds),
        }
        self.monitor_log: List[OrchestrationTrace] = []

    def resolve_resource(
        self,
        *,
        resource_key: str,
        file_paths: Optional[Iterable[str]] = None,
        data_payloads: Optional[Dict[str, Any]] = None,
        mcp_servers: Optional[Iterable[Callable[[str], Any]]] = None,
        https_urls: Optional[Iterable[str]] = None,
    ) -> Tuple[Any, OrchestrationTrace]:
        """Resolve a resource through chained channels with arrest controls."""
        trace = OrchestrationTrace(resource_key=resource_key, started_at=time.time())
        data_payloads = data_payloads or {}

        # 1) File-system fallback paths
        if not self.policies["file"].is_arrested():
            payload, path, err = self._from_files(resource_key, list(file_paths or []))
            trace.steps.append({"channel": "file", "path": path, "ok": err is None, "error": err})
            if err is None:
                self.policies["file"].register_success()
                trace.close(success=True, channel="file", path=path)
                self.monitor_log.append(trace)
                return payload, trace
            self.policies["file"].register_failure()
            trace.errors.append(err)
        else:
            trace.steps.append({"channel": "file", "path": "", "ok": False, "error": "arrested"})

        # 2) In-memory / provided data maps
        if not self.policies["data"].is_arrested():
            payload, path, err = self._from_data_map(resource_key, data_payloads)
            trace.steps.append({"channel": "data", "path": path, "ok": err is None, "error": err})
            if err is None:
                self.policies["data"].register_success()
                trace.close(success=True, channel="data", path=path)
                self.monitor_log.append(trace)
                return payload, trace
            self.policies["data"].register_failure()
            trace.errors.append(err)
        else:
            trace.steps.append({"channel": "data", "path": "", "ok": False, "error": "arrested"})

        # 3) MCP server callable chain
        if not self.policies["mcp"].is_arrested():
            payload, path, err = self._from_mcp(resource_key, list(mcp_servers or []))
            trace.steps.append({"channel": "mcp", "path": path, "ok": err is None, "error": err})
            if err is None:
                self.policies["mcp"].register_success()
                trace.close(success=True, channel="mcp", path=path)
                self.monitor_log.append(trace)
                return payload, trace
            self.policies["mcp"].register_failure()
            trace.errors.append(err)
        else:
            trace.steps.append({"channel": "mcp", "path": "", "ok": False, "error": "arrested"})

        # 4) HTTPS fallback chain
        if not self.policies["https"].is_arrested():
            payload, path, err = self._from_https(list(https_urls or []))
            trace.steps.append({"channel": "https", "path": path, "ok": err is None, "error": err})
            if err is None:
                self.policies["https"].register_success()
                trace.close(success=True, channel="https", path=path)
                self.monitor_log.append(trace)
                return payload, trace
            self.policies["https"].register_failure()
            trace.errors.append(err)
        else:
            trace.steps.append({"channel": "https", "path": "", "ok": False, "error": "arrested"})

        trace.close(success=False)
        self.monitor_log.append(trace)
        raise RuntimeError(f"Failed to resolve {resource_key}; channels exhausted: {trace.errors}")

    def _from_files(self, resource_key: str, file_paths: List[str]) -> Tuple[Any, str, Optional[str]]:
        for candidate in file_paths:
            path = Path(candidate)
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
                return self._decode_payload(resource_key, text), str(path), None
            except OSError as exc:
                return None, str(path), f"file_error:{exc}"
        return None, "", "file_not_found"

    def _from_data_map(self, resource_key: str, payloads: Dict[str, Any]) -> Tuple[Any, str, Optional[str]]:
        if resource_key not in payloads:
            return None, "", "data_key_missing"
        return payloads[resource_key], f"data:{resource_key}", None

    def _from_mcp(
        self,
        resource_key: str,
        servers: List[Callable[[str], Any]],
    ) -> Tuple[Any, str, Optional[str]]:
        for index, server in enumerate(servers):
            try:
                payload = server(resource_key)
                if payload is not None:
                    return payload, f"mcp:{index}", None
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("MCP server %s failed for resource %s", index, resource_key)
                return None, f"mcp:{index}", f"mcp_error:{type(exc).__name__}: {exc}"
        return None, "", "mcp_unavailable"

    def _from_https(self, urls: List[str]) -> Tuple[Any, str, Optional[str]]:
        for url in urls:
            try:
                payload = self._read_https_source(url)
                return payload, url, None
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("HTTPS source failed for url %s", url)
                return None, url, f"https_error:{type(exc).__name__}: {exc}"
        return None, "", "https_unavailable"

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
