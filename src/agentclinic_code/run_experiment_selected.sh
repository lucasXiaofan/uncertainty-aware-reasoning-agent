#!/bin/bash

if [ -z "${BASH_VERSION:-}" ]; then
    exec /bin/bash "$0" "$@"
fi

set -e
set -o pipefail

MODEL="gpt-5-nano"
PATIENT_CSV=""
FOLDER_NAME=""
EXPERIMENT_ID=""
WORKERS=1
CUSTOM_DOCTOR_AGENT_PATH=""
NUM_CASES=""
TOTAL_INFERENCES=30

print_usage() {
    cat <<EOF
Usage:
  $0 --patient_csv <osce.jsonl> --num_cases <n> [OPTIONS]

Required:
  --patient_csv <path>              OSCE-format JSONL input file.
  --num_cases <n>                   Number of cases to run from the start of the file.

Options:
  --data_file <path>                Alias for --patient_csv.
  --count <n>                       Alias for --num_cases.
  --folder <name>                   Output folder name under src/agentclinic_code/results.
                                    Default: generated from data file name and timestamp.
  --workers <n>                     Parallel worker count. Default: $WORKERS
  --experiment_id <id>              Shared experiment ID for all case logs.
  --custom_doctor_agent_path <path> Custom doctor agent .py file or directory containing two_agent_interface.py.
                                    Default: src/agentclinic_code/two_phased_agent/two_agent_interface.py
  --model <name>                    Model for doctor, patient, measurement, and moderator. Default: $MODEL
  --total_inferences <n>            Max doctor/patient turns per case. Default: $TOTAL_INFERENCES
  --help, -h                        Show this help.

Example:
  $0 \\
    --patient_csv src/agentclinic_code/data/mimic_testing.jsonl \\
    --folder mimic_test_run \\
    --num_cases 20 \\
    --workers 4 \\
    --custom_doctor_agent_path src/agentclinic_code/two_phased_agent/two_agent_interface.py
EOF
}

require_value() {
    local flag="$1"
    local value="${2:-}"
    if [[ -z "$value" || "$value" == --* ]]; then
        echo "Error: $flag requires a value"
        exit 1
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            print_usage
            exit 0
            ;;
        --patient_csv|--data_file)
            require_value "$1" "${2:-}"
            PATIENT_CSV="$2"
            shift 2
            ;;
        --folder)
            require_value "$1" "${2:-}"
            FOLDER_NAME="$2"
            shift 2
            ;;
        --experiment_id)
            require_value "$1" "${2:-}"
            EXPERIMENT_ID="$2"
            shift 2
            ;;
        --workers)
            require_value "$1" "${2:-}"
            WORKERS="$2"
            shift 2
            ;;
        --custom_doctor_agent_path)
            require_value "$1" "${2:-}"
            CUSTOM_DOCTOR_AGENT_PATH="$2"
            shift 2
            ;;
        --num_cases|--count)
            require_value "$1" "${2:-}"
            NUM_CASES="$2"
            shift 2
            ;;
        --model)
            require_value "$1" "${2:-}"
            MODEL="$2"
            shift 2
            ;;
        --total_inferences)
            require_value "$1" "${2:-}"
            TOTAL_INFERENCES="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

if [[ -z "$PATIENT_CSV" || -z "$NUM_CASES" ]]; then
    echo "Error: --patient_csv/--data_file and --num_cases/--count are required"
    print_usage
    exit 1
fi

for numeric_value in "$WORKERS" "$NUM_CASES" "$TOTAL_INFERENCES"; do
    if [[ ! "$numeric_value" =~ ^[0-9]+$ ]] || [[ "$numeric_value" -eq 0 ]]; then
        echo "Error: numeric options must be positive integers"
        exit 1
    fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$SCRIPT_DIR"
DATA_DIR="$CODE_DIR/data"
RESULTS_DIR="$CODE_DIR/results"
TWO_PHASE_AGENT_PATH="$CODE_DIR/two_phased_agent/two_agent_interface.py"
VISUALIZATION_LOG_DIR="$CODE_DIR/two_phased_agent/log"

resolve_file() {
    local raw="$1"
    local label="$2"
    local candidate

    for candidate in "$raw" "$DATA_DIR/$raw" "$CODE_DIR/$raw"; do
        if [[ -f "$candidate" ]]; then
            python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$candidate"
            return 0
        fi
    done

    echo "Error: $label not found: $raw"
    exit 1
}

resolve_agent_file() {
    local raw="$1"
    local candidate

    if [[ -z "$raw" ]]; then
        return 0
    fi

    for candidate in "$raw" "$CODE_DIR/$raw"; do
        if [[ -f "$candidate" ]]; then
            python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$candidate"
            return 0
        fi
        if [[ -d "$candidate" && -f "$candidate/two_agent_interface.py" ]]; then
            python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$candidate/two_agent_interface.py"
            return 0
        fi
    done

    echo "Error: custom doctor agent not found: $raw"
    exit 1
}

PATIENT_CSV="$(resolve_file "$PATIENT_CSV" "patient_csv")"
if [[ -z "$FOLDER_NAME" ]]; then
    DATA_STEM="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).stem)' "$PATIENT_CSV")"
    FOLDER_NAME="${DATA_STEM}_$(date +%Y%m%d_%H%M%S)_$$"
