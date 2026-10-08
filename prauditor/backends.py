import os
import json
from abc import ABC, abstractmethod
from google import genai

class Backend(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

class MockBackend(Backend):
    def generate(self, prompt: str) -> str:
        return json.dumps([{"type": "adds_tests", "text": "adds tests"}])

class GeminiBackend(Backend):
    def __init__(self):
        self.client = genai.Client()
        self.model = os.getenv("GEMMA_MODEL", "gemma-4-31b-it")
    def generate(self, prompt: str) -> str:
        return "[]"

class OllamaBackend(Backend):
    def __init__(self):
        self.url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.model = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
    def generate(self, prompt: str) -> str:
        return "[]"

def get_backend(name: str) -> Backend:
    if name == "gemini": return GeminiBackend()
    if name == "ollama": return OllamaBackend()
    return MockBackend()
