# Intent Metrics Calibration and Data Contract

This document defines the runtime metric contract for `quantum_consciousness_core.py` and the offline calibration workflow used to export `calibration/intent_runtime_calibration.v1.json`.

## 1) Sensory data contract (`sensory_data`)

Runtime accepts:

1. **Preferred structured contract (data-driven path)**
   ```json
   {
     "sensor_type": "audio|motion|optical|temperature|generic",
     "units": "Pa|m_s2|lux|celsius|normalized",
     "cadence_hz": 50.0,
     "quality_flags": ["saturated", "noisy"],
     "missing_data_policy": "drop|impute_zero|forward_fill",
     "values": [ ... numeric samples ... ]
   }
   ```
2. **Legacy unstructured array** (backward-compatible fallback; treated as lower confidence).

Contract policies:
- Required fields are enforced for structured payloads.
- Sensor type to unit matching is enforced.
- Missing-data policy is enforced.
- Unit normalization is applied from calibration artifact.
- Cadence and quality flags contribute to `input_data_quality_risk`.

## 2) Runtime metric map

All indices are in `[0,1]`.

| Runtime metric | Source signal | Unit before normalization | Normalization | Dataset source | Validation metric(s) | Operational limit |
|---|---|---|---|---|---|---|
| `signal_geometry_index` | spatial delta variability | contract unit by sensor | artifact unit offset/scale | offline labeled dataset | ECE, F1 | clipped `[0,1]` |
| `temporal_drift_index` | temporal acceleration magnitude | normalized | bounded mean abs acceleration | offline labeled dataset | ECE, FAR | clipped `[0,1]` |
| `positive_flux_index` | positive envelope trend | normalized | bounded mean positive diff | offline labeled dataset | precision/recall | clipped `[0,1]` |
| `rhythmic_coherence_index` | autocorrelation peak ratio | normalized | bounded ratio | offline labeled dataset | F1, FAR | clipped `[0,1]` |
| `pulse_stability_index` | 2nd-order envelope stability | normalized | `1/(1+std)` | offline labeled dataset | F1 | clipped `[0,1]` |
| `high_frequency_response_index` | high-band spectral dispersion | normalized | bounded ratio | offline labeled dataset | FAR | clipped `[0,1]` |
| `smooth_homeostasis_index` | smoothed envelope stability | normalized | `1/(1+std)` | offline labeled dataset | ECE | clipped `[0,1]` |
| `binary_signature_depth_index` | temporal/spatial/recursive binary coherence | normalized binary signature | calibrated weighted blend | offline labeled dataset | ECE, temporal drift | clipped `[0,1]` |
| `recursive_coherence_surge_index` | recursive coherence + bounded std boost | normalized binary signature | bounded boosted mean | offline labeled dataset | precision/recall/F1 | clipped `[0,1]` |
| `signal_proxy_uncertainty_index` | inverse weighted proxy composite | n/a | `1-composite` | offline labeled dataset | ECE | clipped `[0,1]` |
| `input_data_quality_risk` | cadence, quality flags, missing ratio | Hz + quality flags + ratio | weighted quality aggregate | offline labeled dataset | FAR | clipped `[0,1]` |
| `proxy_confidence_index` | uncertainty-quality fused confidence | n/a | `1-max(uncertainty,risk)` | offline labeled dataset | calibration + FAR | clipped `[0,1]` |

## 3) Offline calibration/evaluation pipeline

Script: `<repo_root>/tools/intent_calibration_pipeline.py`

Usage:
```bash
python <repo_root>/tools/intent_calibration_pipeline.py \
  --input /absolute/path/labeled_intent_samples.json \
  --output <repo_root>/calibration/intent_runtime_calibration.v1.json
```

Pipeline guarantees:
- Governed split strategy:
  - train/validation/test by timestamp order
  - temporal holdout (latest segment)
  - domain-shift holdout (least-frequent domain)
- Threshold tuning only on validation split.
- Test split only for evaluation.
- Exported artifact includes threshold values and evaluation summary.

## 4) Acceptance gates

Configured in artifact:
- max expected calibration error <= 0.05
- min precision/recall/F1 >= 0.75
- max false alarm rate <= 0.10
- max temporal drift std <= 0.10
- max robustness delta under domain/noise/dropout <= 0.15

Runtime routing should use fail-safe behavior when confidence/quality are poor:
- `when = data_quality_guardrail`
- `how = defer_and_collect_more_data`

## 5) Traceability per inference cycle

Runtime `human_intent.traceability` includes:
- calibration version
- threshold values used
- key routed inputs (pressure, indecision, turbulence, uncertainty, quality risk, confidence)
- rationale list describing route decisions
