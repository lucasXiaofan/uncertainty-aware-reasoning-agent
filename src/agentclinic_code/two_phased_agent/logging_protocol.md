# Multi-Agent Logging Protocol and Visualization Plan

## 1. Purpose

This protocol defines what the AgentClinic two-phase doctor must log so one
task run can be visualized without reverse-engineering prompts, tool calls, or
working-memory state from loosely related files.

The current runtime has two logical agents:

1. `information_seeking`: invoked for turns 1 through 9.
2. `differential_diagnosis`: invoked for turn 10.

The protocol is designed for more agents and different orchestration policies.
The UI is intentionally replaceable. The logged identities, boundaries,
causal links, inputs, outputs, and artifacts are the stable contract.

## 2. Current-System Findings

The relevant ownership boundaries are:

- `agentclinic_api_only.py` owns the complete patient/scenario task, the
  patient and measurement responses, correctness evaluation, and final result.
- `two_agent_interface.py` owns doctor-agent selection, the 9+1 execution
  sequence, OSCE-note handoff, differential handoff, and doctor output.
- `agent.py` owns one agent invocation's internal LLM/tool loop.
- `logging.py` currently records low-level events and usage for one `Agent`
  runner.
- `working_memory.py` owns plan, OSCE-note, and evidence state.
- `tool_calling.py` owns tool execution and has access to tool inputs/results.

The current trajectory is not a sufficient protocol because it:

- does not model a task containing multiple logical agents;
- conflates an AgentClinic inference, an agent invocation, and an LLM round;
- does not assign stable IDs to agents, invocations, rounds, or tool calls;
- does not explicitly store resolved agent instructions and available tools;
- relies on repeated raw message arrays to infer invocation inputs;
- mutates/deduplicates raw events, which loses exact round context;
- does not make OSCE notes and evidence first-class task results;
- can overwrite the same low-level log path across invocations;
- has no standard representation for image files versus embedded base64 data;
- has no protocol version or migration boundary.

The legacy `two_phased_agent/trajectory` files should not be migrated in place.
New runs should use the protocol below.

## 3. Visualization Hierarchy

The persisted task root is not counted as one of the requested three agent
levels. It provides task metadata and highlighted results.

### Task Root

One patient/scenario run. It contains the objective, orchestration plan,
completion status, final diagnosis, correctness when available, aggregate
usage, agent executions, and highlighted task results.

### Level 1: Logical Agent

One card per configured agent type, for example `information_seeking` and
`differential_diagnosis`.

Collapsed view:

- agent type and display name;
- model;
- invocation count and sequence range;
- short instruction summary;
- initial input summary;
- final output summary;
- aggregate usage/status.

Expanded view:

- complete resolved instruction, prompt source, and prompt hash;
- available tool definitions or tool names plus schema hashes;
- orchestration position;
- ordered invocation/turn cards.

### Level 2: Agent Invocation / Turn

One call to `Agent.run()`. In the current workflow there are nine information
seeking invocations and one differential diagnosis invocation.

Collapsed view:

- global sequence number and agent-local sequence number;
- input source (`patient`, `measurement`, `orchestrator`, or mixed);
- visible input summary;
- final output and terminal action;
- number of LLM rounds;
- tool names called, without tool results;
- duration and usage.

Expanded view:

- exact invocation input;
- memory/state references before and after;
- execution summary in sequential order;
- ordered LLM round cards.

Tool results remain hidden at this level. A turn may say
`update_osce_note -> respond`, but result payloads belong to Level 3.

### Level 3: LLM Round

One model request and response inside an invocation. A single invocation can
contain multiple rounds because memory updates and non-terminal tool calls feed
results back to the model.

Collapsed view:

- round number;
- model response summary;
- tool names and statuses;
- usage, duration, and retry count.

Expanded view:

- complete normalized model input for this round, including messages from
  previous rounds and previous tool results;
- assistant content and raw structured tool calls;
- each tool's parsed input and full result when available;
- errors/retries;
- memory changes caused by the round;
- image artifact references, directory, and decode status.

No base64 image payload is rendered or copied into the materialized log.

## 4. Storage Layout

Use one directory per task run:

```text
logs/agentclinic/<run_id>/
  events.v1.jsonl
  run.v1.json
  artifacts/
    images/
    tool-results/
```

- `events.v1.jsonl` is the canonical append-only record. Write one complete
  event per line and flush after each event.
- `run.v1.json` is a replaceable materialized projection for visualization and
  analysis. Build it from the event stream incrementally or at task end.
- `artifacts/` stores large or binary values. The JSON logs contain metadata
  and relative paths, never image bytes.

Atomic projection writes should use `run.v1.json.tmp` followed by rename.

