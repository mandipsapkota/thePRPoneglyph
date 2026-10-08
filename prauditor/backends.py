import os
import json
import hashlib
import time
import requests
from abc import ABC, abstractmethod
from google import genai

class Backend(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

def get_cache_path(model: str, prompt: str) -> str:
    h = hashlib.sha256((model + prompt).encode('utf-8')).hexdigest()
    os.makedirs(".cache", exist_ok=True)
    return os.path.join(".cache", h + ".json")

def read_cache(model: str, prompt: str):
    path = get_cache_path(model, prompt)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f).get("response")
    return None

def write_cache(model: str, prompt: str, response: str):
    path = get_cache_path(model, prompt)
    with open(path, "w") as f:
        json.dump({"response": response}, f)

def with_retry(func):
    def wrapper(*args, **kwargs):
        tries = 0
        max_tries = 3
        while tries < max_tries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                tries += 1
                if tries >= max_tries:
                    raise e
                time.sleep(1)
    return wrapper

class MockBackend(Backend):
    def generate(self, prompt: str) -> str:
        return json.dumps([{"type": "adds_tests", "text": "adds tests"}])

class GeminiBackend(Backend):
    # Class-level shared state so model check only happens once across all instances
    _shared_client = None
    _resolved_model = None

    def __init__(self):
        if GeminiBackend._shared_client is None:
            GeminiBackend._shared_client = genai.Client()
            # Resolve model once
            target = os.getenv("GEMMA_MODEL", "gemma-4-31b-it")
            try:
                models = list(GeminiBackend._shared_client.models.list())
                available = [m.name for m in models]
                prefixed = f"models/{target}"
                if prefixed in available or target in available:
                    GeminiBackend._resolved_model = target
                else:
                    gemma = [m.name for m in models if "gemma-4" in m.name]
                    GeminiBackend._resolved_model = gemma[0].replace("models/", "") if gemma else target
            except Exception:
                GeminiBackend._resolved_model = target

        self.client = GeminiBackend._shared_client
        self.model = GeminiBackend._resolved_model

    @with_retry
    def _call_api(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return response.text

    def generate(self, prompt: str) -> str:
        cached = read_cache(self.model, prompt)
        if cached is not None:
            return cached
        result = self._call_api(prompt)
        write_cache(self.model, prompt, result)
        return result

class OllamaBackend(Backend):
    def __init__(self):
        self.url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")

    @with_retry
    def _call_api(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0
        }
        resp = requests.post(f"{self.url}/chat/completions", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def generate(self, prompt: str) -> str:
        cached = read_cache(self.model, prompt)
        if cached is not None:
            return cached
        result = self._call_api(prompt)
        write_cache(self.model, prompt, result)
        return result

# Singleton cache for backends so we don't re-create them on every call
_backend_cache = {}

def get_backend(name: str) -> Backend:
    if name not in _backend_cache:
        if name == "gemini":
            _backend_cache[name] = GeminiBackend()
        elif name == "ollama":
            _backend_cache[name] = OllamaBackend()
        else:
            _backend_cache[name] = MockBackend()
    return _backend_cache[name]
