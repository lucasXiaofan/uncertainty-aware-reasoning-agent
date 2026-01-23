#!/bin/bash

# Script to run similar patient cases from similar_patient_medqa folder using gpt-5-mini
# Runs the FIRST case from each diagnosis file using a fixed pool of 10 workers
# Change head -5 to head -30 or remove it to process more cases

# Define output directory and files
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"

OUTPUT_FILE="$RESULTS_DIR/gpt5_mini_similar_patients_${TIMESTAMP}.jsonl"
REPORT_FILE="$RESULTS_DIR/report_v2_gpt5_mini_test.txt"

echo "Saving final results to $OUTPUT_FILE"
echo "Report will be generated at $REPORT_FILE"
echo "Starting similar patient cases run with 10 parallel workers..."
echo "================================================================"

# Dependencies for uv run
DEPS="--with openai>=1.0.0 --with regex --with python-dotenv"
COMMON_ARGS="--doctor_llm openai/gpt-5-mini --total_inferences 20"

# Directory containing similar patient cases
SIMILAR_PATIENT_DIR="similar_patient_medqa"

# Get all diagnosis files from similar_patient_medqa (excluding the report)
DIAGNOSIS_FILES=($(ls "$SIMILAR_PATIENT_DIR"/*.jsonl 2>/dev/null | grep -v "diagnosis_grouping_report"))

if [ ${#DIAGNOSIS_FILES[@]} -eq 0 ]; then
    echo "Error: No JSONL files found in $SIMILAR_PATIENT_DIR"
    exit 1
fi

echo "Found ${#DIAGNOSIS_FILES[@]} diagnosis files to process (first case from each)"

# Create a combined dataset with first case from each diagnosis file
COMBINED_DATASET="$RESULTS_DIR/combined_dataset_${TIMESTAMP}.jsonl"
> "$COMBINED_DATASET"

echo ""
echo "Building combined dataset..."
for diagnosis_file in "${DIAGNOSIS_FILES[@]}"; do
    diagnosis_name=$(basename "$diagnosis_file" .jsonl)
    echo "  - Adding first case from: $diagnosis_name"
    head -1 "$diagnosis_file" >> "$COMBINED_DATASET"
done

# Backup original dataset and replace with combined dataset
if [ -f "agentclinic_medqa_extended.jsonl" ]; then
    cp "agentclinic_medqa_extended.jsonl" "agentclinic_medqa_extended.jsonl.backup_${TIMESTAMP}"
    echo "Backed up original dataset"
fi

cp "$COMBINED_DATASET" "agentclinic_medqa_extended.jsonl"
echo "Installed combined dataset with ${#DIAGNOSIS_FILES[@]} cases"

echo ""
echo "Running cases with 10 parallel workers..."
echo "----------------------------------------------------------------"

# Function to run a specific case by offset
run_case() {
    local scenario_id=$1
    local tmp_file="$RESULTS_DIR/tmp_case_${scenario_id}_${TIMESTAMP}.jsonl"

    echo "Starting case $scenario_id..."
    uv run $DEPS agentclinic_api_only.py \
        --agent_dataset MedQA_Ext \
        --num_scenarios 1 \
        --scenario_offset "$scenario_id" \
        $COMMON_ARGS \
        --output_file "$tmp_file"
    echo "Finished case $scenario_id."
}

# Export function for parallel execution
export -f run_case
export RESULTS_DIR TIMESTAMP DEPS COMMON_ARGS

# Run all cases with 10 fixed workers using xargs
seq 0 $((${#DIAGNOSIS_FILES[@]} - 1)) | xargs -P 10 -I {} bash -c 'run_case "$@"' _ {}

echo "----------------------------------------------------------------"
echo "All cases completed. Merging results..."

# Clear output file and merge results
> "$OUTPUT_FILE"
for i in $(seq 0 $((${#DIAGNOSIS_FILES[@]} - 1))); do
    tmp_file="$RESULTS_DIR/tmp_case_${i}_${TIMESTAMP}.jsonl"
    if [ -f "$tmp_file" ]; then
        cat "$tmp_file" >> "$OUTPUT_FILE"
    fi
done

# Clean up temporary files
rm -f "$RESULTS_DIR"/tmp_case_*_"${TIMESTAMP}".jsonl
rm -f "$COMBINED_DATASET"

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
echo "Results: $OUTPUT_FILE"
echo "Report: $REPORT_FILE"
