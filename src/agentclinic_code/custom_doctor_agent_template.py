"""
Template custom doctor agent for agentclinic_api_only.py.

Run with:
python3 src/agentclinic_code/agentclinic_api_only.py \
  --custom_doctor_agent_path src/agentclinic_code/custom_doctor_agent_template.py

When this file is loaded by agentclinic_api_only.py, these symbols are injected:
- DoctorAgentBase: the built-in DoctorAgent class
- query_model: the shared model-query helper

Keep the public interface compatible with the runtime:
- __init__(scenario, backend_str, max_infs, bias_present, img_request)
- inference_doctor(question, image_requested=False, memory_context="")
- reset()
"""


class CustomDoctorAgent(DoctorAgentBase):
    def __init__(self, scenario, backend_str="gpt-5-nano", max_infs=20, bias_present=None, img_request=False) -> None:
        self.scenario = scenario
        self.backend = backend_str
        self.MAX_INFS = max_infs
        self.bias_present = None if bias_present == "None" else bias_present
        self.img_request = img_request
        self.biases = [
            "recency",
            "frequency",
            "false_consensus",
            "confirmation",
            "status_quo",
            "gender",
            "race",
            "sexual_orientation",
            "cultural",
            "education",
            "religion",
            "socioeconomic",
        ]
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.last_uncertainty_reasoning = ""
        self._experience_printed = False
        self.reset()


    def system_prompt(self) -> str:
        base = (
            "You are a doctor named Dr. Agent who only responds in dialogue. "
            "You are evaluating a patient and may ask focused questions or request tests. "
            f"You may take at most {self.MAX_INFS} turns total and have already used {self.infs}. "
            'Use "REQUEST TEST: [test]" for exams, vitals, or tests. '
            'When ready, output "DIAGNOSIS READY: [diagnosis here]". '
            "Keep each response short and clinically precise."
        )
        if self.img_request:
            base += ' You may also request relevant images with "REQUEST IMAGES".'
        presentation = (
            f"\n\nBelow is the doctor-visible objective/context: {self.presentation}\n"
            "\nUse this only as persistent case context, not as patient dialogue."
        )
        return base + bias_prompt + presentation

    def inference_doctor(self, question, image_requested=False, memory_context="") -> str:
        if self.infs >= self.MAX_INFS:
            return "DIAGNOSIS READY: Unable to determine within allotted turns"

        pass

    def reset(self) -> None:
        self.infs = 0
        self.agent_hist = ""
        self.presentation = self.scenario.examiner_information()
        self.last_uncertainty_reasoning = ""
        self._experience_printed = False


DoctorAgent = CustomDoctorAgent
