#!/bin/bash

# Run selected AgentClinic cases from a specified split or data file
# Usage:
#   ./run_experiment_selected.sh [options]
# Examples:
#   ./run_experiment_selected.sh --count 50 --data_file /path/to/agentclinic_mimiciv.jsonl
#   ./run_experiment_selected.sh --count 100 --random --data_file /path/to/agentclinic_mimiciv.jsonl
#   ./run_experiment_selected.sh --count 50 --model openai/gpt-5-mini --data_file /path/to/file.jsonl
#   ./run_experiment_selected.sh --ids 2,8,15,20 --data_file /path/to/file.jsonl
#   ./run_experiment_selected.sh test openai/gpt-5-mini --ids 2,8,15,20
#   ./run_experiment_selected.sh test openai/gpt-5-mini --ids 1,13 --use_uncertainty_aware --agent_type uncertainty_documentation_agent

set -e

# Optional positional args (skip if first arg looks like a flag)
SPLIT="one_case_test"
MODEL="openai/gpt-5-mini"
if [[ $# -ge 1 && "$1" != --* ]]; then
    SPLIT="$1"
    shift
fi
if [[ $# -ge 1 && "$1" != --* ]]; then
    MODEL="$1"
    shift
fi

USE_MEMORY=""
USE_UNCERTAINTY_AWARE=""
EXPERIMENT_NAME=""
AGENT_TYPE="uncertainty_aware_doctor"
WORKERS=10
DATA_FILE_OVERRIDE=""
IDS_1BASED=""
COUNT=""
START_INDEX=0
RANDOM_SELECT=""
AGENT_DATASET=""

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
        --model)
            MODEL="$2"
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
        --count)
            COUNT="$2"
            if [[ ! "$COUNT" =~ ^[0-9]+$ ]] || [[ "$COUNT" -eq 0 ]]; then
                echo "Error: --count must be a positive integer"
                exit 1
            fi
            shift 2
            ;;
        --start)
            START_INDEX="$2"
            if [[ ! "$START_INDEX" =~ ^[0-9]+$ ]]; then
                echo "Error: --start must be a non-negative integer"
                exit 1
            fi
            shift 2
            ;;
        --random)
            RANDOM_SELECT="1"
            shift
            ;;
        --agent_dataset)
            AGENT_DATASET="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [SPLIT] [model_name] {--ids 2,8,15,20 | --count N} [--random] [--use_memory] [--use_uncertainty_aware] [--agent_type NAME] [--name experiment_name] [--workers N] [--data_file FILE] [--ids_1based]"
            exit 1
            ;;
    esac
done

if [[ ${#IDS_LIST[@]} -eq 0 ]] && [[ -z "$COUNT" ]]; then
    echo "Error: either --ids or --count is required"
    echo "  --ids 2,8,15,20   select specific case IDs (comma-separated, can repeat)"
    echo "  --count 50         select first N cases (or random N with --random)"
    exit 1
fi

if [[ ${#IDS_LIST[@]} -gt 0 ]] && [[ -n "$COUNT" ]]; then
    echo "Error: --ids and --count are mutually exclusive"
    exit 1
fi

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTCLINIC_DIR="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="$SCRIPT_DIR/results"

# Resolve data file and agent_dataset
if [[ -n "$DATA_FILE_OVERRIDE" ]]; then
    DATA_FILE="$DATA_FILE_OVERRIDE"
else
    DATA_FILE="$SCRIPT_DIR/${SPLIT}.jsonl"
fi

# Auto-detect agent_dataset from data file if not specified
if [[ -z "$AGENT_DATASET" ]]; then
    DATA_BASENAME=$(basename "$DATA_FILE")
    case "$DATA_BASENAME" in
        agentclinic_mimiciv*)   AGENT_DATASET="MIMICIV" ;;
        agentclinic_nejm_ext*) AGENT_DATASET="NEJM_Ext" ;;
        agentclinic_nejm*)     AGENT_DATASET="NEJM" ;;
        agentclinic_medqa_ext*|*) AGENT_DATASET="MedQA_Ext" ;;
    esac
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

# Generate IDs from --count if provided
if [[ -n "$COUNT" ]]; then
    if [[ "$START_INDEX" -ge "$NUM_CASES" ]]; then
        echo "Error: --start $START_INDEX is out of range (0..$((NUM_CASES - 1)))"
        exit 1
    fi
    END_INDEX=$((START_INDEX + COUNT))
    if [[ "$END_INDEX" -gt "$NUM_CASES" ]]; then
        echo "Warning: --start $START_INDEX + --count $COUNT exceeds available cases ($NUM_CASES), clamping to $((NUM_CASES - START_INDEX))"
        END_INDEX="$NUM_CASES"
    fi
    if [[ -n "$RANDOM_SELECT" ]]; then
        # Generate random sample of COUNT ids from START_INDEX..NUM_CASES-1
        while IFS= read -r id; do
            IDS_LIST+=("$id")
        done < <(python3 -c "import random; ids=list(range($START_INDEX,$NUM_CASES)); random.shuffle(ids); print('\n'.join(str(i) for i in ids[:$((END_INDEX - START_INDEX))]))")
    else
        # Sequential: cases from START_INDEX to END_INDEX-1
        for ((i=START_INDEX; i<END_INDEX; i++)); do
            IDS_LIST+=("$i")
        done
    fi
fi

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
echo "Agent Dataset:      $AGENT_DATASET"
echo "Model:              $MODEL"
echo "Memory:             $([ -n "$USE_MEMORY" ] && echo "ENABLED" || echo "disabled")"
echo "Uncertainty-Aware:  $([ -n "$USE_UNCERTAINTY_AWARE" ] && echo "ENABLED" || echo "disabled")"
if [[ -n "$USE_UNCERTAINTY_AWARE" ]]; then
    echo "UA Agent Type:      $AGENT_TYPE"
fi
if [[ -n "$EXPERIMENT_NAME" ]]; then
    echo "Experiment:         $EXPERIMENT_NAME"
fi
echo "Num cases in file:  $NUM_CASES"
echo "Selected count:     ${#NORMALIZED_IDS[@]}"
if [[ -n "$RANDOM_SELECT" ]]; then
    echo "Selection mode:     random"
fi
echo "Workers:            $WORKERS"
if [[ ${#NORMALIZED_IDS[@]} -le 20 ]]; then
    echo "Selected IDs:       ${NORMALIZED_IDS[*]}"
else
    echo "Selected IDs:       ${NORMALIZED_IDS[*]:0:10} ... ${NORMALIZED_IDS[*]:$((${#NORMALIZED_IDS[@]}-5))}"
fi
echo "Output:             $OUTPUT_FILE"
echo "========================================================"

# Dependencies for uv run
DEPS="--with openai>=1.0.0 --with regex --with python-dotenv --with pyyaml"
COMMON_ARGS="--doctor_llm $MODEL --total_inferences 20 $USE_MEMORY $USE_UNCERTAINTY_AWARE"
if [[ -n "$USE_UNCERTAINTY_AWARE" ]]; then
    COMMON_ARGS="$COMMON_ARGS --uncertainty_agent_type $AGENT_TYPE"
fi

# Map agent_dataset to the file the Python loader expects
cd "$AGENTCLINIC_DIR"
case "$AGENT_DATASET" in
    MIMICIV)    LOADER_FILE="agentclinic_mimiciv.jsonl" ;;
    MedQA)      LOADER_FILE="agentclinic_medqa.jsonl" ;;
    MedQA_Ext)  LOADER_FILE="agentclinic_medqa_extended.jsonl" ;;
    NEJM)       LOADER_FILE="agentclinic_nejm.jsonl" ;;
    NEJM_Ext)   LOADER_FILE="agentclinic_nejm_extended.jsonl" ;;
    *)          LOADER_FILE="agentclinic_medqa_extended.jsonl" ;;
