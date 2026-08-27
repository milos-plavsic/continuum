# Workflow-engine companion boundary

Continuum complements a durable workflow engine; it does not replace one. A
workflow engine answers **when a task should run and be retried**. Continuum
answers **what promise survives when the permitted agent changes**.

| Concern | Host workflow engine | Continuum |
|---|---:|---:|
| Schedule, timer and retry a task | Owns | Observes |
| Persist task-local workflow state | Owns | Does not duplicate |
| Preserve the institutional obligation | Supplies task facts | Owns append-only obligation |
| Decide which agent may act now | Calls boundary | Owns epoch-fenced authority |
| Decide which memory may cross replacement | Does not infer | Owns purpose-bound reconstruction |
| Deduplicate the external effect | Supplies stable task identity | Enforces semantic idempotency |
| Attest the completed handoff | Supplies provider observation | Independent verifier owns verdict |

The first-party adapter in `continuum.workflow_bridge` maps an ordinary engine
task to the portable three-call SDK. The engine retains its domain model and
retry semantics. A stable task ID becomes the obligation ID; a digest of the
task's semantic content becomes the idempotency key, so redelivery converges
while a changed payload under the same task ID is denied.

```python
from continuum.workflow_bridge import WorkflowEngineBridge, WorkflowTask

binding = bridge.bind(WorkflowTask(
    engine="temporal", namespace="procurement", workflow_id="onboard-42",
    task_id="create-vendor", tenant_id="acme", owner_principal="agent:v19",
    capability="vendor.create", payload={"vendor_id": "vendor-042"}, attempt=3,
))
result = bridge.complete(binding)
```

Run `uv run python examples/workflow_engine_companion.py` for a credential-free
example. This is a first-party interoperability surface, not a claim that
Temporal, Camunda, Airflow, or another vendor has adopted the draft protocol.

## Why retry, DLQ and leader election are insufficient

Those mechanisms remain necessary. They recover execution mechanics, but they
do not by themselves prove four separate facts across executor replacement:

1. **What promise remains open?** An obligation outlives a worker and its queue.
2. **Who may act now?** Authority moves by monotonic epoch and the predecessor is fenced.
3. **What context may cross?** Only purpose-bound verified facts are reconstructed.
4. **Who verifies the effect?** A separate reader, not the executor, issues the verdict.

Continuum begins where ordinary workflow recovery ends: at the change of agent
identity, authority and memory trust.
