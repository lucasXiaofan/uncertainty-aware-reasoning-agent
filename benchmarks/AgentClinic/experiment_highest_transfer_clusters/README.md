# High Transfer Rate Clusters - Experiment Setup

## Overview

This directory contains experiment infrastructure for testing medical diagnosis models on high-transfer-rate patient clusters (transfer rate ≥ 80%).

**Dataset Statistics:**
- **23 clusters** with transfer rate ≥ 80%
- **84 total patient cases**
- All cases are unique (no duplicates or overlap)

**Available Splits:**
- `train.jsonl` - Full training set (37 cases)
- `test.jsonl` - Full test set (47 cases)
- `one_case_train.jsonl` - One case per cluster for training (22 cases)
- `one_case_test.jsonl` - One case per cluster for testing (23 cases)

## Quick Start

### 1. Generate One-Case-Per-Cluster Splits

```bash
# Create special splits with 1 case per cluster
uv run create_one_case_splits.py
```

This creates:
- `one_case_train.jsonl` (22 cases - 1 per cluster)
- `one_case_test.jsonl` (23 cases - 1 per cluster)

### 2. Run Experiments

```bash
# Full test set
./run_experiment.sh test openai/gpt-5-mini --name baseline_full

# One case per cluster (faster, for quick testing)
./run_experiment.sh one_case_test openai/gpt-5-mini --name baseline_single_case

# With memory enabled
./run_experiment.sh test openai/gpt-5-mini --use_memory --name with_memory

# Custom model
./run_experiment.sh one_case_test openai/gpt-4o --name gpt4_ablation
```

## Files Generated

### Combined Files
- `all_high_transfer_clusters_with_splits.json` - All clusters with complete metadata and both train/test data
- `train.jsonl` - All training cases (37 cases)
- `test.jsonl` - All test cases (47 cases)

### Individual Cluster Files (23 files)
- `cluster_01_Acute_Leukemia_Workup.json`
- `cluster_02_Chronic_Leukemia_Lymphoproliferative.json`
- `cluster_03_Antibiotic-Associated_Hospital-Acquired_Diarrhea.json`
- ... and 20 more

Each cluster file contains:
```json
{
  "cluster_id": 1,
  "cluster_name": "Acute Leukemia Workup",
  "transfer_rate": "~95%",
  "diseases": ["Acute lymphoblastic leukemia", "Acute myelogenous leukemia"],
  "total_cases": 2,
  "train_cases_count": 1,
  "test_cases_count": 1,
  "train_data": [...],
  "test_data": [...]
}
```

## How It Works

### Step 1: Filter Clusters by Transfer Rate

Edit threshold in `create_cluster_splits.py`:
```python
TRANSFER_RATE_THRESHOLD = 80  # Change to 85, 90, etc.
```

Parse transfer rate from strings like `"~95%"` or `"~80% (context-dependent)"`:
```python
def parse_transfer_rate(rate_str):
    match = re.search(r'(\d+)%', rate_str)
    return float(match.group(1)) if match else 0.0
```

### Step 2: Match Patient Cases to Clusters

Cases from `agentclinic_medqa_extended.jsonl` are matched by diagnosis:
```python
diagnosis = case['OSCE_Examination']['Correct_Diagnosis'].lower()
# Match against cluster['diseases'] (case-insensitive)
```

### Step 3: Create 50/50 Train/Test Split

```python
random.seed(42)  # For reproducibility
shuffled_cases = cases.copy()
random.shuffle(shuffled_cases)

mid_point = len(shuffled_cases) // 2
train_cases = shuffled_cases[:mid_point]
test_cases = shuffled_cases[mid_point:]
```

## Modifying Configuration

### Change Transfer Rate Threshold

```python
# create_cluster_splits.py, line 17
TRANSFER_RATE_THRESHOLD = 85  # Only clusters ≥ 85%
```

### Change Split Ratio (e.g., 70/30)

```python
# create_cluster_splits.py, create_train_test_split()
split_point = int(len(shuffled_cases) * 0.7)
train_cases = shuffled_cases[:split_point]
test_cases = shuffled_cases[split_point:]
```

### Change Random Seed

```python
# create_cluster_splits.py, line 74
random.seed(123)  # Different shuffling
```

## Expanding the Dataset

### Add New Patient Cases

