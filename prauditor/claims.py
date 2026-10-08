from enum import Enum
from pydantic import BaseModel, ValidationError
from typing import List, Optional
import json

class ClaimType(str, Enum):
    adds_tests = "adds_tests"
    docs_only = "docs_only"
    typo_fix = "typo_fix"
    no_behavior_change = "no_behavior_change"
    references_symbol = "references_symbol"
    other = "other"

class Claim(BaseModel):
    type: ClaimType
    text: str
    symbols: List[str] = []

class ClaimExtraction(BaseModel):
    claims: List[Claim]
    ok: bool
    error: Optional[str] = None

def extract_claims(backend, title: str, body: str) -> ClaimExtraction:
    return ClaimExtraction(claims=[], ok=True)
