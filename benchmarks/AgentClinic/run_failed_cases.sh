#!/bin/bash

# Define output file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"

OUTPUT_FILE="$RESULTS_DIR/consistent_test_4_nogpt4_30interactions_glm_46v.jsonl"
echo "Saving final results to $OUTPUT_FILE"

echo "Starting re-run of 10 failed cases in parallel..."
echo "----------------------------------------------------------------"

# Dependencies for uv run
DEPS="--with openai>=1.0.0 --with regex --with python-dotenv"
COMMON_ARGS="--doctor_llm z-ai/glm-4.6v --total_inferences 30"

# Function to run a specific case
run_case() {
    local dataset=$1
    local scenario_id=$2
    local tmp_file="$RESULTS_DIR/tmp_failed_${dataset}_${scenario_id}_${TIMESTAMP}.jsonl"
    
    echo "Starting $dataset (Scenario ID $scenario_id)..."
    uv run $DEPS agentclinic_api_only.py --agent_dataset "$dataset" --num_scenarios 1 --scenario_offset "$scenario_id" $COMMON_ARGS --output_file "$tmp_file"
    echo "Finished $dataset Scenario $scenario_id."
}

# Run the 10 failed cases in parallel
run_case "MedQA" 0 &
run_case "MedQA" 2 &
run_case "MedQA_Ext" 1 &
run_case "MedQA_Ext" 2 &
run_case "MIMICIV" 1 &
run_case "MIMICIV" 3 &
run_case "MIMICIV" 4 &
run_case "NEJM" 1 &
run_case "NEJM_Ext" 0 &
run_case "NEJM_Ext" 1 &

# Wait for all background processes to finish
wait

# Merge results
echo "----------------------------------------------------------------"
echo "Merging results..."
# Clear output file first
> "$OUTPUT_FILE"
cat "$RESULTS_DIR"/tmp_failed_*_"${TIMESTAMP}".jsonl >> "$OUTPUT_FILE"
rm "$RESULTS_DIR"/tmp_failed_*_"${TIMESTAMP}".jsonl

echo "Benchmark complete. Results saved in $OUTPUT_FILE"

echo "Generating report..."
python3 generate_report.py "$OUTPUT_FILE"
