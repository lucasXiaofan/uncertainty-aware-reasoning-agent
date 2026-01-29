#!/bin/bash

# Run agentclinic experiments on train or test data from high-transfer clusters
# Usage: ./run_experiment.sh [SPLIT] [model_name] [--use_memory] [--name experiment_name]
# Example: ./run_experiment.sh test openai/gpt-5-mini
# Example: ./run_experiment.sh train openai/gpt-4o
# Example: ./run_experiment.sh one_case_test openai/gpt-5-mini --name single_case_baseline
# Example: ./run_experiment.sh test openai/gpt-5-mini --use_memory
# Example: ./run_experiment.sh test openai/gpt-5-mini --name baseline_v1
# Example: ./run_experiment.sh test openai/gpt-5-mini --use_memory --name with_memory_experiment

set -e

# Parse arguments
SPLIT="${1:-one_case_test}"  # Default to test
MODEL="${2:-openai/gpt-5-mini}"  # Default model
USE_MEMORY=""  # Default: memory disabled
EXPERIMENT_NAME=""  # Default: no custom name

# # Parse optional flags
# shift 2 || true  # Remove first two positional args
# while [[ $# -gt 0 ]]; do
#     case $1 in
#         --use_memory)
#             USE_MEMORY="--use_memory"
#             shift
#             ;;
#         --name)
#             EXPERIMENT_NAME="$2"
#             shift 2
#             ;;
#         *)
#             echo "Unknown option: $1"
#             echo "Usage: $0 [SPLIT] [model_name] [--use_memory] [--name experiment_name]"
#             exit 1
#             ;;
#     esac
# done

# Validate split option
VALID_SPLITS=("train" "test" "one_case_train" "one_case_test")
if [[ ! " ${VALID_SPLITS[@]} " =~ " ${SPLIT} " ]]; then
    echo "Usage: $0 [SPLIT] [model_name] [--use_memory] [--name experiment_name]"
    echo "  SPLIT: 'train', 'test', 'one_case_train', or 'one_case_test' (default: test)"
    echo "  MODEL: model name (default: openai/gpt-5-mini)"
    echo "  --use_memory: enable memory retrieval (default: disabled)"
    echo "  --name NAME: custom experiment name for output file (default: auto-generated)"
    echo ""
    echo "Available datasets:"
    echo "  train           - Full training set (37 cases)"
    echo "  test            - Full test set (47 cases)"
    echo "  one_case_train  - One case per cluster for training (22 cases)"
    echo "  one_case_test   - One case per cluster for testing (23 cases)"
    exit 1
fi

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTCLINIC_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="$SCRIPT_DIR/results"
DATA_FILE="$SCRIPT_DIR/${SPLIT}.jsonl"

# Create results directory
mkdir -p "$RESULTS_DIR"

# Check data file exists
if [ ! -f "$DATA_FILE" ]; then
    echo "Error: Data file not found: $DATA_FILE"
    echo ""
    if [[ "$SPLIT" == "one_case_train" || "$SPLIT" == "one_case_test" ]]; then
        echo "Run 'uv run create_one_case_splits.py' first to generate one-case splits"
    else
        echo "Available data files should be: train.jsonl, test.jsonl, one_case_train.jsonl, one_case_test.jsonl"
    fi
    exit 1
fi

# Count cases
NUM_CASES=$(wc -l < "$DATA_FILE" | tr -d ' ')

# Timestamp and output files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MODEL_SAFE=$(echo "$MODEL" | tr '/' '_')

# Build filename
if [[ -n "$EXPERIMENT_NAME" ]]; then
    # Custom experiment name provided
    EXPERIMENT_SAFE=$(echo "$EXPERIMENT_NAME" | tr ' /' '_')
    MEMORY_SUFFIX=""
    if [[ -n "$USE_MEMORY" ]]; then
        MEMORY_SUFFIX="_memory"
    fi
    OUTPUT_FILE="$RESULTS_DIR/${SPLIT}_${EXPERIMENT_SAFE}${MEMORY_SUFFIX}_${TIMESTAMP}.jsonl"
