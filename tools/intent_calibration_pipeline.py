#!/usr/bin/env python3
"""Offline calibration/evaluation pipeline for intent runtime artifacts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


@dataclass
class CalibrationSample:
    timestamp: float
    domain: str
    signal_proxy_uncertainty_index: float
    recursive_coherence_surge_index: float
    choice_pressure: float
    indecision: float
    environmental_turbulence: float
    label_surge: int
    label_immediate: int


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return float(np.clip(numeric, 0.0, 1.0))


def load_samples(path: Path) -> List[CalibrationSample]:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    samples = []
    for row in raw:
        samples.append(
            CalibrationSample(
                timestamp=float(row.get("timestamp", 0.0)),
                domain=str(row.get("domain", "unknown")),
                signal_proxy_uncertainty_index=_to_float(row.get("signal_proxy_uncertainty_index", 0.5)),
                recursive_coherence_surge_index=_to_float(row.get("recursive_coherence_surge_index", 0.0)),
                choice_pressure=_to_float(row.get("choice_pressure", 0.0)),
                indecision=_to_float(row.get("indecision", 0.0)),
                environmental_turbulence=_to_float(row.get("environmental_turbulence", 0.0)),
                label_surge=int(row.get("label_surge", 0)),
                label_immediate=int(row.get("label_immediate", 0)),
            )
        )
    return samples


def split_governance(samples: List[CalibrationSample]) -> Dict[str, List[CalibrationSample]]:
    ordered = sorted(samples, key=lambda sample: sample.timestamp)
    n = len(ordered)
    train_end = max(1, int(n * 0.6))
    val_end = max(train_end + 1, int(n * 0.8))
    train = ordered[:train_end]
    val = ordered[train_end:val_end]
    test = ordered[val_end:]

    # Temporal holdout: last 15% by time.
    temporal_start = max(0, int(n * 0.85))
    temporal_holdout = ordered[temporal_start:]

    # Domain-shift holdout: least frequent domain.
    domain_counts: Dict[str, int] = {}
    for sample in ordered:
        domain_counts[sample.domain] = domain_counts.get(sample.domain, 0) + 1
    holdout_domain = min(domain_counts.items(), key=lambda item: item[1])[0] if domain_counts else "unknown"
    domain_shift_holdout = [sample for sample in ordered if sample.domain == holdout_domain]

    return {
        "train": train,
        "validation": val,
        "test": test,
        "temporal_holdout": temporal_holdout,
        "domain_shift_holdout": domain_shift_holdout,
    }


def _best_threshold(scores: np.ndarray, labels: np.ndarray) -> float:
    if scores.size == 0:
        return 0.5
    candidates = np.unique(scores)
    best_thr = 0.5
    best_f1 = -1.0
    for thr in candidates:
        pred = (scores >= thr).astype(int)
        tp = int(np.sum((pred == 1) & (labels == 1)))
        fp = int(np.sum((pred == 1) & (labels == 0)))
        fn = int(np.sum((pred == 0) & (labels == 1)))
        precision = tp / (tp + fp + 1e-9)
        recall = tp / (tp + fn + 1e-9)
        f1 = 2 * precision * recall / (precision + recall + 1e-9)
        if f1 > best_f1:
            best_f1 = f1
            best_thr = float(thr)
    return float(best_thr)


def _ece(scores: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    if scores.size == 0:
        return 1.0
    ece = 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    for i in range(bins):
        mask = (scores >= edges[i]) & (scores < edges[i + 1] if i < bins - 1 else scores <= edges[i + 1])
        if not np.any(mask):
            continue
        conf = float(np.mean(scores[mask]))
        acc = float(np.mean(labels[mask]))
        ece += float(np.mean(mask)) * abs(conf - acc)
    return float(ece)


def _metrics(scores: np.ndarray, labels: np.ndarray, threshold: float) -> Dict[str, float]:
    pred = (scores >= threshold).astype(int)
    tp = int(np.sum((pred == 1) & (labels == 1)))
    tn = int(np.sum((pred == 0) & (labels == 0)))
    fp = int(np.sum((pred == 1) & (labels == 0)))
    fn = int(np.sum((pred == 0) & (labels == 1)))
    precision = tp / (tp + fp + 1e-9)
    recall = tp / (tp + fn + 1e-9)
    f1 = 2 * precision * recall / (precision + recall + 1e-9)
    false_alarm_rate = fp / (fp + tn + 1e-9)
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "false_alarm_rate": float(false_alarm_rate),
        "expected_calibration_error": _ece(scores, labels),
    }


def calibrate(samples: Dict[str, List[CalibrationSample]]) -> Dict[str, Any]:
    train = samples["train"]
    val = samples["validation"]
    test = samples["test"]
    temporal_holdout = samples["temporal_holdout"]
    domain_shift_holdout = samples["domain_shift_holdout"]

    train_surge_scores = np.array([s.recursive_coherence_surge_index for s in train], dtype=float)
    train_surge_labels = np.array([s.label_surge for s in train], dtype=int)
    val_surge_scores = np.array([s.recursive_coherence_surge_index for s in val], dtype=float)
    val_surge_labels = np.array([s.label_surge for s in val], dtype=int)
    test_surge_scores = np.array([s.recursive_coherence_surge_index for s in test], dtype=float)
    test_surge_labels = np.array([s.label_surge for s in test], dtype=int)

    surge_threshold = _best_threshold(val_surge_scores, val_surge_labels)

    # Prevent tuning on test by freezing threshold before test evaluation.
    val_metrics = _metrics(val_surge_scores, val_surge_labels, surge_threshold)
    test_metrics = _metrics(test_surge_scores, test_surge_labels, surge_threshold)

    temporal_scores = np.array([s.recursive_coherence_surge_index for s in temporal_holdout], dtype=float)
    domain_scores = np.array([s.recursive_coherence_surge_index for s in domain_shift_holdout], dtype=float)
    temporal_drift_std = float(abs(np.std(test_surge_scores) - np.std(temporal_scores)))
    robustness_delta = float(abs(np.mean(test_surge_scores) - np.mean(domain_scores)))

    immediate_threshold = _best_threshold(
        np.array([s.choice_pressure for s in val], dtype=float),
        np.array([s.label_immediate for s in val], dtype=int),
    )

    pressure_mean = float(np.mean([s.choice_pressure for s in train])) if train else 0.0
    indecision_mean = float(np.mean([s.indecision for s in train])) if train else 0.0
    turbulence_mean = float(np.mean([s.environmental_turbulence for s in train])) if train else 0.0

    return {
        "version": "intent-runtime-v1.0.0",
        "calibration_context": {
            "source_dataset": "offline_labeled_dataset",
            "sampling_reference_hz": 50.0,
            "split_counts": {k: len(v) for k, v in samples.items()},
        },
        "routing_thresholds": {
            "immediate_pressure_threshold": immediate_threshold,
            "near_term_pressure_threshold": max(0.1, immediate_threshold * 0.55),
            "high_indecision_threshold": float(np.clip(indecision_mean + 0.2, 0.0, 1.0)),
            "high_environmental_turbulence_threshold": float(np.clip(turbulence_mean + 0.2, 0.0, 1.0)),
            "high_proxy_uncertainty_threshold": 0.7,
            "high_data_quality_risk_threshold": 0.4,
            "low_confidence_threshold": 0.35,
            "focus_detection_threshold": 0.2,
            "constrained_decision_pressure_threshold": float(np.clip(pressure_mean + 0.15, 0.0, 1.0)),
            "exponential_surge_threshold": surge_threshold,
            "max_intent_reasons": 2,
        },
        "acceptance_gates": {
            "max_expected_calibration_error": 0.05,
            "min_precision": 0.75,
            "min_recall": 0.75,
            "min_f1": 0.75,
            "max_false_alarm_rate": 0.1,
            "max_temporal_drift_std": 0.1,
            "max_noise_dropout_robustness_delta": 0.15,
        },
        "evaluation": {
            "validation": val_metrics,
            "test": test_metrics,
            "temporal_drift_std": temporal_drift_std,
            "noise_dropout_robustness_delta": robustness_delta,
        },
    }


def evaluate_gates(artifact: Dict[str, Any]) -> Tuple[bool, Dict[str, bool]]:
    gates = artifact.get("acceptance_gates", {})
    test = artifact.get("evaluation", {}).get("test", {})
    checks = {
        "ece": float(test.get("expected_calibration_error", 1.0)) <= float(gates.get("max_expected_calibration_error", 0.05)),
        "precision": float(test.get("precision", 0.0)) >= float(gates.get("min_precision", 0.75)),
        "recall": float(test.get("recall", 0.0)) >= float(gates.get("min_recall", 0.75)),
        "f1": float(test.get("f1", 0.0)) >= float(gates.get("min_f1", 0.75)),
        "far": float(test.get("false_alarm_rate", 1.0)) <= float(gates.get("max_false_alarm_rate", 0.1)),
        "drift": float(artifact.get("evaluation", {}).get("temporal_drift_std", 1.0)) <= float(gates.get("max_temporal_drift_std", 0.1)),
        "robustness": float(artifact.get("evaluation", {}).get("noise_dropout_robustness_delta", 1.0))
        <= float(gates.get("max_noise_dropout_robustness_delta", 0.15)),
    }
    return bool(all(checks.values())), checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate intent runtime thresholds from labeled data.")
    parser.add_argument("--input", required=True, help="Path to JSON array of labeled samples.")
    parser.add_argument("--output", required=True, help="Output artifact path.")
    args = parser.parse_args()

    samples = load_samples(Path(args.input))
    if len(samples) < 20:
        raise SystemExit("Need at least 20 labeled samples for governed splits.")
    split = split_governance(samples)
    artifact = calibrate(split)
    passed, checks = evaluate_gates(artifact)
    artifact["evaluation"]["gate_checks"] = checks
    artifact["evaluation"]["all_gates_passed"] = passed

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    print(f"wrote artifact: {output_path}")
    print(f"all_gates_passed={passed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
