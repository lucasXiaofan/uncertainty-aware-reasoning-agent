# Analysis Report
**Input File**: `results.jsonl`
**Summary File**: `summary.json`

## 1. Question Asking Quality

| ID | Total Qs | Redundant Qs | Failed Qs (No Info) | Proactive? | Note |
|---|---|---|---|---|---|
| 1113 | 7 | 0 | 5 | True |  |
| 182 | 8 | 1 | 5 | True |  |
| 7 | 8 | 0 | 7 | True |  |
| 1005 | 3 | 0 | 1 | True |  |
| 183 | 5 | 0 | 2 | True |  |
| 1209 | 2 | 0 | 2 | True |  |
| 954 | 4 | 0 | 3 | True |  |
| 1037 | 2 | 0 | 2 | True |  |
| 241 | 2 | 0 | 2 | True |  |
| 135 | 0 | 0 | 0 | False | No questions asked, but correct (Initial context likely sufficient) |
| 1089 | 0 | 0 | 0 | False | No questions asked, but correct (Initial context likely sufficient) |
| 201 | 9 | 0 | 9 | True |  |
| 902 | 3 | 0 | 2 | True |  |
| 1009 | 2 | 0 | 1 | True |  |
| 550 | 0 | 0 | 0 | False | No questions asked, but correct (Initial context likely sufficient) |

**Summary**:
- Total Questions: 55
- Redundant Questions: 1 (1.8%)
- Failed Questions (No Info): 41 (74.5%)

## 2. Decision Ability & Context Usage

| ID | Context % | Trajectory | Final Result | Total Qs | Valid Qs | Input Tokens | Output Tokens |
|---|---|---|---|---|---|---|---|
| 1113 | 16.9% | Improved (Wrong -> Correct) | Correct | 7 | 2 | 303344 | 57176 |
| 182 | 23.7% | Stable Wrong | Wrong | 8 | 3 | 479988 | 84996 |
| 7 | 13.9% | Stable Wrong | Wrong | 8 | 1 | 396783 | 77184 |
| 1005 | 19.5% | Improved (Wrong -> Correct) | Correct | 3 | 2 | 80856 | 15808 |
| 183 | 20.9% | Improved (Wrong -> Correct) | Correct | 5 | 3 | 155112 | 30600 |
| 1209 | 12.2% | Stable Correct | Correct | 2 | 0 | 39075 | 8841 |
| 954 | 36.7% | Stable Correct | Correct | 4 | 1 | 139205 | 30885 |
| 1037 | 9.3% | Stable Correct | Correct | 2 | 0 | 31656 | 6909 |
| 241 | 7.1% | Stable Correct | Correct | 2 | 0 | 37320 | 7551 |
| 135 | 9.0% | Stable Correct | Correct | 0 | 0 | 5088 | 1046 |
| 1089 | 8.9% | Stable Correct | Correct | 0 | 0 | 3242 | 760 |
| 201 | 7.9% | Stable Wrong | Wrong | 9 | 0 | 477660 | 89330 |
| 902 | 11.9% | Stable Correct | Correct | 3 | 1 | 65144 | 15928 |
| 1009 | 18.6% | Stable Correct | Correct | 2 | 1 | 47037 | 11067 |
| 550 | 9.2% | Stable Correct | Correct | 0 | 0 | 5309 | 1169 |

**Token Usage Summary**:
- Total Input Tokens: 2266819
- Total Output Tokens: 439250