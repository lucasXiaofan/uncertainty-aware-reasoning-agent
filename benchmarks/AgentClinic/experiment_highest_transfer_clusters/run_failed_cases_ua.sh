#!/bin/bash

# Run experiments on failed cases dataset with uncertainty-aware doctor
# Supports parallel execution with safe session file handling
#
# Usage: ./run_failed_cases_ua.sh <dataset_file> [model] [parallel_jobs]
#
# Example:
#   ./run_failed_cases_ua.sh failed_test.jsonl
#   ./run_failed_cases_ua.sh failed_test.jsonl openai/gpt-4o
#   ./run_failed_cases_ua.sh failed_test.jsonl openai/gpt-5-mini 4  # 4 parallel jobs

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <dataset_file> [model] [parallel_jobs]"
    echo ""
    echo "Arguments:"
    echo "  dataset_file   - JSONL file with scenarios to run (e.g., failed_test.jsonl)"
    echo "  model          - Model to use (default: openai/gpt-5-mini)"
    echo "  parallel_jobs  - Number of parallel jobs (default: 5)"
    echo ""
    echo "Example:"
    echo "  $0 failed_test.jsonl                          # 5 parallel jobs (default)"
    echo "  $0 failed_test.jsonl openai/gpt-4o 4          # 4 parallel jobs"
    echo "  $0 failed_test.jsonl openai/gpt-5-mini 1      # Sequential"
    echo ""
    echo "Note: Session files are thread-safe - parallel execution is supported."
    exit 1
fi

DATASET_FILE="$1"
MODEL="${2:-openai/gpt-5-mini}"
PARALLEL_JOBS="${3:-4}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTCLINIC_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="$SCRIPT_DIR/results"

# Check if dataset file exists and convert to absolute path
if [ ! -f "$DATASET_FILE" ]; then
    # Try relative to script dir
    if [ -f "$SCRIPT_DIR/$DATASET_FILE" ]; then
        DATASET_FILE="$SCRIPT_DIR/$DATASET_FILE"
    else
        echo "Error: Dataset file not found: $DATASET_FILE"
        exit 1
    fi
else
    # Convert to absolute path
    DATASET_FILE="$(cd "$(dirname "$DATASET_FILE")" && pwd)/$(basename "$DATASET_FILE")"
fi

# Count scenarios
NUM_SCENARIOS=$(wc -l < "$DATASET_FILE" | tr -d ' ')

echo "========================================================"
echo "Uncertainty-Aware Failed Cases Experiment"
echo "========================================================"
echo "Dataset:        $DATASET_FILE"
echo "Scenarios:      $NUM_SCENARIOS"
echo "Model:          $MODEL"
echo "Parallel jobs:  $PARALLEL_JOBS"
echo "========================================================"
echo ""

# Create results directory
mkdir -p "$RESULTS_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MODEL_SAFE=$(echo "$MODEL" | tr '/' '_')
BASENAME=$(basename "$DATASET_FILE" .jsonl)
OUTPUT_FILE="$RESULTS_DIR/${BASENAME}_${MODEL_SAFE}_ua_${TIMESTAMP}.jsonl"

# Backup and install dataset
echo "Installing dataset..."
cd "$AGENTCLINIC_DIR"
ORIGINAL_DATASET="agentclinic_medqa_extended.jsonl"
BACKUP_FILE="${ORIGINAL_DATASET}.backup_${TIMESTAMP}"

if [ -f "$ORIGINAL_DATASET" ]; then
    cp "$ORIGINAL_DATASET" "$BACKUP_FILE"
fi

cp "$DATASET_FILE" "$ORIGINAL_DATASET"

# Run experiments
echo ""
echo "Running experiments..."
echo "--------------------------------------------------------"

OUTPUT_PREFIX="$RESULTS_DIR/.tmp_${BASENAME}_${MODEL_SAFE}_${TIMESTAMP}"
DEPS="--with openai>=1.0.0 --with regex --with python-dotenv --with pyyaml"

# Function to run a single scenario (inline, not exported)
run_one_scenario() {
    local offset=$1
    local scenario_output="${OUTPUT_PREFIX}_scenario_${offset}.jsonl"

    echo "[Job $offset] Starting scenario $offset..."
    uv run $DEPS agentclinic_api_only.py \
        --agent_dataset MedQA_Ext \
        --num_scenarios 1 \
        --scenario_offset "$offset" \
        --doctor_llm "$MODEL" \
        --total_inferences 12 \
        --use_uncertainty_aware \
        --output_file "$scenario_output" 2>&1
    echo "[Job $offset] Completed scenario $offset"
}

if [ "$PARALLEL_JOBS" -gt 1 ]; then
    echo "Running $NUM_SCENARIOS scenarios with $PARALLEL_JOBS parallel jobs..."
    echo ""

    # Use background processes with job control
    running_jobs=0
    for offset in $(seq 0 $((NUM_SCENARIOS - 1))); do
        run_one_scenario "$offset" &
        running_jobs=$((running_jobs + 1))

        # Wait if we've reached max parallel jobs
        if [ "$running_jobs" -ge "$PARALLEL_JOBS" ]; then
            wait -n 2>/dev/null || wait
            running_jobs=$((running_jobs - 1))
        fi
    done

    # Wait for remaining jobs
    wait
else
    echo "Running $NUM_SCENARIOS scenarios sequentially..."
    echo ""

    for offset in $(seq 0 $((NUM_SCENARIOS - 1))); do
        echo "Running scenario $((offset + 1))/$NUM_SCENARIOS (offset=$offset)..."
        run_one_scenario "$offset"
        echo ""
    done
fi

echo "--------------------------------------------------------"

# Combine results
echo ""
echo "Combining results..."
cat ${OUTPUT_PREFIX}_scenario_*.jsonl > "$OUTPUT_FILE" 2>/dev/null || true

# Clean up temp files
rm -f ${OUTPUT_PREFIX}_scenario_*.jsonl

# Restore original dataset
if [ -f "$BACKUP_FILE" ]; then
    mv "$BACKUP_FILE" "$ORIGINAL_DATASET"
    echo "Restored original dataset"
else
    rm -f "$ORIGINAL_DATASET"
fi

echo ""
echo "========================================================"
echo "Experiment Complete!"
echo "========================================================"
echo "Results saved to: $OUTPUT_FILE"

# Generate detailed report if script exists
if [ -f "$AGENTCLINIC_DIR/generate_report_v2.py" ]; then
    echo "Generating detailed report..."
    python3 "$AGENTCLINIC_DIR/generate_report_v2.py" "$OUTPUT_FILE" >/dev/null 2>&1
fi

echo ""

# Show summary
echo "Results summary:"
python3 -c "
import json
import sys

passed = 0
failed = 0

try:
    with open('$OUTPUT_FILE', 'r') as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            if case.get('correct', False):
                passed += 1
            else:
                failed += 1
                print(f\"  FAILED: scenario {case.get('scenario_id')}\")
                print(f\"    Model: {case.get('model_diagnosis', '')[:60]}...\")
                actual = case.get('problem_info', {}).get('OSCE_Examination', {}).get('Correct_Diagnosis', '')
                print(f\"    Actual: {actual}\")

    total = passed + failed
    print()
    print(f'Total: {total}, Passed: {passed}, Failed: {failed}')
    if total > 0:
        print(f'Accuracy: {passed/total*100:.1f}%')
except Exception as e:
    print(f'Error reading results: {e}')
"

echo ""
echo "Session files located in: $SCRIPT_DIR/../../agent/diagnosis_sessions/"
echo "========================================================"