1. Add cases to `agentclinic_medqa_extended.jsonl`:
```json
{"OSCE_Examination": {"Correct_Diagnosis": "Disease Name", ...}}
```

2. Ensure diagnosis matches a disease in `simiar_patient_cluster.json`

3. Re-run:
```bash
uv run create_cluster_splits.py
```

### Add New Cluster

1. Edit `simiar_patient_cluster.json`:
```json
{
  "cluster_id": 35,
  "name": "Your New Cluster",
  "diseases": ["Disease 1", "Disease 2"],
  "shared_diagnostic_path": {
    "transfer_rate": "~85%",
    "key_symptoms": [...],
    "pivotal_tests": [...]
  }
}
```

2. Add matching patient cases to `agentclinic_medqa_extended.jsonl`

3. Re-run the script

### Modify Cluster Transfer Rate

1. Edit `simiar_patient_cluster.json` → update `transfer_rate` field
2. Re-run script to regenerate splits

## Source Files

**Input:**
- `../simiar_patient_cluster.json` - Cluster definitions with transfer rates
- `../agentclinic_medqa_extended.jsonl` - Patient cases (214 total)

**Scripts (repository root):**
- `create_cluster_splits.py` - Generate splits
- `check_duplicates.py` - Verify uniqueness

## Script Details

### create_cluster_splits.py

**Key Functions:**
- `parse_transfer_rate()` - Extract numeric rate from string
- `load_cluster_data()` - Load and filter clusters by threshold
- `load_medqa_cases()` - Load patient cases from JSONL
- `organize_cases_by_cluster()` - Map cases to clusters by diagnosis
- `create_train_test_split()` - Split cases 50/50 with shuffle

**Flow:**
1. Load clusters → filter by transfer rate ≥ 80%
2. Load patient cases
3. Match cases to clusters (by diagnosis)
4. Random 50/50 split for each cluster
5. Save individual cluster JSON files
6. Save combined `train.jsonl` and `test.jsonl`
7. Save `all_high_transfer_clusters_with_splits.json`

### check_duplicates.py

**Verification:**
- MD5 hash of each case to detect duplicates
- Check within train set
- Check within test set
- Check overlap between train and test

## Troubleshooting

**Cases not matching clusters?**
- Check diagnosis spelling (case-insensitive matching)
- Verify disease names in `simiar_patient_cluster.json`

**Need to regenerate?**
```bash
uv run create_cluster_splits.py  # Overwrites existing files
```

## Data Format

Patient case structure:
```json
{
  "OSCE_Examination": {
    "Objective_for_Doctor": "...",
    "Patient_Actor": {
      "Demographics": "35-year-old female",
      "History": "...",
      "Symptoms": {...}
    },
    "Physical_Examination_Findings": {...},
    "Test_Results": {...},
    "Correct_Diagnosis": "Myasthenia gravis"
  }
}
```

## Running Experiments

### run_experiment.sh

Shell script to run experiments on train or test splits.

**Usage:**
```bash
./run_experiment.sh [train|test] [model_name] [--use_memory] [--name experiment_name]
```

**Parameters:**
- `train|test` - Which split to use (default: test)
- `model_name` - LLM model to use (default: openai/gpt-5-mini)
- `--use_memory` - Enable memory retrieval from past experiences (default: disabled)
- `--name NAME` - Custom experiment name for output files (default: auto-generated from model)

**Examples:**
```bash
# Basic run on test set
./run_experiment.sh test openai/gpt-5-mini

# Named experiment for tracking
./run_experiment.sh test openai/gpt-5-mini --name baseline_experiment

# With memory enabled
./run_experiment.sh test openai/gpt-5-mini --use_memory --name memory_ablation

# Different model on train set
./run_experiment.sh train openai/gpt-4o --name gpt4_training
```

**Output Files:**
- Without `--name`: `test_openai_gpt-5-mini_20260128_181234.jsonl`
- With `--name baseline_v1`: `test_baseline_v1_20260128_181234.jsonl`
- With memory: `test_baseline_v1_memory_20260128_181234.jsonl`

Results are saved in `results/` directory.

## Notes

- All matching is case-insensitive
- Same random seed (42) = reproducible splits
- Odd case counts: test set gets extra case
- Empty clusters (no cases) are skipped
- Memory is disabled by default for controlled experiments
