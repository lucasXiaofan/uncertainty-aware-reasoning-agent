# Documentation Tools for Uncertainty-Aware Diagnosis

## Overview

This guide describes the new **documentation-focused diagnostic tools** that provide enhanced structured tracking of diagnostic reasoning with explicit fields for medical guideline relevance and action rationale.

## New Tools

### 1. `document_step` - Structured Diagnostic Documentation

A more comprehensive version of `diagnosis_step` that tracks:

**Parameters:**
- `new_information` (str): New atomic fact learned from patient/test (clean, non-redundant)
- `uncertainties` (str): Differential diagnoses in format: `"disease1: reasoning1; disease2: reasoning2; ..."`
- `reference_relevance` (str): Assessment of medical guideline relevance (currently: "No relevant information retrieved")
- `action` (str): Next action to take (e.g., "ASK PATIENT: ...", "REQUEST TEST: ...")
- `reason` (str): Why this action helps differentiate between current uncertainties

**Returns:** The formatted action string to output

**Example:**
```python
document_step(
    new_information="Patient has productive cough with green sputum for 3 days",
    uncertainties="Pneumonia: productive cough and fever suggest; Bronchitis: cough present but fever less common; TB: chronic cough but acute presentation less typical",
    reference_relevance="No relevant information retrieved",
    action="REQUEST TEST: Chest X-ray",
    reason="Chest X-ray will show infiltrates if pneumonia, helping differentiate from bronchitis"
)
```

### 2. `final_diagnosis_documented` - Clean Information Synthesis

Enhanced final diagnosis that uses only clean accumulated information:

**Parameters:**
- `reason` (str): Why ready for diagnosis OR what would be clarified with more rounds

**Returns:** `"DIAGNOSIS READY: [diagnosis]"` in AgentClinic format

**Features:**
- Loads ONLY `new_information` entries (clean atomic facts)
- Uses LLM (gpt-5-mini) to synthesize final diagnosis
- Records final step with diagnosis in session
- No redundant or narrative text - only facts

**Example:**
```python
final_diagnosis_documented(
    reason="Chest X-ray confirms pneumonia with infiltrate, fever and productive cough support diagnosis"
)
# Returns: "DIAGNOSIS READY: Community-acquired pneumonia"
```

**When out of rounds:**
```python
final_diagnosis_documented(
    reason="Maximum rounds used - would clarify sputum culture results and white blood cell count if given more chances"
)
```

## Session Structure

The new tools use an enhanced session structure:

```json
{
  "session_id": "scenario_12345_1234567890",
  "steps": [
    {
      "step_number": 1,
      "new_information": "Patient is 45-year-old male with fever 102°F",
      "uncertainties": {
        "Sepsis": "elevated fever and vital signs",
        "Pneumonia": "fever could indicate respiratory infection"
      },
      "reference_relevance": "No relevant information retrieved",
      "action": "ASK PATIENT: Do you have cough or chest pain?",
      "action_reason": "Helps differentiate respiratory vs other infection source"
    }
  ],
  "all_information": [
    "Patient is 45-year-old male with fever 102°F",
    "Patient has productive cough with green sputum",
    "Chest X-ray shows right lower lobe infiltrate"
  ],
  "current_uncertainties": {
    "Community-acquired pneumonia": "X-ray confirms with infiltrate"
  },
  "final_diagnosis": "Community-acquired pneumonia"
}
```

## Agent Configuration

### Using the Documentation Agent

The `uncertainty_documentation_agent` is configured to use these new tools:

```yaml
uncertainty_documentation_agent:
  model: "openai/gpt-5-mini"
  tools:
    - document_step
    - final_diagnosis_documented
  terminal_tools:
    - document_step
    - final_diagnosis_documented
```

### Instantiating the Agent

```python
from benchmarks.AgentClinic.uncertainty_aware_doctor import UncertaintyAwareDoctorAgent

# Use the documentation-focused agent
agent = UncertaintyAwareDoctorAgent(
    scenario=scenario,
    agent_type="uncertainty_documentation_agent",  # NEW PARAMETER
    max_infs=12
)

# Use the original simpler agent (default)
agent = UncertaintyAwareDoctorAgent(
    scenario=scenario,
    agent_type="uncertainty_aware_doctor",  # or omit for default
    max_infs=12
)
```

## Key Features

### 1. Clean Information Tracking
- Only **atomic facts** are stored in `all_information`
- No redundant narrative or repeated information
- Perfect for LLM synthesis in final diagnosis

### 2. Structured Uncertainties
- Differential diagnoses stored as `{disease: reasoning}` dictionary
- Easy to track evolution of diagnostic thinking
- Clear documentation of why each disease is considered

### 3. Action Rationale
- Every action must include **why** it helps differentiate
- Encourages thoughtful information gathering
- Reduces redundant or non-discriminative questions

