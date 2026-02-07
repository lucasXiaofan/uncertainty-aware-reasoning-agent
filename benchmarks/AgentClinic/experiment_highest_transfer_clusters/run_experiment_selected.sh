#!/bin/bash

# Run selected AgentClinic cases from a specified split or data file
# Usage:
#   ./run_experiment_selected.sh [SPLIT] [model_name] --ids 2,8,15,20 [options]
# Examples:
#   ./run_experiment_selected.sh test openai/gpt-5-mini --ids 2,8,15,20
#   ./run_experiment_selected.sh train openai/gpt-5-mini --ids 1,13,15,16 --use_uncertainty_aware --agent_type uncertainty_documentation_agent
#   ./run_experiment_selected.sh one_case_test openai/gpt-5-mini --ids 2,8,15,20 --name failed_train
#   ./run_experiment_selected.sh test openai/gpt-5-mini --ids 2,8,15,20 --ids 1,13,15,16 --use_memory
#   ./run_experiment_selected.sh test openai/gpt-5-mini --ids 3,4 --ids_1based
#   ./run_experiment_selected.sh test openai/gpt-5-mini --ids 2,8,15 --data_file /path/to/custom.jsonl

set -e

SPLIT="${1:-one_case_test}"
MODEL="${2:-openai/gpt-5-mini}"
shift 2 || true

USE_MEMORY=""
USE_UNCERTAINTY_AWARE=""
EXPERIMENT_NAME=""
AGENT_TYPE="uncertainty_aware_doctor"
WORKERS=4
DATA_FILE_OVERRIDE=""
IDS_1BASED=""

IDS_LIST=()

add_ids() {
    local raw="$1"
    local cleaned
    cleaned=$(echo "$raw" | tr -d ' ')
    IFS=',' read -r -a parts <<< "$cleaned"
    for id in "${parts[@]}"; do
        if [[ -z "$id" ]]; then
            continue
        fi
        if [[ ! "$id" =~ ^[0-9]+$ ]]; then
            echo "Error: invalid id '$id' (must be non-negative integer)"
            exit 1
        fi
        IDS_LIST+=("$id")
    done
}

# Parse optional flags
while [[ $# -gt 0 ]]; do
    case $1 in
        --use_memory)
            USE_MEMORY="--use_memory"
            shift
            ;;
        --use_uncertainty_aware)
            USE_UNCERTAINTY_AWARE="--use_uncertainty_aware"
            shift
            ;;
        --agent_type)
            AGENT_TYPE="$2"
            shift 2
            ;;
        --name)
            EXPERIMENT_NAME="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --data_file)
            DATA_FILE_OVERRIDE="$2"
            shift 2
            ;;
        --ids)
            add_ids "$2"
            shift 2
            ;;
        --ids_1based)
            IDS_1BASED="1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [SPLIT] [model_name] --ids 2,8,15,20 [--use_memory] [--use_uncertainty_aware] [--agent_type NAME] [--name experiment_name] [--workers N] [--data_file FILE] [--ids_1based]"
            exit 1
            ;;
    esac
done