## 5. Common Types

### 5.1 IDs

All IDs are strings and unique within their scope:

```text
run_id        run_<uuid-or-sortable-id>
agent_id      agent_information_seeking
invocation_id inv_0001
round_id      inv_0001_round_01
tool_call_id  model-provided ID, or generated tc_<id>
artifact_id   artifact_<id>
highlight_id  highlight_<id>
event_id      evt_<sortable-id>
```

Every child stores its parent IDs. Sequence numbers are one-based and must not
be used as identity.

### 5.2 Timestamp, Status, and Usage

All timestamps use UTC ISO 8601. Durations use integer milliseconds.

Allowed statuses:

```text
pending | running | completed | failed | cancelled | incomplete
```

Usage shape:

```json
{
  "input_tokens": 0,
  "cached_input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0,
  "expense_usd": 0.0
}
```

Unknown values are `null`, not omitted or replaced with zero.

### 5.3 Content

Inputs and outputs use normalized content parts:

```json
[
  {"type": "text", "text": "Hospital response..."},
  {"type": "image_ref", "artifact_id": "artifact_image_01"}
]
```

Plain text can additionally have `text` for display convenience, but
`content_parts` is authoritative when multimodal content exists.

## 6. Canonical Event Protocol

Every JSONL line uses this envelope:

```json
{
  "protocol": "agent-observability",
  "protocol_version": "1.0.0",
  "event_id": "evt_...",
  "event_type": "round.completed",
  "timestamp": "2026-06-13T18:00:00.000Z",
  "run_id": "run_...",
  "agent_id": "agent_information_seeking",
  "invocation_id": "inv_0001",
  "round_id": "inv_0001_round_01",
  "sequence": 12,
  "payload": {}
}
```

Only IDs applicable to an event are required. `sequence` is monotonically
increasing across the task and provides deterministic ordering.

Required event types:

| Event | Emitted by | Required payload |
|---|---|---|
| `task.started` | AgentClinic runner | task metadata, objective, orchestration plan |
| `agent.registered` | two-agent interface | type, model, instruction, tools |
| `invocation.started` | two-agent interface | sequence, input, state-before refs |
| `round.started` | `Agent.run` | round sequence, exact normalized input |
| `llm.completed` | `Agent.run` | assistant response, usage, latency |
| `tool.started` | tool loop | call ID, name, parsed arguments |
| `tool.completed` | tool loop | call ID, result/ref, status, latency |
| `memory.updated` | working memory | memory type, operation, before/after or patch |
| `round.completed` | `Agent.run` | status, summary, usage |
| `invocation.completed` | two-agent interface | final output, terminal action, usage |
| `highlight.upserted` | two-agent interface | typed highlight payload |
| `environment.completed` | AgentClinic runner | patient/measurement input and output |
| `task.completed` | AgentClinic runner | diagnosis, correctness, aggregate usage |
| `error.recorded` | any layer | scope, error type/message, retryable |

An LLM call retry should emit `error.recorded` and remain inside the same
round. A new successful model request after a tool result is a new round.

## 7. Materialized `run.v1.json`

The UI reads the following top-level structure:

```json
{
  "protocol": "agent-observability",
  "protocol_version": "1.0.0",
  "run": {},
  "orchestration": {},
  "highlights": [],
  "agents": [],
  "artifacts": [],
  "metrics": {},
  "errors": []
}
```

### 7.1 `run`

Required properties:

| Property | Meaning |
|---|---|
| `run_id` | Stable task identity |
| `task_type` | `agentclinic_patient_run` |
| `dataset` | Dataset name |
| `scenario_id` | Dataset scenario identity |
| `objective` | Doctor-visible task input |
| `status` | Task status |
| `started_at`, `ended_at`, `duration_ms` | Timing |
| `final_output` | Final displayed diagnosis or failure result |
| `evaluation` | Correct diagnosis and correctness, when allowed |
| `source` | Entry script and configuration |

Hidden patient information should be logged only when the run's privacy policy
allows it. It should never be mixed with doctor-visible input.

### 7.2 `orchestration`

```json
{
  "strategy": "fixed_sequence",
  "description": "Nine information-seeking invocations, then diagnosis",
  "planned_steps": [
    {
      "agent_id": "agent_information_seeking",
      "repeat": 9,
      "termination": "respond"
    },
    {
      "agent_id": "agent_differential_diagnosis",
      "repeat": 1,
      "termination": "final_diagnosis"
    }
  ],
  "actual_invocation_order": ["inv_0001", "inv_0002", "inv_0010"]
}
```

`actual_invocation_order` must contain all invocation IDs. The abbreviated
example above is not a valid completed run.

