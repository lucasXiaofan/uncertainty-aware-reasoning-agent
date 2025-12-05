#!/bin/bash

# Extract OPENAI_API_KEY
export OPENAI_API_KEY=$(grep "OPENAI_API_KEY" ../../.env | cut -d '=' -f2 | tr -d '"' | tr -d "'")

echo "API Key length: ${#OPENAI_API_KEY}"

# Define the datasets
datasets=("MedQA" "MedQA_Ext" "NEJM" "NEJM_Ext")

# Loop through each dataset and run the benchmark
for dataset in "${datasets[@]}"; do
    echo "----------------------------------------------------------------"
    echo "Running benchmark for dataset: $dataset"
    echo "----------------------------------------------------------------"
    uv run --with openai==0.28.0 --with replicate==0.23.1 --with anthropic --with transformers --with datasets --with regex agentclinic.py --agent_dataset "$dataset" --num_scenarios 2 --doctor_llm gpt-4o-mini --openai_api_key "$OPENAI_API_KEY"
    echo ""
done
