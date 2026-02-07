# Uncertainty-Aware Doctor Agent Implementation

## Overview
Implemented an uncertainty-aware diagnostic agent that explicitly tracks diagnostic reasoning through structured tools. Session management is handled by wrapper code - the agent only focuses on clinical reasoning.

## Key Design Decisions

### 1. Session Management (Invisible to Agent)
- **Wrapper handles session ID**: Created in `UncertaintyAwareDoctorAgent.__init__()`
- **Thread-local context**: Session ID stored in thread-local storage via `set_current_session()`
- **Tools access automatically**: `diagnosis_step` and `final_diagnosis` use `get_current_session()`
- **Agent doesn't see session ID**: Removed from tool parameters and system prompt

### 2. One Tool Call Per Turn
- **Agent config**: `max_turns: 1` forces single tool call
- **Explicit reasoning**: Each turn records information, uncertainties, and next action
- **Formatted output**: Tool returns what to say/do (not just logging)

### 3. Dual Purpose Tools
Tools serve two functions:
1. **Record to session file**: Persist diagnostic reasoning for analysis
2. **Return formatted action**: Provide response to AgentClinic

## Implementation Files

### Created Files

#### `agent/tools/diagnosis_session.py`
Session management with thread-local context:
```python
def set_current_session(session_id: str)  # Wrapper calls before agent
def get_current_session() -> str          # Tools use to get session
def append_step(session_id, ...)          # Record step to file
def get_accumulated_notes(session_id)     # Get all notes so far
```

### Modified Files

#### `agent/tools/implementations.py`
Added two tools (NO session_id parameter):

**`diagnosis_step(new_information, current_uncertainties, next_step_action)`**
- Records: info + differential + planned action
- Returns: formatted action
  - "ASK PATIENT: question" → returns "question"
  - "REQUEST TEST: test" → returns "REQUEST TEST: test"
  - "DIAGNOSIS READY" → returns signal message

**`final_diagnosis(reason_ready)`**
- Extracts: all new_information from session steps
- Synthesizes: uses gpt-5-mini LLM to generate clean final diagnosis
- Records: final diagnosis with synthesis prompt
- Returns: `"DIAGNOSIS READY: [diagnosis]"` (AgentClinic format)

#### `agent/agent_config.yaml`
Added `uncertainty_aware_doctor` agent:
- `model: "x-ai/grok-4.1-fast"`
- `max_turns: 1` (one tool call per inference)
- `tools: [diagnosis_step, final_diagnosis]`
- `terminal_tools: [final_diagnosis]`
- System prompt: NO session_id mention (handled by wrapper)

#### `agent/tools/__init__.py`
Added exports:
- `diagnosis_step`, `final_diagnosis`
- `set_current_session`, `get_current_session`
- Session management functions

#### `benchmarks/AgentClinic/uncertainty_aware_doctor.py`
Wrapper class `UncertaintyAwareDoctorAgent`:
- Drop-in replacement for `DoctorAgent`
- Creates session_id per scenario
- Calls `set_current_session()` before agent inference
- Extracts tool result as response
- Compatible interface: `inference_doctor()`, token tracking, etc.

## Usage in AgentClinic

### In `agentclinic_api_only.py`

Replace:
```python
from agentclinic_api_only import DoctorAgent
doctor_agent = DoctorAgent(scenario, backend_str=doctor_llm, ...)
```

With:
```python
from uncertainty_aware_doctor import UncertaintyAwareDoctorAgent
doctor_agent = UncertaintyAwareDoctorAgent(scenario, backend_str=doctor_llm, ...)
```

Everything else stays the same!

## Workflow

### Each Turn:
1. **Wrapper** (`inference_doctor`):
   - Calls `set_current_session(self.session_id)`
   - Gets accumulated notes: `get_accumulated_notes(self.session_id)`
   - Builds prompt with context (NO session_id in prompt)
   - Calls `agent.run()`

2. **Agent** (uncertainty_aware_doctor):
   - Analyzes patient response + accumulated notes
   - Calls `diagnosis_step()` with 3 args:
     - `new_information`: What was learned
     - `current_uncertainties`: Current differential (2-4 diseases)
     - `next_step_action`: Next action (ASK PATIENT/REQUEST TEST/DIAGNOSIS READY)
   - OR calls `final_diagnosis()` when ready

3. **Tool** (`diagnosis_step`/`final_diagnosis`):
   - Gets session from `get_current_session()` automatically
   - Appends to session file
   - Returns formatted response

4. **Wrapper**:
   - Extracts tool result
   - Returns to AgentClinic

## Session File Format

Stored in `agent/diagnosis_sessions/{session_id}.json`:

```json
{
  "session_id": "scenario_12345_1706123456",
  "steps": [
    {
      "step_number": 1,
      "new_information": "Patient presents with chest pain, 2 hours duration",
      "current_uncertainties": ["MI", "PE", "costochondritis"],
      "next_step_action": "REQUEST TEST: Vital_Signs"
    },
    {
      "step_number": 2,
      "new_information": "BP 120/80, HR 78, pain reproducible on palpation",
      "current_uncertainties": ["costochondritis", "muscle strain"],
      "next_step_action": "ASK PATIENT: When did you start exercising?"
    }
  ],
  "accumulated_notes": "[Step 1]\nNew Info: ...\nDifferential: ...\n\n[Step 2]\n...",
  "current_uncertainties": ["costochondritis", "muscle strain"]
}
```

## LLM-Based Diagnosis Synthesis

