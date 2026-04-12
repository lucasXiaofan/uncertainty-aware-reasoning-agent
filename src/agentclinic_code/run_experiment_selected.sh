#!/bin/bash

# Run selected AgentClinic cases from a dataset file
# Usage:
#   ./run_experiment_selected.sh --model <model> --data_file <path> {--ids <list> | --count <num>} [OPTIONS]
#
# Required:
#   --model <str>      Model for all agents. Default: gpt-5-nano.
#   --data_file <path> Path to the dataset (.jsonl) file.
#   --ids <list>       Select specific case IDs (comma-separated, e.g. 0,2,8,15).
#     OR
#   --count <num>      Evaluate a specified number of cases (first N, or random N with --random).
#
# Selection Options:
#   --start <idx>      (Optional) Start evaluating from index <idx> (0-indexed). Default: 0
#   --random           (Optional) Select <count> random cases rather than sequential ones.
#   --ids_1based       (Optional) Treat provided IDs as 1-based indices instead of 0-based.
#
# Output & Execution Options:
#   --name <str>       (Optional) Experiment name prefix for the output JSONL file.
#   --folder <str>     (Optional) Output folder name. Default: experiment_<timestamp>
#   --workers <num>    (Optional) Number of parallel workers. Default: 10
#
# Agent Configuration Options:
#   --knowledge <mode> (Optional) External knowledge mode: none|symptom|diagnosis|both. Default: none
#
# Other Options:
#   --agent_dataset <dataset> (Optional) Override dataset handler (e.g. MIMICIV, NEJM, MedQA, NewMedQA). Auto-inferred otherwise.
#
# Examples:
#   ./run_experiment_selected.sh --data_file data/agentclinic_mimiciv.jsonl --count 50
#   ./run_experiment_selected.sh --model gpt-5-nano --data_file agentclinic_mimiciv.jsonl --ids 2,8,15
#   ./run_experiment_selected.sh --data_file data/agentclinic_mimiciv.jsonl --count 10 --knowledge symptom
set -e

MODEL="gpt-5-nano"

EXPERIMENT_NAME=""
FOLDER_NAME=""
WORKERS=10
DATA_FILE_OVERRIDE=""
IDS_1BASED=""
COUNT=""
START_INDEX=0
RANDOM_SELECT=""
AGENT_DATASET=""
KNOWLEDGE_MODE="none"

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
        --name)
            EXPERIMENT_NAME="$2"
            shift 2
            ;;
        --folder)
            FOLDER_NAME="$2"
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
        --knowledge)
            KNOWLEDGE_MODE="$2"
            if [[ ! "$KNOWLEDGE_MODE" =~ ^(none|symptom|diagnosis|both)$ ]]; then
                echo "Error: --knowledge must be one of: none, symptom, diagnosis, both"
                exit 1
            fi
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --model <model> --data_file <path> {--ids <list> | --count <num>} [OPTIONS]"
            exit 1
            ;;
    esac
done

if [[ -z "$DATA_FILE_OVERRIDE" ]]; then
    echo "Error: --data_file is required"
    exit 1
fi

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
CODE_DIR="$SCRIPT_DIR"
DATA_DIR="$CODE_DIR/data"
RESULTS_DIR="$CODE_DIR/results"

resolve_data_file() {
    local raw="$1"
    if [[ -f "$raw" ]]; then
        python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$raw"
        return 0
    fi

    if [[ -f "$DATA_DIR/$raw" ]]; then
        python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$DATA_DIR/$raw"
        return 0
    fi

    echo "Error: Data file not found: $raw"
    echo "Checked:"
    echo "  $raw"
    echo "  $DATA_DIR/$raw"
    exit 1
}

DATA_FILE="$(resolve_data_file "$DATA_FILE_OVERRIDE")"
DATA_BASENAME="$(basename "$DATA_FILE")"

# Auto-detect agent_dataset from data file if not specified
if [[ -z "$AGENT_DATASET" ]]; then
    DATA_PATH_LC=$(printf '%s' "$DATA_FILE" | tr '[:upper:]' '[:lower:]')
    if [[ "$DATA_PATH_LC" == *"mimic"* ]]; then
        AGENT_DATASET="MIMICIV"
    elif [[ "$DATA_PATH_LC" == *"nejm_ext"* ]] || [[ "$DATA_PATH_LC" == *"nejm_extended"* ]]; then
        AGENT_DATASET="NEJM_Ext"
    elif [[ "$DATA_PATH_LC" == *"nejm"* ]]; then
        AGENT_DATASET="NEJM"
    elif [[ "$DATA_PATH_LC" == *"new_medqa_similar_cases"* ]]; then
        AGENT_DATASET="NewMedQA"
    elif [[ "$DATA_PATH_LC" == *"medqa_ext"* ]] || [[ "$DATA_PATH_LC" == *"medqa_extended"* ]]; then
        AGENT_DATASET="MedQA_Ext"
    elif [[ "$DATA_PATH_LC" == *"medqa"* ]]; then
        AGENT_DATASET="MedQA"
    else
        AGENT_DATASET="MedQA_Ext"
    fi
fi

# Create results directory
mkdir -p "$RESULTS_DIR"

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

# Experiment output folder
if [[ -n "$FOLDER_NAME" ]]; then
    FOLDER_SAFE=$(echo "$FOLDER_NAME" | tr ' /' '_')
    EXP_FOLDER="$RESULTS_DIR/$FOLDER_SAFE"
else
    EXP_FOLDER="$RESULTS_DIR/experiment_${TIMESTAMP}"
fi
mkdir -p "$EXP_FOLDER"

MEMORY_SUFFIX=""

