# Analysis Report
**Input File**: `results.jsonl`

## 1. Question Asking Quality

| ID | Total Qs | Redundant Qs | Failed Qs (No Info) | Proactive? | Note |
|---|---|---|---|---|---|
| 9 | 7 | 0 | 3 | True |  |
| 10 | 0 | 0 | 0 | False | No questions asked, and incorrect (Premature decision) |
| 18 | 7 | 0 | 6 | True |  |
| 28 | 6 | 0 | 2 | True |  |
| 30 | 4 | 0 | 2 | True |  |
| 33 | 4 | 0 | 1 | True |  |
| 34 | 2 | 0 | 1 | True |  |
| 38 | 7 | 0 | 6 | True |  |
| 41 | 2 | 0 | 1 | True |  |
| 43 | 7 | 0 | 5 | True |  |
| 44 | 1 | 0 | 0 | True |  |
| 45 | 7 | 0 | 4 | True |  |
| 46 | 7 | 0 | 4 | True |  |
| 49 | 7 | 0 | 6 | True |  |

**Summary**:
- Total Questions: 68
- Redundant Questions: 0 (0.0%)
- Failed Questions (No Info): 41 (60.3%)

## 2. Decision Ability & Context Usage

| ID | Context % | Trajectory | Final Result | Total Qs | Valid Qs | Input Tokens | Output Tokens |
|---|---|---|---|---|---|---|---|
| 9 | 99.2% | Improved (Wrong -> Correct) | Correct | 7 | 4 | 199208 | 27848 |
| 10 | 13.0% | Stable Wrong | Wrong | 0 | 0 | 4189 | 758 |
| 18 | 20.0% | Stable Wrong | Wrong | 7 | 1 | 203952 | 31800 |
| 28 | 100.0% | Improved (Wrong -> Correct) | Correct | 6 | 4 | 220969 | 33166 |
| 30 | 37.5% | Improved (Wrong -> Correct) | Correct | 4 | 2 | 64365 | 10955 |
| 33 | 100.0% | Stable Correct | Correct | 4 | 3 | 83765 | 12180 |
| 34 | 43.2% | Stable Wrong | Wrong | 2 | 1 | 27507 | 5157 |
| 38 | 32.9% | Degraded (Correct -> Wrong) | Wrong | 7 | 1 | 245320 | 33496 |
| 41 | 19.8% | Stable Correct | Correct | 2 | 1 | 28419 | 5280 |
| 43 | 32.2% | Improved (Wrong -> Correct) | Correct | 7 | 2 | 232872 | 30040 |
| 44 | 18.6% | Stable Correct | Correct | 1 | 1 | 7876 | 1374 |
| 45 | 100.0% | Stable Correct | Correct | 7 | 3 | 183600 | 29736 |
| 46 | 39.2% | Improved (Wrong -> Correct) | Correct | 7 | 3 | 236712 | 37936 |
| 49 | 30.3% | Stable Wrong | Wrong | 7 | 1 | 175736 | 26432 |

**Token Usage Summary**:
- Total Input Tokens: 1914490
- Total Output Tokens: 286158