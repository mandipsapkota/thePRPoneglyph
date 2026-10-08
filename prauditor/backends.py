import os
import json
import hashlib
import time
from abc import ABC, abstractmethod

class Backend(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

def get_backend(name: str) -> Backend:
    if name == "mock":
        return MockBackend()
    return MockBackend()

class MockBackend(Backend):
    def generate(self, prompt: str) -> str:
        return json.dumps([{"type": "adds_tests", "text": "adds tests"}])
