# MediQ with OpenAI-Compatible APIs

This directory contains an OpenAI-compatible version of the MediQ benchmark that works with OpenRouter, DeepSeek, OpenAI, and other OpenAI-compatible API providers.

## Setup

### 1. Install Dependencies

```bash
pip install openai python-dotenv
```

### 2. Configure Environment Variables

Create a `.env` file in your project root (or in the `benchmarks/mediQ` directory):

```bash
# For OpenRouter (recommended for access to multiple models)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# For DeepSeek (if using DeepSeek directly)
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# For OpenAI (if using OpenAI models)
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Get API Keys

- **OpenRouter**: Sign up at [https://openrouter.ai/](https://openrouter.ai/) for access to multiple models including DeepSeek, Llama, Claude, etc.
- **DeepSeek**: Sign up at [https://platform.deepseek.com/](https://platform.deepseek.com/) for direct DeepSeek access
- **OpenAI**: Get keys from [https://platform.openai.com/](https://platform.openai.com/)

## Usage

### Basic Usage with OpenRouter

Run the benchmark with DeepSeek via OpenRouter (default configuration):

```bash
python run_mediq_openai.py \
  --num_patients 10 \
  --model_name "deepseek/deepseek-chat-v3" \
  --api_account "openrouter"
```

### Using Different Models

#### DeepSeek Direct API
```bash
python run_mediq_openai.py \
  --num_patients 10 \
  --model_name "deepseek-chat" \
  --api_account "deepseek"
```

#### OpenAI Models
```bash
python run_mediq_openai.py \
  --num_patients 10 \
  --model_name "gpt-4-turbo-preview" \
  --api_account "openai"
```

#### Other OpenRouter Models
```bash
# Using Llama via OpenRouter
python run_mediq_openai.py \
  --num_patients 10 \
  --model_name "meta-llama/llama-3.3-70b-instruct" \
  --api_account "openrouter"

# Using Claude via OpenRouter
python run_mediq_openai.py \
  --num_patients 10 \
  --model_name "anthropic/claude-3.5-sonnet" \
  --api_account "openrouter"
```

### Advanced Configuration

#### Custom Expert Class
```bash
python run_mediq_openai.py \
  --num_patients 10 \
  --model_name "deepseek/deepseek-chat-v3" \
  --expert_class "ScaleExpert"  # Other options: RareMethod1LucasVer, BasicExpert, etc.
```

#### Adjust Generation Parameters
```bash
python run_mediq_openai.py \
  --num_patients 10 \
  --model_name "deepseek/deepseek-chat-v3" \
  --temperature 0.7 \
  --max_tokens 2000 \
  --top_p 0.95 \
  --max_questions 5
```

#### Custom API Base URL
```bash
python run_mediq_openai.py \
  --num_patients 10 \
  --model_name "your-custom-model" \
  --api_account "custom" \
  --api_base_url "https://your-custom-endpoint.com/v1"
```

## Command-Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--num_patients` | 10 | Number of patients to evaluate |
| `--model_name` | `deepseek/deepseek-chat-v3` | Model identifier |
| `--api_account` | `openrouter` | API provider (openrouter, deepseek, openai) |
| `--api_base_url` | None | Custom API base URL (optional) |
| `--expert_class` | `RareMethod1LucasVer` | Expert class to use |
| `--max_questions` | 3 | Maximum questions the expert can ask |
| `--temperature` | 0.6 | Sampling temperature (0.0-1.0) |
| `--max_tokens` | 1500 | Maximum tokens to generate |
| `--top_p` | 0.9 | Top-p sampling value |
| `--data_dir` | `data` | Data directory (relative to mediQ dir) |
| `--output_dir` | `outputs` | Output directory for results |
| `--log_dir` | `logs` | Directory for logs |

## Architecture

The OpenAI-compatible version consists of:

- `helper_openai.py`: OpenAI-compatible API client (replaces original helper.py)
- `expert_openai.py`: Expert module using OpenAI helper
- `expert_functions_openai.py`: Expert functions using OpenAI helper
- `expert_basics_openai.py`: Basic expert operations using OpenAI helper
- `patient_openai.py`: Patient module using OpenAI helper
- `run_mediq_openai.py`: Runner script for the OpenAI version

## Output Files

After running, you'll find:

```
outputs/
  mediq_<model>_<timestamp>.jsonl  # Results

logs/
  mediq_<model>_<timestamp>.log         # General log
  mediq_<model>_history_<timestamp>.log # Interaction history
  mediq_<model>_detail_<timestamp>.log  # Detailed prompts/responses
  mediq_<model>_messages_<timestamp>.log # API messages
```

## Troubleshooting

### API Key Not Found
```
Error: No API key found for account 'openrouter'
```
**Solution**: Make sure your `.env` file contains the correct API key and is in the right location.

### Model Not Found
```
Error: Model not found
```
**Solution**: Check the model name format. For OpenRouter, use `provider/model-name` format (e.g., `deepseek/deepseek-chat-v3`).

### Rate Limiting
If you encounter rate limits, try:
- Reducing `--num_patients`
- Using a different model tier
- Adding delays between requests (requires code modification)

## Examples

### Quick Test (2 patients)
```bash
python run_mediq_openai.py --num_patients 2
```

### Full Evaluation (100 patients)
```bash
python run_mediq_openai.py \
  --num_patients 100 \
  --model_name "deepseek/deepseek-chat-v3" \
  --temperature 0.6 \
  --max_questions 5 \
  --output_dir "outputs/full_eval" \
  --log_dir "logs/full_eval"
```

### Compare Multiple Models
```bash
# Run with DeepSeek
python run_mediq_openai.py --num_patients 20 --model_name "deepseek/deepseek-chat-v3"

# Run with GPT-4
python run_mediq_openai.py --num_patients 20 --model_name "gpt-4-turbo-preview" --api_account "openai"

# Run with Llama
python run_mediq_openai.py --num_patients 20 --model_name "meta-llama/llama-3.3-70b-instruct"
```

## Notes

- The OpenAI version is optimized for API-based models only (no local model support)
- Uses the same prompts and evaluation logic as the original MediQ benchmark
- Supports all OpenAI-compatible endpoints that follow the chat completions API format
- Token usage is tracked and logged for cost estimation