### 7.3 `agents[]` (Level 1)

Required properties:

```json
{
  "agent_id": "agent_information_seeking",
  "agent_type": "information_seeking",
  "display_name": "Information Seeking Agent",
  "model": "gpt-5-nano",
  "instruction": {
    "source_path": "src/agent/prompts/agentclinic_information_gathering.md",
    "sha256": "...",
    "resolved_text": "...",
    "summary": "Gather clinical information and maintain the OSCE note."
  },
  "tools": [
    {"name": "bash", "schema_sha256": "..."},
    {"name": "update_osce_note", "schema_sha256": "..."},
    {"name": "update_plan", "schema_sha256": "..."}
  ],
  "status": "completed",
  "initial_input": {},
  "final_output": {},
  "summary": {},
  "usage": {},
  "invocations": []
}
```

Log `resolved_text`, not only the path. Prompt files can change after a run.
The hash makes prompt comparisons cheap.

### 7.4 `agents[].invocations[]` (Level 2)

Required properties:

```json
{
  "invocation_id": "inv_0001",
  "global_sequence": 1,
  "agent_sequence": 1,
  "phase": "information_seeking",
  "status": "completed",
  "started_at": "...",
  "ended_at": "...",
  "duration_ms": 2100,
  "input": {
    "source": "patient",
    "summary": "Patient reports one day of right lower quadrant pain.",
    "text": "...",
    "content_parts": [],
    "artifact_ids": []
  },
  "state_before": {
    "memory_snapshot_id": "memory_inv_0001_before"
  },
  "execution_summary": [
    {"sequence": 1, "kind": "memory_update", "label": "Updated OSCE note"},
    {"sequence": 2, "kind": "terminal_action", "label": "Asked patient"}
  ],
  "tool_names": ["update_osce_note", "bash"],
  "final_output": {
    "type": "ask_patient",
    "text": "Does the pain worsen with movement?",
    "raw_payload": {}
  },
  "state_after": {
    "memory_snapshot_id": "memory_inv_0001_after"
  },
  "usage": {},
  "rounds": []
}
```

For the diagnosis invocation, `input` must explicitly include the OSCE-note
handoff, differential list, and latest hospital response. Do not require the
viewer to find these in a previous agent's memory.

### 7.5 `rounds[]` (Level 3)

Required properties:

```json
{
  "round_id": "inv_0001_round_01",
  "sequence": 1,
  "status": "completed",
  "started_at": "...",
  "ended_at": "...",
  "duration_ms": 900,
  "input": {
    "messages": [],
    "message_count": 3,
    "artifact_ids": []
  },
  "assistant": {
    "content": "",
    "tool_call_ids": ["call_osce_01"]
  },
  "tool_calls": [
    {
      "tool_call_id": "call_osce_01",
      "sequence": 1,
      "name": "update_osce_note",
      "arguments": {},
      "status": "completed",
      "result": {},
      "result_artifact_id": null,
      "started_at": "...",
      "ended_at": "...",
      "duration_ms": 4
    }
  ],
  "memory_changes": [],
  "retries": [],
  "usage": {}
}
```

`input.messages` is the exact input sent to the model after normalization and
image extraction. This intentionally includes earlier assistant/tool messages
so a detailed viewer can explain why the model acted as it did.

Tool `arguments` should be parsed JSON when valid. Preserve the original string
as `arguments_raw` only when parsing fails. Tool results may be inline JSON,
text, or an artifact reference.

### 7.6 `highlights[]`

Highlights are task results, not trajectory events:

```json
{
  "highlight_id": "highlight_final_osce_note",
  "type": "osce_note",
  "title": "Final OSCE Note",
  "producer_agent_id": "agent_information_seeking",
  "source_invocation_id": "inv_0009",
  "is_final": true,
  "updated_at": "...",
  "data": {}
}
```

Required initial highlight types:

- `osce_note`: final structured note from the information-seeking agent;
- `differential_diagnosis_list`: final top-three list before handoff;
- `diagnostic_evidence`: evidence memory from the diagnosis agent;
- `final_diagnosis`: single diagnosis and terminal payload;
- `evaluation`: correct answer and correctness, if available.

The viewer should render these above the trajectory with stronger color and
spacing. Intermediate memory states stay inside invocation/round details.

### 7.7 `artifacts[]` and Image Policy

```json
{
  "artifact_id": "artifact_image_01",
  "kind": "image",
  "media_type": "image/jpeg",
  "original_source": "data_url",
  "stored_path": "artifacts/images/artifact_image_01.jpg",
  "directory": "artifacts/images",
  "decoded": true,
  "decode_status": "success",
  "sha256": "...",
  "byte_size": 12345,
  "created_by": {
    "invocation_id": "inv_0003",
    "round_id": "inv_0003_round_01"
  }
}
```