fi
if [[ -z "$CUSTOM_DOCTOR_AGENT_PATH" ]]; then
    CUSTOM_DOCTOR_AGENT_PATH="$TWO_PHASE_AGENT_PATH"
fi
CUSTOM_DOCTOR_AGENT_PATH="$(resolve_agent_file "$CUSTOM_DOCTOR_AGENT_PATH")"

TOTAL_CASES=$(wc -l < "$PATIENT_CSV" | tr -d ' ')
if [[ "$NUM_CASES" -gt "$TOTAL_CASES" ]]; then
    echo "Error: --num_cases $NUM_CASES exceeds available cases $TOTAL_CASES"
    exit 1
fi

FOLDER_SAFE=$(echo "$FOLDER_NAME" | tr ' /' '__')
if [[ -z "$EXPERIMENT_ID" ]]; then
    EXPERIMENT_ID="$FOLDER_SAFE"
fi
EXP_FOLDER="$RESULTS_DIR/$FOLDER_SAFE"
CASE_DIR="$EXP_FOLDER/cases"
STDOUT_LOG_DIR="$EXP_FOLDER/logs"
OUTPUT_FILE="$EXP_FOLDER/results.csv"
mkdir -p "$CASE_DIR" "$STDOUT_LOG_DIR" "$VISUALIZATION_LOG_DIR"

DEPS=(--with 'openai>=1.0.0' --with regex --with python-dotenv --with pyyaml --with requests)

echo "========================================================"
echo "AgentClinic OSCE Run"
echo "========================================================"
echo "Input:        $PATIENT_CSV"
echo "Output dir:   $EXP_FOLDER"
echo "Cases:        $NUM_CASES / $TOTAL_CASES"
echo "Workers:      $WORKERS"
echo "Model:        $MODEL"
echo "Inferences:   $TOTAL_INFERENCES"
echo "Experiment:   $EXPERIMENT_ID"
if [[ -n "$CUSTOM_DOCTOR_AGENT_PATH" ]]; then
    echo "Doctor agent: $CUSTOM_DOCTOR_AGENT_PATH"
fi
echo "========================================================"

run_case() {
    local case_id="$1"
    local tmp_file="$CASE_DIR/case_${case_id}.csv"
    local log_file="$STDOUT_LOG_DIR/case_${case_id}.log"
    local run_log_file="$VISUALIZATION_LOG_DIR/${FOLDER_SAFE}_case_${case_id}.json"
    local agent_args=()

    if [[ -n "$CUSTOM_DOCTOR_AGENT_PATH" ]]; then
        agent_args=(--custom_doctor_agent_path "$CUSTOM_DOCTOR_AGENT_PATH")
    fi

    rm -f "$tmp_file" "$log_file" "$run_log_file"

    echo "[case $case_id] start"
    if uv run "${DEPS[@]}" python -u "$CODE_DIR/agentclinic_api_only.py" \
        --patient_csv "$PATIENT_CSV" \
        --num_scenarios 1 \
        --scenario_offset "$case_id" \
        --doctor_llm "$MODEL" \
        --patient_llm "$MODEL" \
        --measurement_llm "$MODEL" \
        --moderator_llm "$MODEL" \
        --total_inferences "$TOTAL_INFERENCES" \
        --experiment_id "$EXPERIMENT_ID" \
        "${agent_args[@]}" \
        --output_file "$tmp_file" \
        --run_log_path "$run_log_file" > "$log_file" 2>&1; then
        echo "[case $case_id] done"
    else
        echo "[case $case_id] failed; see $log_file"
        return 1
    fi
}

ACTIVE_PIDS=()
FAILED=0

for ((case_id=0; case_id<NUM_CASES; case_id++)); do
    run_case "$case_id" &
    ACTIVE_PIDS+=("$!")

    if [[ "${#ACTIVE_PIDS[@]}" -ge "$WORKERS" ]]; then
        if ! wait "${ACTIVE_PIDS[0]}"; then
            FAILED=1
        fi
        ACTIVE_PIDS=("${ACTIVE_PIDS[@]:1}")
    fi
done

for pid in "${ACTIVE_PIDS[@]}"; do
    if ! wait "$pid"; then
        FAILED=1
    fi
done

> "$OUTPUT_FILE"
for ((case_id=0; case_id<NUM_CASES; case_id++)); do
    tmp_file="$CASE_DIR/case_${case_id}.csv"
    if [[ -f "$tmp_file" ]]; then
        if [[ "$case_id" -eq 0 ]]; then
            cat "$tmp_file" >> "$OUTPUT_FILE"
        else
            tail -n +2 "$tmp_file" >> "$OUTPUT_FILE"
        fi
    fi
done

PROCESSED=$(($(wc -l < "$OUTPUT_FILE" | tr -d ' ') - 1))
if [[ "$PROCESSED" -lt 0 ]]; then
    PROCESSED=0
fi

echo "========================================================"
echo "Complete"
echo "Results:      $OUTPUT_FILE"
echo "Case logs:    $STDOUT_LOG_DIR"
echo "Viewer logs:  $VISUALIZATION_LOG_DIR/${FOLDER_SAFE}_case_<id>.json"
echo "Experiment:   $EXPERIMENT_ID"
echo "Processed:    $PROCESSED"
echo "========================================================"

exit "$FAILED"
