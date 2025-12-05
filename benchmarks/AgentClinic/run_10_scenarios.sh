#!/bin/bash

# Extract OPENAI_API_KEY
export OPENAI_API_KEY=$(grep "OPENAI_API_KEY" ../../.env | cut -d '=' -f2 | tr -d '"' | tr -d "'")

# Define the datasets and number of scenarios for each to total 10
# MedQA: 3
# MedQA_Ext: 3
# NEJM: 2
# NEJM_Ext: 2
# Total: 10

echo "Starting agentclinic_api_only Benchmark (10 scenarios total)..."
echo "----------------------------------------------------------------"

echo "Running MedQA (3 scenarios)..."
uv run --with openai==0.28.0 --with regex agentclinic_api_only.py --agent_dataset MedQA --num_scenarios 3 --doctor_llm gpt-5-mini --openai_api_key "$OPENAI_API_KEY"
echo "----------------------------------------------------------------"

echo "Running MedQA_Ext (3 scenarios)..."
uv run --with openai==0.28.0 --with regex agentclinic_api_only.py --agent_dataset MedQA_Ext --num_scenarios 3 --doctor_llm gpt-5-mini --openai_api_key "$OPENAI_API_KEY"
echo "----------------------------------------------------------------"

echo "Running NEJM (2 scenarios)..."
uv run --with openai==0.28.0 --with regex agentclinic_api_only.py --agent_dataset NEJM --num_scenarios 2 --doctor_llm gpt-5-mini --openai_api_key "$OPENAI_API_KEY"
echo "----------------------------------------------------------------"

echo "Running NEJM_Ext (2 scenarios)..."
uv run --with openai==0.28.0 --with regex agentclinic_api_only.py --agent_dataset NEJM_Ext --num_scenarios 2 --doctor_llm gpt-5-mini --openai_api_key "$OPENAI_API_KEY"
echo "----------------------------------------------------------------"

echo "Benchmark complete."
