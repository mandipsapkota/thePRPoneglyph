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
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

def parse_pr_url(url: str):
    parts = url.split('/')
    return parts[3], parts[4], int(parts[6])

def parse_pr_ref(ref: str):
    owner_repo, number = ref.split('#')
    owner, repo = owner_repo.split('/')
    return owner, repo, int(number)

def _fetch_files(owner: str, repo: str, number: int) -> tuple[List[ChangedFile], int, int]:
    """Fetch changed files with diffs, handling pagination."""
    headers = _get_headers()
    files = []
    page = 1
    total_add = 0
    total_del = 0
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files?per_page=100&page={page}"
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        for f in batch:
            files.append(ChangedFile(
                filename=f['filename'],
                status=f['status'],
                additions=f['additions'],
                deletions=f['deletions'],
                patch=f.get('patch'),  # missing for binary/very large files
            ))
            total_add += f['additions']
            total_del += f['deletions']
        if len(batch) < 100:
            break
        page += 1
    return files, total_add, total_del

def fetch_pr(owner: str, repo: str, number: int) -> PRData:
    headers = _get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    r = requests.get(url, headers=headers)
    if r.status_code == 401:
        raise RuntimeError("GitHub returned 401 Unauthorized. Check your GITHUB_TOKEN.")
    elif r.status_code == 403:
        raise RuntimeError("GitHub returned 403 Forbidden. Token may lack repo scope or hit rate limit.")
    elif r.status_code == 404:
        raise RuntimeError(f"PR #{number} not found in {owner}/{repo}.")
    elif r.status_code != 200:
        raise RuntimeError(f"GitHub API error: {r.status_code}")
    data = r.json()

    files, total_add, total_del = _fetch_files(owner, repo, number)
    return PRData(
        owner=owner, repo=repo, number=number,
        title=data.get('title', ''),
        body=data.get('body', '') or '',
        author=data.get('user', {}).get('login', ''),
        base=data.get('base', {}).get('ref', ''),
        head=data.get('head', {}).get('ref', ''),
        files=files,
        total_additions=total_add,
        total_deletions=total_del,
        url=data.get('html_url', '')
    )

def list_open_prs(owner: str, repo: str, limit: int = 30) -> List[PRData]:
    """List open PRs. File diffs are loaded lazily via ensure_files_loaded()."""
    headers = _get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&per_page={limit}"
    r = requests.get(url, headers=headers)
    if r.status_code == 401:
        raise RuntimeError("GitHub returned 401 Unauthorized. Check your GITHUB_TOKEN.")
    elif r.status_code == 403:
        raise RuntimeError("GitHub returned 403 Forbidden. Token may need 'repo' scope, or you need SSO authorization for this org.")
    elif r.status_code == 404:
        raise RuntimeError(f"Repository '{owner}/{repo}' not found, or the token cannot access it.")
    elif r.status_code != 200:
        raise RuntimeError(f"GitHub API error {r.status_code}: {r.text}")

    prs = []
    for data in r.json():
        prs.append(PRData(
            owner=owner, repo=repo, number=data['number'],
            title=data.get('title', ''),
            body=data.get('body', '') or '',
            author=data.get('user', {}).get('login', ''),
            base=data.get('base', {}).get('ref', ''),
            head=data.get('head', {}).get('ref', ''),
            files=[],  # loaded lazily
            total_additions=data.get('additions', 0),
            total_deletions=data.get('deletions', 0),
            url=data.get('html_url', '')
        ))
    return prs

def ensure_files_loaded(pr: PRData) -> PRData:
    """Fetch file diffs for a PR if not already loaded. Returns updated PRData."""
    if pr.files:
        return pr  # already loaded
    files, total_add, total_del = _fetch_files(pr.owner, pr.repo, pr.number)
    pr.files = files
    pr.total_additions = total_add
    pr.total_deletions = total_del
    return pr

def add_label(owner: str, repo: str, number: int, label: str):
    headers = _get_headers()
    # Ensure label exists first
    requests.post(
        f"https://api.github.com/repos/{owner}/{repo}/labels",
        headers=headers, json={"name": label, "color": "ededed"}
    )
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/labels"
    r = requests.post(url, headers=headers, json={"labels": [label]})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Could not add label: {r.status_code} {r.text}")

def get_pr_state(owner: str, repo: str, number: int) -> PRState:
    headers = _get_headers()
    r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}", headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"Could not get PR state: {r.status_code}")
    d = r.json()
    viewer = get_authenticated_user()
    return PRState(
        state=d.get('state', 'open'),
        merged=d.get('merged', False),
        mergeable=d.get('mergeable'),
        mergeable_state=d.get('mergeable_state', 'unknown'),
        head_sha=d.get('head', {}).get('sha', ''),
        check_status='none',
        author_is_viewer=(d.get('user', {}).get('login', '') == viewer)
    )

def get_authenticated_user() -> str:
    headers = _get_headers()
    r = requests.get("https://api.github.com/user", headers=headers)
    if r.status_code == 200:
        return r.json().get('login', '')
    return ''

def approve_pr(owner: str, repo: str, number: int, body: str = ""):
    headers = _get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/reviews"
    r = requests.post(url, headers=headers, json={"event": "APPROVE", "body": body})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Could not approve PR: {r.status_code} {r.text}")

def merge_pr(owner: str, repo: str, number: int, merge_method: str = "squash", expected_head_sha: str = ""):
    headers = _get_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/merge"
    payload = {"merge_method": merge_method}
    if expected_head_sha:
        payload["sha"] = expected_head_sha
    r = requests.put(url, headers=headers, json=payload)
    if r.status_code == 405:
        raise RuntimeError("PR is not mergeable.")
    elif r.status_code == 409:
        raise RuntimeError("SHA mismatch — new commits were pushed since the audit. Please re-audit.")
    elif r.status_code not in (200, 201):
        raise RuntimeError(f"Could not merge PR: {r.status_code} {r.text}")

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
    os.makedirs(".cache", exist_ok=True)
    entry = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "repo": repo, "number": number, "action": action,
        "head_sha": head_sha, "verdict": verdict, "maintainer": maintainer
    }
    with open(".cache/audit_log.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
