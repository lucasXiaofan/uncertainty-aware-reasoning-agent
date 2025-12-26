# CP_ENV Benchmark Analysis (20 Cases) - gpt-4o-mini

This report summarizes the benchmark execution of 20 cases from the `CP_ENV` dataset using `gpt-4o-mini` for both the patient and doctor agents.

### **Benchmark Execution Summary**
Out of the 20 cases attempted, 19 cases successfully completed the simulation pipeline. One case (Item 16) failed to reach a conclusion.

| Metric | Value |
| :--- | :--- |
| **Total Success/Attempted** | 19 / 20 |
| **Correct Diagnoses (Successes only)** | 13 / 19 |
| **Final Accuracy (Total)** | **65.0%** (13/20) |
| **Average Total Interactions (per patient)** | **19.37** |
| **Average Subjective QA (Conversation) Rounds** | **16.63** interactions |
| **Average Examination Check (Lab Tests) Rounds** | **2.74** tests |
| **Average Tokens Used (per patient)** | **19,226** |

---

### **Detailed Analysis Per Patient**

Below is the breakdown for each patient, including the number of rounds used for dialogue (Subjective QA) vs. laboratory examinations.

| Patient ID | Correct? | Subjective QA (Int.) | Lab Exams | Tokens Used | Lab Examinations Used |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **5** | ✅ | 15 | 1 | 12,559 | CT scan of the sinuses |
| **7** | ✅ | 13 | 4 | 15,010 | ANA test, skin biopsy, ultrasound, MRI |
| **6** | ❌ | 17 | 2 | 16,732 | Vulvar swab, Tissue biopsy |
| **8** | ❌ | 17 | 2 | 18,732 | Skin biopsy, CBC |
| **4** | ✅ | 17 | 2 | 18,651 | Wood's lamp, skin biopsy |
| **1** | ✅ | 15 | 2 | 18,644 | Imaging studies, Dermatological exam |
| **3** | ❌ | 21 | 1 | 24,978 | Biopsy |
| **9** | ✅ | 17 | 2 | 18,036 | Skin Biopsy, Patch Testing |
| **10** | ✅ | 15 | 2 | 15,412 | Skin biopsy, CBC |
| **11** | ✅ | 15 | 3 | 15,625 | IOP measurement, Ocular ultrasound, CBC |
| **13** | ✅ | 15 | 2 | 15,291 | Skin biopsy, Basic blood tests |
| **2** | ❌ | 22 | 5 | 32,899 | Platelet count, Clotting factors, Blood tests, Skin culture, Bone marrow biopsy |
| **12** | ✅ | 15 | 3 | 16,515 | CT scan, EMG, MRI |
| **15** | ✅ | 13 | 2 | 14,947 | Biopsy of ulcer, CBC |
| **14** | ❌ | 19 | 3 | 22,393 | MRI brain, Neuropsychological testing, Lumbar puncture |
| **17** | ✅ | 15 | 2 | 15,820 | Skin biopsy, Dermatoscopy |
| **19** | ✅ | 15 | 3 | 14,329 | FNA biopsy, Thyroid function tests, Neck ultrasound |
| **18** | ✅ | 17 | 2 | 17,878 | Skin Assessment, Comprehensive Eye Exam |
| **20** | ❌ | 23 | 9 | 40,849 | Stool Occult Blood, Skin Biopsy, CMP, CBC, Colonoscopy, anti-dsDNA, ANA, ANCA |
| **16** | ❌ | 7* | 0* | 4,207* | *(Failed to conclude)* |

---

### **Observations**
- **Subjective QA vs. Examination**: The simulation heavily relies on initial dialogue (averaging ~16-17 interactions) to gather history. Most successful diagnoses require **2 to 3 lab examinations**.
- **Efficiency**: The average token consumption of ~19k per case suggest high efficiency for the depth of interaction achieved.
- **Complexity Threshold**: Case 20 demonstrates the upper bound of the current agent interaction, requiring 9 separate tests and over 40k tokens, yet failing to reach the exact ground truth.