esac

# Only backup/copy if data file differs from the native loader path
NEEDS_COPY=""
DATA_FILE_ABS=$(cd "$(dirname "$DATA_FILE")" && pwd)/$(basename "$DATA_FILE")
LOADER_FILE_ABS="$AGENTCLINIC_DIR/$LOADER_FILE"
if [[ "$DATA_FILE_ABS" != "$LOADER_FILE_ABS" ]]; then
    NEEDS_COPY="1"
    BACKUP_FILE="${LOADER_FILE}.backup_${TIMESTAMP}"
    if [ -f "$LOADER_FILE" ]; then
        cp "$LOADER_FILE" "$BACKUP_FILE"
        echo "Backed up $LOADER_FILE"
    fi
    cp "$DATA_FILE" "$LOADER_FILE"
    echo "Installed dataset ($DATA_FILE -> $LOADER_FILE) with ${NUM_CASES} cases"
else
    echo "Using native dataset: $LOADER_FILE (${NUM_CASES} cases)"
fi

echo ""
echo "Running selected cases..."
echo "--------------------------------------------------------"

run_case() {
    local scenario_id=$1
    local tmp_file="$RESULTS_DIR/tmp_case_${scenario_id}_${TIMESTAMP}.jsonl"

    uv run $DEPS agentclinic_api_only.py \
        --agent_dataset "$AGENT_DATASET" \
        --num_scenarios 1 \
        --scenario_offset "$scenario_id" \
        $COMMON_ARGS \
        --output_file "$tmp_file" 2>/dev/null

    echo "  Completed case $scenario_id"
}

export -f run_case
export RESULTS_DIR TIMESTAMP DEPS COMMON_ARGS AGENT_DATASET

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

# Restore original dataset if we copied
if [[ -n "$NEEDS_COPY" ]]; then
    if [ -f "$BACKUP_FILE" ]; then
        mv "$BACKUP_FILE" "$LOADER_FILE"
        echo "Restored $LOADER_FILE"
    else
        rm -f "$LOADER_FILE"
    fi
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

# Re-evaluate failed cases with full problem_info using gpt-5-mini
REEVAL_SCRIPT="$SCRIPT_DIR/reevaluate_false_cases_full_info.py"
REEVAL_CSV="${OUTPUT_FILE%.jsonl}_false_cases_full_info_eval_${TIMESTAMP}.csv"
if [ -f "$REEVAL_SCRIPT" ]; then
    echo "Re-eval:     running false-case full-info check..."
    uv run $DEPS python "$REEVAL_SCRIPT" \
        --input_jsonl "$OUTPUT_FILE" \
        --output_csv "$REEVAL_CSV" \
        --model "gpt-5-mini" \
        --moderator_model "gpt-5-mini"
    echo "Re-eval CSV: $REEVAL_CSV"
else
    echo "Re-eval:     skipped (script not found: $REEVAL_SCRIPT)"
fi

echo "========================================================"
