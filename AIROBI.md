# Aierioub (AiRobI)

**AiRobI** = **Ai error research innovation output update batches**.

Module: `aieroub_airobi.py`

## Purpose

AiRobI continuously converts error return codes into researched innovation update batches with sandbox-first validation.

## Process chain

1. Ingest `ErrorReturnSignal` inputs.
2. Classify each error code to a research topic.
3. Gather research context through orchestrated fallback channels:
   - file paths
   - data payload maps
   - MCP server callables
   - HTTPS URLs
4. Generate update recommendations.
5. Run sandbox tests (`sandbox_test_update`) before rollout.

## Continuous update mode

`AiRobI.run_continuous(...)` supports repeated update cycles fed by an async error source.

## Core safety controls

- Chained fallback acquisition provided by `ProtocolWorkflowOrchestrator`.
- Arrest/circuit-breaker behavior per channel to prevent repeated unstable paths.
- Batch and sandbox logs for traceability.