# Build filename
BASE_NAME=$(basename "$DATA_FILE")
BASE_NAME=${BASE_NAME%.jsonl}

if [[ -n "$EXPERIMENT_NAME" ]]; then
    EXPERIMENT_SAFE=$(echo "$EXPERIMENT_NAME" | tr ' /' '_')
    OUTPUT_FILE="$EXP_FOLDER/${EXPERIMENT_SAFE}_${MODEL_SAFE}_${TIMESTAMP}.jsonl"
else
    OUTPUT_FILE="$EXP_FOLDER/${BASE_NAME}_${MODEL_SAFE}_selected_${TIMESTAMP}.jsonl"
fi

echo "========================================================"
echo "High-Transfer Clusters Experiment (Selected Cases)"
echo "========================================================"
echo "Split/Data:         $DATA_FILE"
echo "Agent Dataset:      $AGENT_DATASET"
echo "Model:              $MODEL"
echo "Knowledge:          $KNOWLEDGE_MODE"
if [[ -n "$EXPERIMENT_NAME" ]]; then
    echo "Experiment:         $EXPERIMENT_NAME"
fi
echo "Output folder:      $EXP_FOLDER"
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
DEPS="--with openai>=1.0.0 --with regex --with python-dotenv --with pyyaml --with requests"
COMMON_ARGS="--doctor_llm $MODEL --patient_llm $MODEL --measurement_llm $MODEL --moderator_llm $MODEL --total_inferences 20"
COMMON_ARGS="$COMMON_ARGS --knowledge $KNOWLEDGE_MODE"

# Map agent_dataset to the default file the Python loader expects when no
# explicit data_file override is passed.
case "$AGENT_DATASET" in
    MIMICIV)    LOADER_FILE="agentclinic_mimiciv.jsonl" ;;
    MedQA)      LOADER_FILE="agentclinic_medqa.jsonl" ;;
    MedQA_Ext)  LOADER_FILE="agentclinic_medqa_extended.jsonl" ;;
    NEJM)       LOADER_FILE="agentclinic_nejm.jsonl" ;;
    NEJM_Ext)   LOADER_FILE="agentclinic_nejm_extended.jsonl" ;;
    NewMedQA)   LOADER_FILE="new_medqa_similar_cases.jsonl" ;;
    *)          LOADER_FILE="agentclinic_medqa_extended.jsonl" ;;
esac

if [[ "$(basename "$DATA_FILE")" != "$(basename "$LOADER_FILE")" ]]; then
    echo "Info: data_file basename '$DATA_BASENAME' differs from default loader file '$LOADER_FILE' for dataset '$AGENT_DATASET'"
    echo "      Passing --data_file so Python loads the selected file directly."
fi

echo ""
echo "Running selected cases..."
echo "--------------------------------------------------------"

run_case() {
    local scenario_id=$1
    local tmp_file="$EXP_FOLDER/tmp_case_${scenario_id}_${TIMESTAMP}.jsonl"

    uv run $DEPS python "$CODE_DIR/agentclinic_api_only.py" \
        --agent_dataset "$AGENT_DATASET" \
        --data_file "$DATA_FILE" \
        --num_scenarios 1 \
        --scenario_offset "$scenario_id" \
        $COMMON_ARGS \
        --output_file "$tmp_file" 2>/dev/null

    echo "  Completed case $scenario_id"
}

export -f run_case
export CODE_DIR RESULTS_DIR EXP_FOLDER TIMESTAMP DEPS COMMON_ARGS AGENT_DATASET DATA_FILE

printf "%s\n" "${NORMALIZED_IDS[@]}" | xargs -P "$WORKERS" -I {} bash -c 'run_case "$@"' _ {}

echo "--------------------------------------------------------"
echo "Merging results..."

# Merge results
> "$OUTPUT_FILE"
for i in "${NORMALIZED_IDS[@]}"; do
    tmp_file="$EXP_FOLDER/tmp_case_${i}_${TIMESTAMP}.jsonl"
    if [ -f "$tmp_file" ]; then
        cat "$tmp_file" >> "$OUTPUT_FILE"
    fi
done

# Clean up temp files
rm -f "$EXP_FOLDER"/tmp_case_*_"${TIMESTAMP}".jsonl

echo ""
echo "========================================================"
echo "Experiment Complete!"
echo "========================================================"
echo "Results:     $OUTPUT_FILE"

# Generate detailed report if script exists (generates its own report_v2_*.txt file)
if [ -f "$CODE_DIR/generate_report_v2.py" ]; then
    python3 "$CODE_DIR/generate_report_v2.py" "$OUTPUT_FILE" >/dev/null 2>&1
fi

# Show quick summary
TOTAL=$(wc -l < "$OUTPUT_FILE" | tr -d ' ')
echo "Cases:       $TOTAL cases processed"

# Re-evaluate failed cases with full problem_info using the selected model
REEVAL_SCRIPT="$SCRIPT_DIR/reevaluate_false_cases_full_info.py"
REEVAL_CSV="$EXP_FOLDER/false_cases_full_info_eval_${TIMESTAMP}.csv"
if [ -f "$REEVAL_SCRIPT" ]; then
    echo "Re-eval:     running false-case full-info check..."
    uv run $DEPS python "$REEVAL_SCRIPT" \
        --input_jsonl "$OUTPUT_FILE" \
        --output_csv "$REEVAL_CSV" \
        --provider openai \
        --model "$MODEL" \
        --moderator_model "$MODEL"
    echo "Re-eval CSV: $REEVAL_CSV"
else
    echo "Re-eval:     skipped (script not found: $REEVAL_SCRIPT)"
fi

echo "========================================================"
