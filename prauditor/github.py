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
        f.write(json.dumps(log_entry) + "\n")
