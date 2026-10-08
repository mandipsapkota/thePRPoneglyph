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
    
    files = []
    # Simplified for space
    return PRData(
        owner=owner, repo=repo, number=number,
        title=data.get('title', ''), body=data.get('body', ''),
        author=data.get('user', {}).get('login', ''),
        base=data.get('base', {}).get('ref', ''),
        head=data.get('head', {}).get('ref', ''),
        files=files, total_additions=0, total_deletions=0,
        url=data.get('html_url', '')
    )

def list_open_prs(owner: str, repo: str, limit: int = 30):
    headers = _get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&per_page={limit}"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub API Error {r.status_code}: {r.text}")
    
    prs = []
    for data in r.json():
        prs.append(PRData(
            owner=owner, repo=repo, number=data['number'],
            title=data.get('title', ''), body=data.get('body', '') or '',
            author=data.get('user', {}).get('login', ''),
            base=data.get('base', {}).get('ref', ''),
            head=data.get('head', {}).get('ref', ''),
            files=[], total_additions=0, total_deletions=0,
            url=data.get('html_url', '')
        ))
    return prs

def post_comment(owner: str, repo: str, number: int, body: str):
    pass

def add_label(owner: str, repo: str, number: int, label: str):
    pass

def get_pr_state(owner: str, repo: str, number: int) -> PRState:
    return PRState(state="open", merged=False, mergeable=True, mergeable_state="clean", head_sha="abc", check_status="success", author_is_viewer=False)

def get_authenticated_user():
    return "viewer"

def approve_pr(owner: str, repo: str, number: int, body: str):
    pass

def merge_pr(owner: str, repo: str, number: int, merge_method="squash", expected_head_sha=""):
    pass

def post_comment(owner: str, repo: str, number: int, body: str):
    headers = _get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments"
    r = requests.post(url, headers=headers, json={"body": body})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Could not post comment: {r.status_code} {r.text}")

def close_pr(owner: str, repo: str, number: int):
    headers = _get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    r = requests.patch(url, headers=headers, json={"state": "closed"})
    if r.status_code != 200:
        raise RuntimeError(f"Could not close PR: {r.status_code} {r.text}")

def log_action(repo: str, number: int, action: str, head_sha: str, verdict: str, maintainer: str):
    pass

