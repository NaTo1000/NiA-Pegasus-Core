import json
import os
import sys
import types
from importlib import import_module


def _load_module():
    if "quantum_computing" not in sys.modules:
        sys.modules["quantum_computing"] = types.SimpleNamespace()
    return import_module("quantum_consciousness_core")


def _engine(dimension=32):
    module = _load_module()
    return module.SyntheticConsciousness(dimension=dimension)


def test_loads_external_calibration_artifact(tmp_path):
    module = _load_module()
    calibration_path = tmp_path / "intent_calibration.json"
    artifact = {
        "version": "intent-runtime-v9.9.9",
        "routing_thresholds": {"exponential_surge_threshold": 0.91},
    }
    calibration_path.write_text(json.dumps(artifact), encoding="utf-8")
    os.environ["NIA_INTENT_CALIBRATION_PATH"] = str(calibration_path)
    try:
        engine = module.SyntheticConsciousness(dimension=32)
    finally:
        os.environ.pop("NIA_INTENT_CALIBRATION_PATH", None)
    assert engine.intent_calibration_version == "intent-runtime-v9.9.9"
    assert engine.intent_calibration["routing_thresholds"]["exponential_surge_threshold"] == 0.91


def test_structured_sensory_contract_produces_quality_metrics():
    engine = _engine()
    memories = [
        {
            "sensory_data": {
                "sensor_type": "audio",
                "units": "Pa",
                "cadence_hz": 50.0,
                "quality_flags": [],
                "missing_data_policy": "drop",
                "values": [0.1, 0.12, 0.08, 0.11, 0.09, 0.1],
            }
        },
        {
            "sensory_data": {
                "sensor_type": "audio",
                "units": "Pa",
                "cadence_hz": 48.0,
                "quality_flags": ["noisy"],
                "missing_data_policy": "impute_zero",
                "values": [0.2, 0.18, None, 0.19, 0.17, 0.2],
            }
        },
    ]
    factors = engine._compute_sensory_biological_proxies(memories)
    assert factors["contract_valid_samples"] >= 1.0
    assert 0.0 <= factors["input_data_quality_risk"] <= 1.0
    assert 0.0 <= factors["proxy_confidence_index"] <= 1.0
    assert "signal_geometry_index" in factors
    # Backward compatibility
    assert factors["fingerprint_geometry_proxy"] == factors["signal_geometry_index"]


def test_uncertainty_guardrail_routes_to_fail_safe():
    engine = _engine()
    human_intent = engine._compose_human_intent_logic(
        intentions=[],
        micro_signals={},
        decision_state={"choice_pressure": 0.1, "indecision": 0.2},
        affective_landscape={"grief_of_loss": 0.0, "joy_of_love": 0.0},
        environmental_dynamics={"environmental_turbulence": 0.1},
        behavioral_fluidity={"overall_fidget_index": 0.1},
        biological_factors={
            "signal_proxy_uncertainty_index": 0.9,
            "input_data_quality_risk": 0.9,
            "proxy_confidence_index": 0.1,
            "recursive_coherence_surge_index": 0.95,
        },
        distress_state={"desperation_index": 0.1, "psychological_overload_risk": 0.1, "paranoia_hypervigilance": 0.1},
    )
    assert human_intent["when"] == "data_quality_guardrail"
    assert human_intent["how"] == "defer_and_collect_more_data"
    assert "traceability" in human_intent
    assert human_intent["traceability"]["calibration_version"].startswith("intent-runtime-v")
