# Protocol Logic and Orchestration Procedures

This repository now includes a chained orchestration workflow in:

- `/home/runner/work/NiA-Pegasus-Core/NiA-Pegasus-Core/protocol_orchestration.py`

## Workflow chain

`ProtocolWorkflowOrchestrator.resolve_resource(...)` evaluates resource acquisition in this order:

1. file paths (`file_paths`)
2. in-memory/data payload map (`data_payloads`)
3. MCP server callables (`mcp_servers`)
4. HTTPS URLs (`https_urls`)

Each channel is monitored and recorded in `OrchestrationTrace` with:

- selected channel/path
- per-step success/failure
- errors
- start/end timestamps

## Arrest procedures (circuit breaker)

Each channel has an independent arrest policy (`CircuitArrestPolicy`):

- `max_failures`
- `cooldown_seconds`
- failure count and arrest window tracking

After repeated failures, a channel is temporarily arrested and skipped until cooldown expires.

## Runtime integration

`QuantumRoboticController` includes:

- `self.protocol_orchestrator`
- `orchestrate_protocol_resource(...)`
- `self.workflow_monitor_log` for monitored workflow events

This provides aligned protocol orchestration with fallback paths to the same resource across file/data/MCP/HTTPS inputs.
