#!/bin/bash

# Define output file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"

OUTPUT_FILE="$RESULTS_DIR/benchmark_${TIMESTAMP}.jsonl"
echo "Saving final results to $OUTPUT_FILE"

echo "Starting agentclinic_api_only Parallel Benchmark..."
echo "----------------------------------------------------------------"

# Dependencies for uv run
DEPS="--with openai>=1.0.0 --with regex --with python-dotenv"
COMMON_ARGS="--doctor_llm z-ai/glm-4.6v"

# Function to run a benchmark in the background
run_dataset() {
    local dataset=$1
    local num=$2
    local tmp_file="$RESULTS_DIR/tmp_${dataset}_${TIMESTAMP}.jsonl"
    
    echo "Starting $dataset ($num scenarios)..."
    uv run $DEPS agentclinic_api_only.py --agent_dataset "$dataset" --num_scenarios "$num" $COMMON_ARGS --output_file "$tmp_file"
    echo "Finished $dataset."
}

# Run datasets in parallel
run_dataset "MedQA" 5 &
run_dataset "MedQA_Ext" 5 &
run_dataset "NEJM" 5 &
run_dataset "NEJM_Ext" 5 &
run_dataset "MIMICIV" 5 &

# Wait for all background processes to finish
wait

# Merge results
echo "----------------------------------------------------------------"
echo "Merging results..."
cat "$RESULTS_DIR"/tmp_*_"${TIMESTAMP}".jsonl > "$OUTPUT_FILE"
rm "$RESULTS_DIR"/tmp_*_"${TIMESTAMP}".jsonl

echo "Benchmark complete. Results saved in $OUTPUT_FILE"

echo "Generating report..."
python3 generate_report.py "$OUTPUT_FILE"