else
    # Default naming: split_model_memory_timestamp
    MEMORY_SUFFIX=""
    if [[ -n "$USE_MEMORY" ]]; then
        MEMORY_SUFFIX="_memory"
    fi
    OUTPUT_FILE="$RESULTS_DIR/${SPLIT}_${MODEL_SAFE}${MEMORY_SUFFIX}_${TIMESTAMP}.jsonl"
fi

echo "========================================================"
echo "High-Transfer Clusters Experiment"
echo "========================================================"
echo "Split:       $SPLIT"
echo "Model:       $MODEL"
echo "Memory:      $([ -n "$USE_MEMORY" ] && echo "ENABLED" || echo "disabled")"
if [[ -n "$EXPERIMENT_NAME" ]]; then
    echo "Experiment:  $EXPERIMENT_NAME"
fi
echo "Data file:   $DATA_FILE"
echo "Num cases:   $NUM_CASES"
echo "Output:      $OUTPUT_FILE"
echo "========================================================"

# Dependencies for uv run
DEPS="--with openai>=1.0.0 --with regex --with python-dotenv"
COMMON_ARGS="--doctor_llm $MODEL --total_inferences 20 $USE_MEMORY"

# Backup original dataset
cd "$AGENTCLINIC_DIR"
ORIGINAL_DATASET="agentclinic_medqa_extended.jsonl"
BACKUP_FILE="${ORIGINAL_DATASET}.backup_${TIMESTAMP}"

if [ -f "$ORIGINAL_DATASET" ]; then
    cp "$ORIGINAL_DATASET" "$BACKUP_FILE"
    echo "Backed up original dataset"
fi

# Install our dataset
cp "$DATA_FILE" "$ORIGINAL_DATASET"
echo "Installed ${SPLIT} dataset with ${NUM_CASES} cases"

echo ""
echo "Running experiment..."
echo "--------------------------------------------------------"

# Run all cases with parallel workers
run_case() {
    local scenario_id=$1
    local tmp_file="$RESULTS_DIR/tmp_case_${scenario_id}_${TIMESTAMP}.jsonl"

    uv run $DEPS agentclinic_api_only.py \
        --agent_dataset MedQA_Ext \
        --num_scenarios 1 \
        --scenario_offset "$scenario_id" \
        $COMMON_ARGS \
        --output_file "$tmp_file" 2>/dev/null

    echo "  Completed case $((scenario_id + 1))/$NUM_CASES"
}

export -f run_case
export RESULTS_DIR TIMESTAMP DEPS COMMON_ARGS NUM_CASES

# Run with 10 parallel workers
seq 0 $((NUM_CASES - 1)) | xargs -P 10 -I {} bash -c 'run_case "$@"' _ {}

echo "--------------------------------------------------------"
echo "Merging results..."

# Merge results
> "$OUTPUT_FILE"
for i in $(seq 0 $((NUM_CASES - 1))); do
    tmp_file="$RESULTS_DIR/tmp_case_${i}_${TIMESTAMP}.jsonl"
    if [ -f "$tmp_file" ]; then
        cat "$tmp_file" >> "$OUTPUT_FILE"
    fi
done

# Clean up temp files
rm -f "$RESULTS_DIR"/tmp_case_*_"${TIMESTAMP}".jsonl

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
echo "Results:     $OUTPUT_FILE"

# Generate detailed report if script exists (generates its own report_v2_*.txt file)
if [ -f "$AGENTCLINIC_DIR/generate_report_v2.py" ]; then
    python3 "$AGENTCLINIC_DIR/generate_report_v2.py" "$OUTPUT_FILE" >/dev/null 2>&1
fi

# Show quick summary
TOTAL=$(wc -l < "$OUTPUT_FILE" | tr -d ' ')
echo "Cases:       $TOTAL cases processed"
echo "========================================================"
