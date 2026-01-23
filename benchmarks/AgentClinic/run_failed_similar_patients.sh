#!/bin/bash

# Script to run only the FAILED similar patient cases
# Uses the pre-generated failed_cases.jsonl

# Define output directory and files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"

OUTPUT_FILE="$RESULTS_DIR/gpt5_mini_failed_similar_cases_${TIMESTAMP}.jsonl"
REPORT_FILE="$RESULTS_DIR/report_failed_cases_${TIMESTAMP}.txt"
FAILED_CASES_FILE="failed_cases.jsonl"

echo "Saving final results to $OUTPUT_FILE"
echo "Report will be generated at $REPORT_FILE"

# Change to the script's directory
cd "$(dirname "$0")" || exit
echo "Changed directory to $(pwd)"

FAILED_CASES_FILE="failed_cases.jsonl"
echo "Using failed cases file: $FAILED_CASES_FILE"

# Check if failed cases file exists
if [ ! -f "$FAILED_CASES_FILE" ]; then
    echo "Error: $FAILED_CASES_FILE not found!"
    exit 1
fi

# Count lines in failed cases file
NUM_CASES=$(wc -l < "$FAILED_CASES_FILE" | tr -d ' ')
echo "Found $NUM_CASES failed cases to process."

# Dependencies for uv run
DEPS="--with openai>=1.0.0 --with regex --with python-dotenv"
COMMON_ARGS="--doctor_llm openai/gpt-5-mini --total_inferences 20"

# Backup original dataset and replace with failed cases dataset
if [ -f "agentclinic_medqa_extended.jsonl" ]; then
    cp "agentclinic_medqa_extended.jsonl" "agentclinic_medqa_extended.jsonl.backup_${TIMESTAMP}"
    echo "Backed up original dataset"
fi

cp "$FAILED_CASES_FILE" "agentclinic_medqa_extended.jsonl"
echo "Installed failed cases dataset"

echo ""
echo "Running cases with parallel workers..."
echo "----------------------------------------------------------------"

# Function to run a specific case by offset
run_case() {
    local scenario_id=$1
    local tmp_file="$RESULTS_DIR/tmp_failed_case_${scenario_id}_${TIMESTAMP}.jsonl"

    echo "Starting case offset $scenario_id..."
    uv run $DEPS agentclinic_api_only.py \
        --agent_dataset MedQA_Ext \
        --num_scenarios 1 \
        --scenario_offset "$scenario_id" \
        $COMMON_ARGS \
        --output_file "$tmp_file"
    echo "Finished case offset $scenario_id."
}

# Export function for parallel execution
export -f run_case
export RESULTS_DIR TIMESTAMP DEPS COMMON_ARGS

# Run all cases
# We have NUM_CASES lines, so offsets are 0 to NUM_CASES-1
seq 0 $(($NUM_CASES - 1)) | xargs -P 8 -I {} bash -c 'run_case "$@"' _ {}

echo "----------------------------------------------------------------"
echo "All cases completed. Merging results..."

# Clear output file and merge results
> "$OUTPUT_FILE"
for i in $(seq 0 $(($NUM_CASES - 1))); do
    tmp_file="$RESULTS_DIR/tmp_failed_case_${i}_${TIMESTAMP}.jsonl"
    if [ -f "$tmp_file" ]; then
        cat "$tmp_file" >> "$OUTPUT_FILE"
    fi
done

# Clean up temporary files
rm -f "$RESULTS_DIR"/tmp_failed_case_*_"${TIMESTAMP}".jsonl

# Restore original dataset
if [ -f "agentclinic_medqa_extended.jsonl.backup_${TIMESTAMP}" ]; then
    mv "agentclinic_medqa_extended.jsonl.backup_${TIMESTAMP}" "agentclinic_medqa_extended.jsonl"
    echo "Restored original dataset"
else
    rm -f "agentclinic_medqa_extended.jsonl"
fi

echo "================================================================"
echo "Benchmark complete. Results saved in $OUTPUT_FILE"

# Generate report
if [ -f "generate_report_v2.py" ]; then
    echo "Generating report..."
    python3 generate_report_v2.py "$OUTPUT_FILE" > "$REPORT_FILE"
    echo "Report saved to $REPORT_FILE"
else
    echo "Warning: generate_report_v2.py not found, skipping report generation"
fi

echo "================================================================"
echo "All done!"