The `final_diagnosis` tool uses a two-stage approach:

### Stage 1: Information Gathering (Diagnostic Agent)
- Agent (gpt-5-mini) gathers information through conversation
- Each step records atomic facts in `new_information`
- Tracks differential diagnoses and uncertainties
- Focuses on collecting clean, factual information

### Stage 2: Diagnosis Synthesis (Separate LLM)
- When ready, agent calls `final_diagnosis(reason_ready)`
- Tool extracts all `new_information` from session steps
- Sends accumulated facts to fresh gpt-5-mini instance
- LLM synthesizes clean, concise final diagnosis
- Returns in AgentClinic format: `"DIAGNOSIS READY: [diagnosis]"`

### Benefits of Separation:
1. **Clean information**: Agent focuses on gathering atomic facts, not diagnosis formatting
2. **Fresh perspective**: Synthesis LLM sees only facts, no conversation noise
3. **Consistent output**: Dedicated LLM ensures clean diagnosis format
4. **Focused prompts**: Each LLM has a single, clear task

## Benefits

1. **Agent simplicity**: Agent focuses on reasoning, not session management
2. **Explicit uncertainty tracking**: Every step shows differential diagnoses
3. **Transparent reasoning**: Session files show full diagnostic thought process
4. **Parallel execution**: Thread-local context supports multiple concurrent sessions
5. **AgentClinic compatible**: Drop-in replacement with same interface
6. **Analyzable**: Session files enable post-hoc analysis of diagnostic reasoning
7. **Two-stage diagnosis**: Separate information gathering from diagnosis synthesis

## Testing

To verify implementation:

```bash
cd /Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent

# Test imports
python3 -c "
import sys; sys.path.insert(0, 'agent')
from tools import diagnosis_step, final_diagnosis, set_current_session, get_current_session
from tools.diagnosis_session import append_step, get_accumulated_notes
print('All imports successful!')
"

# Test agent config
python3 -c "
import yaml
with open('agent/agent_config.yaml') as f:
    cfg = yaml.safe_load(f)
assert 'uncertainty_aware_doctor' in cfg['agents']
assert cfg['agents']['uncertainty_aware_doctor']['max_turns'] == 1
print('Agent config correct!')
"

# Test tool execution with context
python3 -c "
import sys; sys.path.insert(0, 'agent')
from tools import execute_tool, set_current_session, clear_session

test_id = 'test_123'
clear_session(test_id)
set_current_session(test_id)

result = execute_tool('diagnosis_step', {
    'new_information': 'Patient has fever',
    'current_uncertainties': 'pneumonia, flu',
    'next_step_action': 'REQUEST TEST: Chest_X-Ray'
})
assert 'REQUEST TEST: Chest_X-Ray' in result
print('Tool execution successful!')
print('Result:', result)
"
```

## Complete Workflow Example

### What the Agent Sees and Does:

```python
# Step 1: Initial assessment
diagnosis_step(
    new_information="Patient presents with chest pain for 2 hours, sharp quality",
    current_uncertainties="MI (acute onset), PE (sharp pain), costochondritis, pleurisy",
    next_step_action="REQUEST TEST: Vital Signs"
)
# Returns: "REQUEST TEST: Vital Signs"

# Step 2: After vitals
diagnosis_step(
    new_information="BP 120/80, HR 78, RR 16, SpO2 98%, temp 37.0°C - all normal",
    current_uncertainties="costochondritis (likely - stable vitals), muscle strain, anxiety",
    next_step_action="REQUEST TEST: Chest examination"
)
# Returns: "REQUEST TEST: Chest examination"

# Step 3: After physical exam
diagnosis_step(
    new_information="Pain reproducible on palpation of left chest wall at 4th rib",
    current_uncertainties="costochondritis (most likely - reproducible pain), muscle strain",
    next_step_action="ASK PATIENT: Any recent trauma, heavy lifting, or new exercise?"
)
# Returns: "Any recent trauma, heavy lifting, or new exercise?"

# Step 4: After patient response
diagnosis_step(
    new_information="Patient started weight training 3 days ago, first time in years",
    current_uncertainties="costochondritis (trauma + reproducible pain confirms)",
    next_step_action="DIAGNOSIS READY"
)
# Returns: "I'm ready to provide a diagnosis. Let me finalize my assessment."

# Step 5: Final diagnosis
final_diagnosis(
    reason_ready="Musculoskeletal chest pain confirmed by reproducible tenderness, recent trauma history, normal vitals, and no cardiac risk factors. All serious causes ruled out."
)
# Internally: Extracts all new_information from steps 1-4
# Sends to gpt-5-mini: "Patient presents with..., BP 120/80..., Pain reproducible..., Started weight training..."
# LLM synthesizes: "Costochondritis"
# Returns: "DIAGNOSIS READY: Costochondritis"
```

### What the Agent Doesn't Handle:
- ✗ Session ID management (wrapper handles via thread-local context)
- ✗ Diagnosis formatting/synthesis (separate LLM handles)
- ✓ Information gathering (agent's focus)
- ✓ Uncertainty tracking (agent's focus)
- ✓ Deciding when to diagnose (agent's focus)

## Next Steps

1. **Run on AgentClinic**: Test with actual scenarios
2. **Analyze sessions**: Review session files to verify reasoning quality
3. **Tune synthesis prompt**: Adjust gpt-5-mini prompt for better diagnoses
4. **Experience generation**: Use failed cases to generate learning experiences
5. **Integrate with memory retrieval**: Add past experiences to prompt