if [[ ${#IDS_LIST[@]} -eq 0 ]]; then
    echo "Error: --ids is required (comma-separated list, can repeat)"
    exit 1
fi

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTCLINIC_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="$SCRIPT_DIR/results"

# Resolve data file
if [[ -n "$DATA_FILE_OVERRIDE" ]]; then
    DATA_FILE="$DATA_FILE_OVERRIDE"
else
    DATA_FILE="$SCRIPT_DIR/${SPLIT}.jsonl"
fi

# Create results directory
mkdir -p "$RESULTS_DIR"

# Check data file exists
if [ ! -f "$DATA_FILE" ]; then
    echo "Error: Data file not found: $DATA_FILE"
    exit 1
fi

# Count cases
NUM_CASES=$(wc -l < "$DATA_FILE" | tr -d ' ')

# Normalize ids (bash 3.2 compatible)
NORMALIZED_IDS=()
contains_id() {
    local needle="$1"
    shift
    for existing in "$@"; do
        if [[ "$existing" == "$needle" ]]; then
            return 0
        fi
    done
    return 1
}

for id in "${IDS_LIST[@]}"; do
    if [[ -n "$IDS_1BASED" ]]; then
        if [[ "$id" -eq 0 ]]; then
            echo "Error: --ids_1based requires ids >= 1"
            exit 1
        fi
        id=$((id - 1))
    fi
    if contains_id "$id" "${NORMALIZED_IDS[@]}"; then
        continue
    fi
    NORMALIZED_IDS+=("$id")
done

# Validate ids
for id in "${NORMALIZED_IDS[@]}"; do
    if [[ "$id" -lt 0 || "$id" -ge "$NUM_CASES" ]]; then
        echo "Error: scenario id $id is out of range (0..$((NUM_CASES - 1)))"
        exit 1
    fi
done

# Timestamp and output files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MODEL_SAFE=$(echo "$MODEL" | tr '/' '_')

MEMORY_SUFFIX=""
if [[ -n "$USE_MEMORY" ]]; then
    MEMORY_SUFFIX="_memory"
fi
UA_SUFFIX=""
if [[ -n "$USE_UNCERTAINTY_AWARE" ]]; then
    UA_SUFFIX="_ua"
fi

# Build filename
BASE_NAME=$(basename "$DATA_FILE")
BASE_NAME=${BASE_NAME%.jsonl}

if [[ -n "$EXPERIMENT_NAME" ]]; then
    EXPERIMENT_SAFE=$(echo "$EXPERIMENT_NAME" | tr ' /' '_')
    OUTPUT_FILE="$RESULTS_DIR/${EXPERIMENT_SAFE}_${MODEL_SAFE}${MEMORY_SUFFIX}${UA_SUFFIX}_${TIMESTAMP}.jsonl"
else
    OUTPUT_FILE="$RESULTS_DIR/${BASE_NAME}_${MODEL_SAFE}${MEMORY_SUFFIX}${UA_SUFFIX}_selected_${TIMESTAMP}.jsonl"
fi

echo "========================================================"
echo "High-Transfer Clusters Experiment (Selected Cases)"
echo "========================================================"
echo "Split/Data:         $DATA_FILE"
echo "Model:              $MODEL"
echo "Memory:             $([ -n "$USE_MEMORY" ] && echo "ENABLED" || echo "disabled")"
echo "Uncertainty-Aware:  $([ -n "$USE_UNCERTAINTY_AWARE" ] && echo "ENABLED" || echo "disabled")"
if [[ -n "$USE_UNCERTAINTY_AWARE" ]]; then
    echo "UA Agent Type:      $AGENT_TYPE"
fi
if [[ -n "$EXPERIMENT_NAME" ]]; then
    echo "Experiment:         $EXPERIMENT_NAME"
fi
echo "Num cases total:    $NUM_CASES"
echo "Selected IDs:       ${NORMALIZED_IDS[*]}"
echo "Output:             $OUTPUT_FILE"
echo "========================================================"

# Dependencies for uv run
DEPS="--with openai>=1.0.0 --with regex --with python-dotenv --with pyyaml"
COMMON_ARGS="--doctor_llm $MODEL --total_inferences 20 $USE_MEMORY $USE_UNCERTAINTY_AWARE"
if [[ -n "$USE_UNCERTAINTY_AWARE" ]]; then
    COMMON_ARGS="$COMMON_ARGS --uncertainty_agent_type $AGENT_TYPE"
fi

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
echo "Installed dataset with ${NUM_CASES} cases"

echo ""
echo "Running selected cases..."
echo "--------------------------------------------------------"

run_case() {
    local scenario_id=$1
    local tmp_file="$RESULTS_DIR/tmp_case_${scenario_id}_${TIMESTAMP}.jsonl"

    uv run $DEPS agentclinic_api_only.py \
        --agent_dataset MedQA_Ext \
        --num_scenarios 1 \
        --scenario_offset "$scenario_id" \
        $COMMON_ARGS \
        --output_file "$tmp_file" 2>/dev/null

    echo "  Completed case $scenario_id"
}

export -f run_case
export RESULTS_DIR TIMESTAMP DEPS COMMON_ARGS

printf "%s\n" "${NORMALIZED_IDS[@]}" | xargs -P "$WORKERS" -I {} bash -c 'run_case "$@"' _ {}

echo "--------------------------------------------------------"
echo "Merging results..."

# Merge results
> "$OUTPUT_FILE"
for i in "${NORMALIZED_IDS[@]}"; do
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