### 4. Medical Guideline Integration (Future)
- `reference_relevance` field prepared for guideline context
- Currently: "No relevant information retrieved"
- Future: Agent can assess if retrieved guidelines are helpful

### 5. Automatic Session Management
- Session ID set by `inference_doctor` via `set_current_session()`
- Tools automatically use current session (no manual session_id passing)
- Thread-safe with file locking for parallel scenarios

## Workflow Example

```python
# Turn 1: Initial vital signs
document_step(
    new_information="45M, fever 102.3°F, BP 145/92, HR 105",
    uncertainties="Sepsis: fever and tachycardia; Pneumonia: fever suggests infection; UTI: fever without localization",
    reference_relevance="No relevant information retrieved",
    action="ASK PATIENT: Do you have cough or difficulty breathing?",
    reason="Respiratory symptoms differentiate pneumonia from other infection sources"
)

# Turn 2: Patient response
document_step(
    new_information="Productive cough with green sputum for 3 days, pleuritic chest pain",
    uncertainties="Community-acquired pneumonia: productive cough and pleuritic pain strongly suggest; Bronchitis: cough present but pleuritic pain uncommon",
    reference_relevance="No relevant information retrieved",
    action="REQUEST TEST: Chest X-ray",
    reason="X-ray will confirm pneumonia with infiltrates vs bronchitis without"
)

# Turn 3: Test results
document_step(
    new_information="Chest X-ray shows right lower lobe infiltrate",
    uncertainties="Community-acquired pneumonia: confirmed by infiltrate",
    reference_relevance="No relevant information retrieved",
    action="REQUEST TEST: Sputum culture",
    reason="Culture identifies organism for targeted antibiotic therapy"
)

# Final diagnosis
final_diagnosis_documented(
    reason="X-ray infiltrate confirms pneumonia, productive cough and fever support CAP diagnosis"
)
# Returns: "DIAGNOSIS READY: Community-acquired pneumonia"
```

## Differences from Original Tools

| Feature | `diagnosis_step` | `document_step` |
|---------|-----------------|-----------------|
| Uncertainties format | List of strings | Dictionary with reasoning |
| Guideline relevance | Not tracked | Explicit field |
| Action rationale | Not required | Required |
| Information storage | `accumulated_notes` (text) | `all_information` (list) |
| Structure | Simple | Highly structured |

| Feature | `final_diagnosis` | `final_diagnosis_documented` |
|---------|-------------------|------------------------------|
| Information source | Extracts from steps | Uses `all_information` list |
| Data quality | May include narrative | Only clean atomic facts |
| Session update | Records final step | Records + updates count |
| Parameter | `reason_ready` | `reason` |

## Testing

Run the test script to verify the tools work correctly:

```bash
python test_documentation_tools.py
```

Expected output:
```
================================================================================
TESTING DOCUMENTATION TOOLS
================================================================================

1. Created test session: test_doc_session_001

2. Documenting Step 1: Initial vital signs...
   Response: ASK PATIENT: Do you have any cough, chest pain, or difficulty breathing?

3. Documenting Step 2: Patient response...
   Response: REQUEST TEST: Chest X-ray

...

Final Response: DIAGNOSIS READY: Community-acquired pneumonia

================================================================================
TEST COMPLETED SUCCESSFULLY!
================================================================================
```

## Integration with AgentClinic

The `UncertaintyAwareDoctorAgent` wrapper automatically:

1. Sets session context before each inference
2. Handles max inference limit (calls appropriate final_diagnosis)
3. Extracts responses from tools
4. Updates conversation history
5. Tracks tokens

No changes needed to AgentClinic experiment scripts - just specify `agent_type`:

```python
doctor = UncertaintyAwareDoctorAgent(
    scenario,
    backend_str="openai/gpt-5-mini",
    max_infs=12,
    agent_type="uncertainty_documentation_agent"  # Use new tools
)
```

## Future Enhancements

1. **Medical Guideline Retrieval**: Populate `reference_relevance` with actual guideline assessment
2. **Experience Retrieval**: Use documented uncertainties to retrieve similar past cases
3. **Uncertainty Metrics**: Track how uncertainties evolve over time
4. **Action Effectiveness**: Analyze which action types best reduce uncertainty
5. **Visualization**: Generate diagnostic decision trees from documented steps

## File Locations

- **Tools**: `/agent/tools/documentation_tools.py`
- **Registration**: `/agent/tools/__init__.py`
- **Config**: `/agent/agent_config.yaml` (see `uncertainty_documentation_agent`)
- **Wrapper**: `/benchmarks/AgentClinic/uncertainty_aware_doctor.py`
- **Test**: `/test_documentation_tools.py`

## Questions?

For issues or questions, refer to:
- Session management: `/agent/tools/diagnosis_session.py`
- Original tools: `/agent/tools/implementations.py`
- Agent wrapper: `/benchmarks/AgentClinic/uncertainty_aware_doctor.py`
