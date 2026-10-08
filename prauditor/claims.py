import json
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ValidationError

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

PROMPT_TEMPLATE = """
Extract claims from the following PR description. Only extract explicit claims, do not infer.
Output ONLY a JSON array of objects with keys: "type" (string), "text" (string), "symbols" (array of strings).

Types:
adds_tests: claims about adding or updating tests.
docs_only: claims that the PR only updates documentation.
typo_fix: claims that the PR fixes a typo.
no_behavior_change: claims that the PR does not change behavior (e.g. refactor).
references_symbol: claims about specific symbols (variables, functions, classes).
other: any other specific claim.

Examples:
PR: "Fixed a typo in the main header" -> [{{"type": "typo_fix", "text": "Fixed a typo in the main header", "symbols": []}}]
PR: "Adds comprehensive tests for user login" -> [{{"type": "adds_tests", "text": "Adds comprehensive tests for user login", "symbols": []}}]
PR: "Docs only. Updated `run_audit` function signature." -> [{{"type": "docs_only", "text": "Docs only.", "symbols": []}}, {{"type": "references_symbol", "text": "Updated `run_audit` function signature.", "symbols": ["run_audit"]}}]

PR Title: {title}
PR Body: {body}
"""

def extract_claims(backend, title: str, body: str) -> ClaimExtraction:
    prompt = PROMPT_TEMPLATE.format(title=title, body=body[:2000])
    
    def parse(response_text):
        try:
            # simple markdown extraction
            text = response_text.strip()
            if text.startswith("```json"):
                text = text.split("```json")[1].split("```")[0].strip()
            elif text.startswith("```"):
                text = text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(text)
            claims = [Claim(**item) for item in data]
            return ClaimExtraction(claims=claims, ok=True)
        except Exception as e:
            return str(e)
            
    response = backend.generate(prompt)
    result = parse(response)
    
    if isinstance(result, str):
        # retry once
        response2 = backend.generate(prompt + f"\\n\\nPrevious error: {result}\\nPlease output ONLY valid JSON array.")
        result2 = parse(response2)
        if isinstance(result2, str):
            return ClaimExtraction(claims=[], ok=False, error=result2)
        return result2
        
    return result
