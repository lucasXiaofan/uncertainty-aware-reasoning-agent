#!/bin/bash
# Interactive AgentClinic session - play as the human doctor
# Usage: ./run_interactive.sh [path/to/file.jsonl]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTCLINIC_DIR="$(dirname "$SCRIPT_DIR")"

# ── 1. Pick the data file ────────────────────────────────────────────────────

DEFAULT_DATA_FILE="$AGENTCLINIC_DIR/agentclinic_medqa_extended_fixed.jsonl"

if [[ -n "$1" ]]; then
    DATA_FILE="$1"
else
    # List only source dataset files (agentclinic_*.jsonl) in the AgentClinic directory
    mapfile -t JSONL_FILES < <(find "$AGENTCLINIC_DIR" -maxdepth 1 -name "agentclinic_*.jsonl" | sort)
    if [[ ${#JSONL_FILES[@]} -eq 0 ]]; then
        echo "No agentclinic_*.jsonl dataset files found in $AGENTCLINIC_DIR"
        exit 1
    fi

    echo "Available datasets:"
    for i in "${!JSONL_FILES[@]}"; do
        if [[ "${JSONL_FILES[$i]}" == "$DEFAULT_DATA_FILE" ]]; then
            echo "  $((i+1))) $(basename "${JSONL_FILES[$i]}")  [default]"
        else
            echo "  $((i+1))) $(basename "${JSONL_FILES[$i]}")"
        fi
    done
    echo ""
    read -rp "Select dataset [1-${#JSONL_FILES[@]}] (Enter = default): " choice
    if [[ -z "$choice" ]]; then
        DATA_FILE="$DEFAULT_DATA_FILE"
    elif [[ ! "$choice" =~ ^[0-9]+$ ]] || [[ "$choice" -lt 1 ]] || [[ "$choice" -gt ${#JSONL_FILES[@]} ]]; then
        echo "Invalid choice"
        exit 1
    else
        DATA_FILE="${JSONL_FILES[$((choice-1))]}"
    fi
fi

if [[ ! -f "$DATA_FILE" ]]; then
    echo "Error: file not found: $DATA_FILE"
    exit 1
fi

NUM_CASES=$(wc -l < "$DATA_FILE" | tr -d ' ')
echo ""
echo "Dataset: $(basename "$DATA_FILE")  ($NUM_CASES cases, IDs 0–$((NUM_CASES-1)))"
echo ""

# ── 2. Pick the scenario ID ──────────────────────────────────────────────────

read -rp "Enter scenario ID [0-$((NUM_CASES-1))]: " SCENARIO_ID
if [[ ! "$SCENARIO_ID" =~ ^[0-9]+$ ]] || [[ "$SCENARIO_ID" -ge "$NUM_CASES" ]]; then
    echo "Error: invalid scenario ID '$SCENARIO_ID'"
    exit 1
fi

# ── 3. Auto-detect agent_dataset from filename ───────────────────────────────

DATA_BASENAME=$(basename "$DATA_FILE")
case "$DATA_BASENAME" in
    agentclinic_mimiciv*)    AGENT_DATASET="MIMICIV" ;;
    agentclinic_nejm_ext*)   AGENT_DATASET="NEJM_Ext" ;;
    agentclinic_nejm*)       AGENT_DATASET="NEJM" ;;
    agentclinic_medqa_ext*)  AGENT_DATASET="MedQA_Ext" ;;
    *)                       AGENT_DATASET="MedQA_Ext" ;;
esac

# Map dataset to the filename the Python loader expects
case "$AGENT_DATASET" in
    MIMICIV)   LOADER_FILE="agentclinic_mimiciv.jsonl" ;;
    MedQA)     LOADER_FILE="agentclinic_medqa.jsonl" ;;
    MedQA_Ext) LOADER_FILE="agentclinic_medqa_extended.jsonl" ;;
    NEJM)      LOADER_FILE="agentclinic_nejm.jsonl" ;;
    NEJM_Ext)  LOADER_FILE="agentclinic_nejm_extended.jsonl" ;;
    *)         LOADER_FILE="agentclinic_medqa_extended.jsonl" ;;
esac

# ── 4. Copy data file into the expected loader path if needed ────────────────

DATA_FILE_ABS=$(cd "$(dirname "$DATA_FILE")" && pwd)/$(basename "$DATA_FILE")
LOADER_FILE_ABS="$AGENTCLINIC_DIR/$LOADER_FILE"
BACKUP_FILE=""

if [[ "$DATA_FILE_ABS" != "$LOADER_FILE_ABS" ]]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="${LOADER_FILE_ABS}.backup_${TIMESTAMP}"
    if [[ -f "$LOADER_FILE_ABS" ]]; then
        cp "$LOADER_FILE_ABS" "$BACKUP_FILE"
    fi
    cp "$DATA_FILE" "$LOADER_FILE_ABS"
fi

restore() {
    if [[ -n "$BACKUP_FILE" ]]; then
        if [[ -f "$BACKUP_FILE" ]]; then
            mv "$BACKUP_FILE" "$LOADER_FILE_ABS"
        else
            rm -f "$LOADER_FILE_ABS"
        fi
    fi
}
trap restore EXIT

# ── 5. Launch ────────────────────────────────────────────────────────────────

echo ""
echo "========================================================"
echo "  AgentClinic – Interactive Session"
echo "  Dataset:  $(basename "$DATA_FILE")  ($AGENT_DATASET)"
echo "  Scenario: $SCENARIO_ID"
echo "  You are the doctor. Type your questions/orders."
echo "========================================================"
echo ""

cd "$AGENTCLINIC_DIR"
INTERACTIVE_MODEL="${INTERACTIVE_MODEL:-gpt-5-mini}"
uv run \
    --with "openai>=1.0.0" \
    --with regex \
    --with python-dotenv \
    --with pyyaml \
    agentclinic_api_only.py \
    --inf_type human_doctor \
    --doctor_llm "$INTERACTIVE_MODEL" \
    --patient_llm "$INTERACTIVE_MODEL" \
    --measurement_llm "$INTERACTIVE_MODEL" \
    --moderator_llm "$INTERACTIVE_MODEL" \
    --agent_dataset "$AGENT_DATASET" \
    --scenario_offset "$SCENARIO_ID" \
    --num_scenarios 1