Rules:

1. Never store base64 or a `data:image/...` URL in `events.v1.jsonl` or
   `run.v1.json`.
2. Decode supported embedded images into `artifacts/images/`.
3. Display `stored_path`, `directory`, and `decoded`.
4. For remote URLs, set `decoded: false` unless downloaded and decoded.
5. If decoding fails, preserve metadata and `decode_status: failed`; do not
   preserve the full encoded payload in the visualization log.
6. Apply the same artifact-ref mechanism to oversized tool results.

## 8. Instrumentation Plan

### Phase 1: Protocol primitives

Add a run-scoped `TraceWriter` with:

- append-only `emit(event_type, ids, payload)`;
- monotonic task sequence;
- UTC timestamps;
- safe JSON serialization;
- image extraction/redaction;
- atomic projection generation.

Do not make `AgentRunLogger` independently own or overwrite the task file.
Instead, inject the run-scoped writer and invocation identity into each Agent.

### Phase 2: Agent and invocation boundaries

In `two_agent_interface.py`:

- register both agents during `reset`;
- include resolved prompt text/hash and exact tool set;
- emit invocation start before `_PhaseAgent.run`;
- emit invocation completion after parsing the terminal payload;
- log the explicit diagnosis handoff;
- upsert OSCE, differential, evidence, and diagnosis highlights;
- expose `trace_path`/`run_id` to `agentclinic_api_only.py`.

### Phase 3: Round and tool boundaries

In `agent.py`:

- emit `round.started` immediately before each model call;
- emit `llm.completed` with response and usage;
- emit `round.completed` after all tool calls for that response;
- keep retries attached to the same round.

In `tool_calling.py` and working-memory updates:

- emit `tool.started` and `tool.completed`;
- record parsed input and result before UI redaction;
- emit memory update patches/snapshots;
- extract images and large payloads to artifacts.

### Phase 4: Task lifecycle

In `agentclinic_api_only.py`:

- create one run ID before constructing agents;
- emit task start with dataset/scenario/configuration;
- log patient and measurement environment exchanges;
- emit task completion with correctness and aggregate usage;
- include `trace_path`, `run_id`, and protocol version in output JSONL.

### Phase 5: Projection and validation

- Build `run.v1.json` from events.
- Validate required fields and parent-child references.
- Assert exactly 9 information invocations and 1 diagnosis invocation for the
  fixed current strategy.
- Assert every completed invocation has at least one completed round and one
  final output.
- Assert the diagnosis input references the final OSCE highlight.
- Assert image-bearing content contains artifact refs and no base64.

## 9. Failure and Partial-Run Behavior

- A task can be visualized while running because events are append-only.
- A failed invocation remains visible with completed rounds and the error.
- Missing `task.completed` means the projector reports `status: incomplete`.
- A tool timeout records its input, failed status, and error; the result is
  `null`.
- Unknown future fields must be ignored by readers.
- Breaking semantic changes require a major protocol version.

## 10. Minimum Test Matrix

1. One information invocation with one model round and terminal response.
2. One invocation with OSCE update in round 1 and Bash response in round 2.
3. Full 9+1 run with correct agent and invocation ordering.
4. Diagnosis handoff contains final OSCE note, differential list, and latest
   hospital response.
5. Evidence and final OSCE note appear as highlights.
6. Tool results are present at Level 3 but absent from Level 2 summaries.
7. Base64 image input becomes an artifact reference with decode metadata.
8. Tool failure and model retry remain attached to the correct round.
9. Crash before task completion produces a valid incomplete projection.
10. Projection can be rebuilt byte-equivalently from the canonical event log.

## 11. Mock Visualization

The minimal mock is in `visualization/index.html` and reads
`visualization/mock_run.v1.json`.

It demonstrates:

- task summary and orchestration;
- separately highlighted OSCE note, differential list, evidence, and diagnosis;
- Level 1 logical-agent cards;
- Level 2 invocation/turn cards;
- Level 3 round cards;
- hidden-by-default raw input/output and tool details;
- tool results shown only at Level 3;
- image artifact path and decode status without rendering encoded image data.

The mock is deliberately dependency-free. A production UI can replace it
without changing the protocol.

Preview it from the repository root:

```bash
python3 -m http.server 8765 \
  --directory src/agentclinic_code/two_phased_agent/visualization
```

Then open `http://127.0.0.1:8765/`.

This document and mock do not yet change runtime logging. The instrumentation
work is deliberately separated into Phases 1 through 5 above so the protocol
can be reviewed before it becomes a compatibility contract.
