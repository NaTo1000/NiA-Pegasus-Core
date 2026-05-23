import json
import subprocess
import sys
from pathlib import Path


def _sample(i: int) -> dict:
    return {
        "timestamp": float(i),
        "domain": "A" if i % 3 else "B",
        "signal_proxy_uncertainty_index": min(1.0, 0.1 + 0.02 * (i % 10)),
        "recursive_coherence_surge_index": min(1.0, 0.2 + 0.03 * (i % 15)),
        "choice_pressure": min(1.0, 0.2 + 0.025 * (i % 12)),
        "indecision": min(1.0, 0.15 + 0.02 * (i % 11)),
        "environmental_turbulence": min(1.0, 0.1 + 0.03 * (i % 10)),
        "label_surge": 1 if (i % 7 in (0, 1, 2)) else 0,
        "label_immediate": 1 if (i % 5 in (0, 1)) else 0,
    }


def test_pipeline_exports_governed_artifact(tmp_path):
    repo_root = Path("/home/runner/work/NiA-Pegasus-Core/NiA-Pegasus-Core")
    input_path = tmp_path / "samples.json"
    output_path = tmp_path / "artifact.json"
    input_path.write_text(json.dumps([_sample(i) for i in range(60)]), encoding="utf-8")

    script = repo_root / "tools" / "intent_calibration_pipeline.py"
    cmd = [sys.executable, str(script), "--input", str(input_path), "--output", str(output_path)]
    subprocess.run(cmd, check=True)

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["version"].startswith("intent-runtime-v")
    split_counts = artifact["calibration_context"]["split_counts"]
    assert split_counts["train"] > 0
    assert split_counts["validation"] > 0
    assert split_counts["test"] > 0
    assert split_counts["temporal_holdout"] > 0
    assert split_counts["domain_shift_holdout"] > 0
    assert "gate_checks" in artifact["evaluation"]
    assert isinstance(artifact["evaluation"]["all_gates_passed"], bool)
