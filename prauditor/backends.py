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
        max_tries = 4
        while tries < max_tries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                tries += 1
                if tries >= max_tries:
                    raise e
                time.sleep(2 ** tries)
    return wrapper

class MockBackend(Backend):
    def generate(self, prompt: str) -> str:
        return json.dumps([{"type": "adds_tests", "text": "adds tests"}])

class GeminiBackend(Backend):
    def __init__(self):
        self.client = genai.Client()
        self.model = os.getenv("GEMMA_MODEL", "gemma-4-31b-it")
        self._checked_model = False

    def _ensure_model(self):
        if self._checked_model:
            return
        
        try:
            models = list(self.client.models.list())
            available_names = [m.name for m in models]
            
            model_name = self.model
            if not model_name.startswith('models/'):
                model_name = f'models/{self.model}'
                
            if model_name not in available_names and self.model not in available_names:
                gemma_models = [m.name for m in models if "gemma-4" in m.name]
                if not gemma_models:
                    raise RuntimeError("No gemma-4 models found in Gemini API.")
                self.model = gemma_models[0].replace('models/', '')
                print(f"Configured model not found. Using: {self.model}")
        except Exception:
            pass
            
        self._checked_model = True

    @with_retry
    def _call_api(self, prompt: str) -> str:
        self._ensure_model()
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
        resp = requests.post(f"{self.url}/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def generate(self, prompt: str) -> str:
        cached = read_cache(self.model, prompt)
        if cached is not None:
            return cached
        result = self._call_api(prompt)
        write_cache(self.model, prompt, result)
        return result

def get_backend(name: str) -> Backend:
    if name == "gemini": return GeminiBackend()
    if name == "ollama": return OllamaBackend()
    return MockBackend()
