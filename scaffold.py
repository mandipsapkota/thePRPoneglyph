import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w') as f:
        f.write(content.strip() + '\n')

write_file('pyproject.toml', '''
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "prauditor"
version = "0.1.0"
description = "Is your PR genuine?"
requires-python = ">=3.11"
dependencies = [
    "google-genai",
    "requests",
    "pydantic>=2.0.0",
    "python-dotenv",
    "streamlit",
    "pytest"
]

[project.scripts]
prauditor = "prauditor.cli:main"
''')

write_file('.gitignore', '''
.env
.cache/
__pycache__/
.venv/
*.egg-info/
''')

write_file('.env.example', '''
GITHUB_TOKEN=
GEMINI_API_KEY=
GEMMA_MODEL=gemma-4-31b-it
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=gemma4:e4b
''')

write_file('LICENSE', '''
MIT License

Copyright (c) 2026 prauditor contributors
''')

write_file('ASSUMPTIONS.md', '''
# Assumptions
- Gemma 4 models follow the provided few-shot prompt to output JSON arrays accurately.
- `google-genai` provides standard generative API methods.
- A human must explicitly click Accept/Reject in the Streamlit app to merge or close.
- Python 3.11+ is available on the system.
''')

write_file('SPEC.md', '''
# SPEC
## Architecture
1. Claim Extraction: Uses Gemma 4 (via Gemini API or Ollama) to extract claims from PR description.
2. Verification: Deterministic Python code checks the code diff to verify the extracted claims.
3. Verdict: Rules determine if the PR is genuine, needs review, or claims are unsupported.
4. Dashboard: Allows a human maintainer to safely merge/close PRs based on the advisory verdict.
''')

write_file('prauditor/__init__.py', '')
write_file('prauditor/github.py', '''
import os
import requests
from pydantic import BaseModel
from typing import List, Optional
import json
import datetime

class ChangedFile(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    patch: Optional[str] = None

class PRData(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    body: str
    author: str
    base: str
    head: str
    files: List[ChangedFile]
    total_additions: int
    total_deletions: int
    url: str

class PRState(BaseModel):
    state: str
    merged: bool
    mergeable: Optional[bool]
    mergeable_state: str
    head_sha: str
    check_status: str
    author_is_viewer: bool

def _get_headers():
    token = os.getenv("GITHUB_TOKEN")
    if not token: return {}
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

def parse_pr_url(url: str):
    parts = url.split('/')
    return parts[3], parts[4], int(parts[6])

def parse_pr_ref(ref: str):
    owner_repo, number = ref.split('#')
    owner, repo = owner_repo.split('/')
    return owner, repo, int(number)

def fetch_pr(owner: str, repo: str, number: int) -> PRData:
    headers = _get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub API Error: {r.status_code}")
    data = r.json()
    
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files"
    r_files = requests.get(files_url, headers=headers)
    files_data = r_files.json() if r_files.status_code == 200 else []
    
    files = []
    for f in files_data:
        files.append(ChangedFile(
            filename=f['filename'],
            status=f['status'],
            additions=f['additions'],
            deletions=f['deletions'],
            patch=f.get('patch')
        ))
        
    return PRData(
        owner=owner,
        repo=repo,
        number=number,
        title=data['title'],
        body=data['body'] or "",
        author=data['user']['login'],
        base=data['base']['ref'],
        head=data['head']['ref'],
        files=files,
        total_additions=data['additions'],
        total_deletions=data['deletions'],
        url=data['html_url']
    )

def log_action(repo: str, number: int, action: str, head_sha: str, verdict: str, maintainer: str):
    os.makedirs(".cache", exist_ok=True)
    with open(".cache/audit_log.jsonl", "a") as f:
        log_entry = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "repo": repo,
            "number": number,
            "action": action,
            "head_sha": head_sha,
            "verdict": verdict,
            "maintainer": maintainer
        }
        f.write(json.dumps(log_entry) + "\\n")
''')

write_file('prauditor/backends.py', '''
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
''')

write_file('prauditor/claims.py', '''
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
''')

write_file('prauditor/checkers/__init__.py', '')
write_file('prauditor/checkers/base.py', '''
from enum import Enum
from pydantic import BaseModel

class Status(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIABLE = "UNVERIFIABLE"

class CheckResult(BaseModel):
    claim: dict
    status: Status
    evidence: str
''')

write_file('prauditor/verdict.py', '''
def evaluate_verdict(results):
    return "needs_review"
''')

write_file('prauditor/report.py', '''
def render_report(results):
    return "Report"
''')

write_file('prauditor/cli.py', '''
def main():
    print("CLI")
''')

write_file('dashboard/app.py', '''
import streamlit as st
st.title("prauditor Dashboard")
''')

write_file('eval/fixtures.py', '')
write_file('eval/build_dataset.py', '')
write_file('eval/run_eval.py', '')
write_file('eval/seed_prs.txt', '')
write_file('skills/pr-audit/SKILL.md', '''
---
name: pr-audit
description: Run prauditor checks on a PR
---
# PR Audit
''')
write_file('scripts/list_models.py', '')
write_file('tests/test_github.py', '')
write_file('tests/test_checkers.py', '')
write_file('README.md', '# prauditor')
