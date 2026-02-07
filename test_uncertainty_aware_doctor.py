"""Test script for uncertainty-aware doctor agent implementation."""
import sys
import os

# Add agent to path
sys.path.insert(0, "agent")

print("=" * 60)
print("Testing Uncertainty-Aware Doctor Agent Implementation")
print("=" * 60)

# Test 1: Import session management
print("\n[Test 1] Importing session management...")
try:
    from tools.diagnosis_session import (
        load_session, save_session, append_step,
        get_accumulated_notes, clear_session
    )
    print("✓ Session management imports OK")
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

# Test 2: Import tools
print("\n[Test 2] Importing diagnosis tools...")
try:
    from tools import diagnosis_step, final_diagnosis
    print("✓ Diagnosis tools imports OK")
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

# Test 3: Check tool schemas registered
print("\n[Test 3] Checking tool schemas...")
try:
    from tools import get_tool_schema
    ds_schema = get_tool_schema('diagnosis_step')
    fd_schema = get_tool_schema('final_diagnosis')
    assert ds_schema is not None, "diagnosis_step schema not found"
    assert fd_schema is not None, "final_diagnosis schema not found"
    print(f"✓ diagnosis_step schema: {ds_schema['function']['name']}")
    print(f"✓ final_diagnosis schema: {fd_schema['function']['name']}")
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

# Test 4: Test agent config
print("\n[Test 4] Checking agent config...")
try:
    import yaml
    with open('agent/agent_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    assert 'uncertainty_aware_doctor' in config['agents'], "Agent not in config"
    agent_cfg = config['agents']['uncertainty_aware_doctor']
    print(f"✓ Agent config found")
    print(f"  Model: {agent_cfg['model']}")
    print(f"  Tools: {agent_cfg['tools']}")
    print(f"  Max turns: {agent_cfg['max_turns']}")
    print(f"  Terminal tools: {agent_cfg['terminal_tools']}")
    assert agent_cfg['max_turns'] == 1, "max_turns should be 1"
except Exception as e:
    print(f"✗ Failed: {e}")
    sys.exit(1)

# Test 5: Test session operations
print("\n[Test 5] Testing session operations...")
try:
    test_session_id = "test_session_123"

    # Clear any existing session
    clear_session(test_session_id)

    # Append first step
    session1 = append_step(
        session_id=test_session_id,
        new_information="Patient presents with chest pain",
        uncertainties=["myocardial infarction", "pulmonary embolism", "costochondritis"],
        next_step_action="REQUEST TEST: Vital_Signs"
    )
    print(f"✓ Step 1 appended - {len(session1['steps'])} steps total")

    # Append second step
    session2 = append_step(
        session_id=test_session_id,
        new_information="BP 120/80, HR 78, temp normal. Pain is sharp and reproducible.",
        uncertainties=["costochondritis", "pleurisy"],
        next_step_action="ASK PATIENT: When did the pain start?"
    )
    print(f"✓ Step 2 appended - {len(session2['steps'])} steps total")

    # Get accumulated notes
    notes = get_accumulated_notes(test_session_id)
    print(f"✓ Accumulated notes retrieved ({len(notes)} chars)")
    print(f"  Preview: {notes[:100]}...")

    # Load session
    loaded = load_session(test_session_id)
    assert len(loaded['steps']) == 2, "Should have 2 steps"
    print(f"✓ Session loaded with {len(loaded['steps'])} steps")

    # Clear session
    cleared = clear_session(test_session_id)
    assert cleared, "Should have cleared session"
    print(f"✓ Session cleared")
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Test diagnosis_step tool directly
print("\n[Test 6] Testing diagnosis_step tool...")
try:
    from tools import execute_tool
    test_session_id2 = "test_tool_session"
    clear_session(test_session_id2)

    # Call diagnosis_step tool
    result = execute_tool("diagnosis_step", {
        "diagnosis_session_id": test_session_id2,
        "new_information": "Patient has fever and cough for 3 days",
        "current_uncertainties": "pneumonia, bronchitis, COVID-19",
        "next_step_action": "REQUEST TEST: Chest_X-Ray"
    })
    print(f"✓ diagnosis_step executed")
    print(f"  Result: {result}")
    assert "REQUEST TEST: Chest_X-Ray" in result, "Should return formatted action"

    # Test ASK PATIENT format
    result2 = execute_tool("diagnosis_step", {
        "diagnosis_session_id": test_session_id2,
        "new_information": "X-ray shows infiltrate in right lower lobe",
        "current_uncertainties": "bacterial pneumonia, atypical pneumonia",
        "next_step_action": "ASK PATIENT: Do you have any underlying health conditions?"
    })
    print(f"✓ diagnosis_step with ASK PATIENT format")
    print(f"  Result: {result2}")
    assert "Do you have any underlying health conditions?" in result2
    assert "ASK PATIENT:" not in result2, "Should strip ASK PATIENT prefix"

    clear_session(test_session_id2)
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Test final_diagnosis tool
print("\n[Test 7] Testing final_diagnosis tool...")
try:
    test_session_id3 = "test_final_session"
    clear_session(test_session_id3)

    result = execute_tool("final_diagnosis", {
        "diagnosis_session_id": test_session_id3,
        "reason_ready": "Clear evidence of bacterial pneumonia with positive infiltrate",
        "uncertainties_resolved": "Ruled out COVID-19 with negative test, atypical pneumonia unlikely given rapid onset",
        "final_diagnosis_text": "Community-acquired bacterial pneumonia"
    })
    print(f"✓ final_diagnosis executed")
    print(f"  Result: {result}")
    assert "DIAGNOSIS READY:" in result, "Should return AgentClinic format"
    assert "Community-acquired bacterial pneumonia" in result

    clear_session(test_session_id3)
except Exception as e:
    print(f"✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ ALL TESTS PASSED!")
print("=" * 60)
print("\nImplementation summary:")
print("- diagnosis_session.py: Session management with file locking")
print("- diagnosis_step tool: Records info + returns formatted action")
print("- final_diagnosis tool: Records final diagnosis + returns AgentClinic format")
print("- uncertainty_aware_doctor config: max_turns=1 for one tool call per turn")
print("- UncertaintyAwareDoctorAgent: Simplified wrapper for AgentClinic")
print("\nReady for integration with AgentClinic!")
