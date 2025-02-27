import os
import requests
import time
import random
from pathlib import Path
from typing import Optional

class OpenRouterClient:
    def __init__(self, api_keys: list[str], model: str = "deepseek/deepseek-r1:free"):
        if not api_keys:
            raise ValueError("At least one API key is required")
        # Shuffle the API keys to distribute usage randomly
        self.api_keys = list(api_keys)  # Create a copy to avoid modifying the original
        random.shuffle(self.api_keys)
        self.current_key_index = 0
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    def get_next_api_key(self) -> str:
        """Get the next API key in the rotation"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return self.api_keys[self.current_key_index]

    def extract_final_answer(self, response):
        end_think_index = response.find("</think>")
        if end_think_index != -1:
            final_answer = response[end_think_index + len("</think>"):].strip()
            return final_answer
        else:
            return response

    def chat_completion(self, message: str) -> Optional[str]:
        # Try each API key until we get a valid response
        initial_key_index = self.current_key_index
        tried_keys = set()

        while len(tried_keys) < len(self.api_keys):
            current_key = self.api_keys[self.current_key_index]
            tried_keys.add(current_key)

            try:
                # Add a delay to prevent rate limiting
                time.sleep(1)

                headers = {
                    "Authorization": f"Bearer {current_key}",
                    "HTTP-Referer": "https://github.com/blade-finding-filter",
                    "X-Title": "Blade Finding Filter"
                }

                data = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": message}]
                }

                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
                )

                response.raise_for_status()

                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"].strip()
                    if content:  # If we got a non-empty response, return it
                        return self.extract_final_answer(content)

                print(f"[OpenRouter] Empty response from key {self.current_key_index + 1}, trying next key...")
                self.get_next_api_key()

            except Exception as e:
                print(f"[OpenRouter] Error with key {self.current_key_index + 1}: {str(e)}")
                self.get_next_api_key()

        # If we've tried all keys and still got no response, reset to initial key and return None
        self.current_key_index = initial_key_index
        return None

def create_openrouter_client() -> Optional[OpenRouterClient]:
    """Create an OpenRouterClient instance with API keys from config file and environment."""
    api_keys = []

    # Try to read API keys from file in the same directory
    try:
        keys_file = Path('openrouter_keys.txt')
        with open(keys_file, 'r') as f:
            # Skip comment lines and empty lines
            api_keys = [line.strip() for line in f
                       if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print("Warning: OpenRouter API keys file not found at openrouter_keys.txt")

    # Check environment variables for additional keys
    env_keys = []
    i = 1
    while True:
        key = os.getenv(f'OPENROUTER_API_KEY_{i}')
        if not key:
            break
        env_keys.append(key)
        i += 1

    # Combine keys from file and environment
    api_keys.extend(env_keys)

    if not api_keys:
        print("Error: No OpenRouter API keys found in file or environment variables")
        return None

    # Get model from environment variable
    model = os.getenv('OPENROUTER_MODEL', 'deepseek/deepseek-r1:free')  # Default to deepseek-r1:free if not specified
    print(f"[OpenRouter] Using model: {model}")
    print(f"[OpenRouter] Loaded {len(api_keys)} API keys (shuffled)")

    try:
        return OpenRouterClient(api_keys, model=model)
    except Exception as e:
        print(f"Error creating OpenRouter client: {str(e)}")
        return None