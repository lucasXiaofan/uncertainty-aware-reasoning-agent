import logging
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# A dictionary to cache API clients to avoid recreating them
global models
models = {}

def log_info(message, logger_name="message_logger", print_to_std=False, mode="info"):
    logger = logging.getLogger(logger_name)
    if logger:
        if mode == "error": logger.error(message)
        if mode == "warning": logger.warning(message)
        else: logger.info(message)
    if print_to_std: print(message + "\n")

class ModelCache:
    def __init__(self, model_name, use_api=None, **kwargs):
        self.model_name = model_name
        self.use_api = use_api
        self.client = None
        self.args = kwargs
        self.load_client()

    def load_client(self):
        """Initialize OpenAI-compatible API client"""
        # Get API configuration from kwargs or environment
        api_account = self.args.get("api_account", "openrouter")
        base_url = self.args.get("api_base_url", None)
        api_key = self.args.get("api_key", None)

        # Priority: explicit api_key > environment variable based on account > default env var
        if api_key is None:
            if api_account == "openrouter":
                api_key = os.getenv("OPENROUTER_API_KEY")
                if base_url is None:
                    base_url = "https://openrouter.ai/api/v1"
            elif api_account == "deepseek":
                api_key = os.getenv("DEEPSEEK_API_KEY")
                if base_url is None:
                    base_url = "https://api.deepseek.com"
            elif api_account == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                # OpenAI uses default base_url
            else:
                # Generic case: try to get key from <ACCOUNT>_API_KEY
                api_key = os.getenv(f"{api_account.upper()}_API_KEY")

        if api_key is None:
            raise ValueError(f"No API key found for account '{api_account}'. "
                           f"Please set {api_account.upper()}_API_KEY environment variable "
                           f"or pass api_key explicitly.")

        # Initialize OpenAI client with custom base URL if provided
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            log_info(f"Initialized API client for {api_account} with base_url: {base_url}")
        else:
            self.client = OpenAI(api_key=api_key)
            log_info(f"Initialized API client for {api_account}")

        self.api_account = api_account

    def generate(self, messages):
        """Generate response using OpenAI-compatible API"""
        log_info(f"[{self.model_name}][INPUT]: {messages}")

        # Get generation parameters
        temperature = self.args.get("temperature", 0.6)
        max_tokens = self.args.get("max_tokens", 256)
        top_p = self.args.get("top_p", 0.9)
        top_logprobs = self.args.get("top_logprobs", 0)

        try:
            # Prepare API call parameters
            api_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p
            }

            # Add logprobs if requested
            if top_logprobs > 0:
                api_params["logprobs"] = True
                api_params["top_logprobs"] = top_logprobs

            # Make API call
            response = self.client.chat.completions.create(**api_params)

            # Extract response
            response_text = response.choices[0].message.content.strip()

            # Extract usage stats
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens
            }

            # Extract logprobs if available
            log_probs = None
            if top_logprobs > 0 and hasattr(response.choices[0], 'logprobs'):
                log_probs = response.choices[0].logprobs.content if response.choices[0].logprobs else None

            output_dict = {'response_text': response_text, 'usage': usage, 'log_probs': log_probs}
            log_info(f"[{self.model_name}][OUTPUT]: {output_dict}")

            return response_text, log_probs, usage

        except Exception as e:
            log_info(f"[ERROR] [{self.model_name}]: API call failed: {str(e)}", mode="error")
            raise


def get_response(messages, model_name, use_api=None, **kwargs):
    """
    Get response from OpenAI-compatible API.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model_name: Model identifier (e.g., 'deepseek/deepseek-chat-v3' for OpenRouter)
        use_api: API provider name (e.g., 'openrouter', 'deepseek', 'openai')
        **kwargs: Additional arguments including:
            - api_account: API account name (default: 'openrouter')
            - api_base_url: Custom API base URL
            - api_key: Explicit API key (overrides environment variables)
            - temperature: Sampling temperature (default: 0.6)
            - max_tokens: Maximum tokens to generate (default: 256)
            - top_p: Top-p sampling (default: 0.9)
            - top_logprobs: Number of top logprobs to return (default: 0)

    Returns:
        Tuple of (response_text, log_probs, usage)
    """
    # Auto-detect API provider if not specified
    if use_api is None:
        if 'gpt' in model_name or 'o1' in model_name:
            use_api = "openai"
        elif 'deepseek' in model_name:
            use_api = "deepseek"
        else:
            use_api = kwargs.get("api_account", "openrouter")

    # Create cache key combining model name and API account
    api_account = kwargs.get("api_account", use_api)
    cache_key = f"{model_name}_{api_account}"

    model_cache = models.get(cache_key, None)
    if model_cache is None:
        model_cache = ModelCache(model_name, use_api=use_api, **kwargs)
        models[cache_key] = model_cache

    return model_cache.generate(messages)
