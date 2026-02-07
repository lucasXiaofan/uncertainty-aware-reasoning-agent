#!/usr/bin/env python3
"""Test script for the new documentation tools."""
import os
import sys

# Add paths for imports
agent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "agent"))
if agent_path not in sys.path:
    sys.path.append(agent_path)

from tools.documentation_tools import document_step, final_diagnosis_documented
from tools.diagnosis_session import set_current_session, load_session, clear_session

def test_documentation_workflow():
    """Test the complete documentation workflow."""
    print("=" * 80)
    print("TESTING DOCUMENTATION TOOLS")
    print("=" * 80)

    # Create a test session
    test_session_id = "test_doc_session_001"
    set_current_session(test_session_id)

    print(f"\n1. Created test session: {test_session_id}")

    # Step 1: Document first observation
    print("\n2. Documenting Step 1: Initial vital signs...")
    response1 = document_step(
        new_information="Patient is a 45-year-old male with fever 102.3°F, BP 145/92, HR 105",
        uncertainties="Sepsis: elevated vital signs and fever; Pneumonia: fever and tachycardia could indicate respiratory infection; UTI: fever and elevated HR without specific localization",
        reference_relevance="No relevant information retrieved",
        action="ASK PATIENT: Do you have any cough, chest pain, or difficulty breathing?",
        reason="This question helps differentiate between pneumonia (respiratory symptoms) and other sources of infection"
    )
    print(f"   Response: {response1}")

    # Step 2: Document second observation
    print("\n3. Documenting Step 2: Patient response...")
    response2 = document_step(
        new_information="Patient reports productive cough with green sputum for 3 days, mild chest pain with deep breathing",
        uncertainties="Community-acquired pneumonia: productive cough with sputum and pleuritic chest pain strongly suggest; Bronchitis: could explain cough but less likely with fever and pleuritic pain; Sepsis: still possible but pneumonia is leading differential",
        reference_relevance="No relevant information retrieved",
        action="REQUEST TEST: Chest X-ray",
        reason="Chest X-ray will confirm or rule out pneumonia by showing infiltrates, and help differentiate from bronchitis"
    )
    print(f"   Response: {response2}")

    # Step 3: Document test result
    print("\n4. Documenting Step 3: Test results...")
    response3 = document_step(
        new_information="Chest X-ray shows right lower lobe infiltrate consistent with pneumonia",
        uncertainties="Community-acquired pneumonia: X-ray confirms diagnosis with RLL infiltrate; Aspiration pneumonia: possible but patient has no risk factors mentioned",
        reference_relevance="No relevant information retrieved",
        action="REQUEST TEST: Sputum culture and CBC",
        reason="Sputum culture identifies causative organism for targeted antibiotic therapy; CBC confirms infection with elevated WBC"
    )
    print(f"   Response: {response3}")

    # Load session to inspect
    print("\n5. Inspecting session data...")
    session = load_session(test_session_id)
    print(f"   Total steps documented: {len(session.get('steps', []))}")
    print(f"   Clean information count: {len(session.get('all_information', []))}")
    print("\n   Clean information collected:")
    for i, info in enumerate(session.get('all_information', []), 1):
        print(f"      {i}. {info}")

    # Final diagnosis
    print("\n6. Calling final diagnosis...")
    final_response = final_diagnosis_documented(
        reason="Chest X-ray confirms pneumonia with RLL infiltrate, clinical presentation with productive cough and fever support community-acquired pneumonia diagnosis"
    )
    print(f"   Final Response: {final_response}")

    # Load final session state
    print("\n7. Final session state...")
    final_session = load_session(test_session_id)
    print(f"   Total steps (including final): {len(final_session.get('steps', []))}")
    print(f"   Final diagnosis: {final_session.get('final_diagnosis', 'Not set')}")

    # Cleanup
    print("\n8. Cleaning up test session...")
    clear_session(test_session_id)
    print("   Session cleared.")

    print("\n" + "=" * 80)
    print("TEST COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_documentation_workflow()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
