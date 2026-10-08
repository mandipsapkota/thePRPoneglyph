import re
from enum import Enum
from typing import List
from pydantic import BaseModel

class Status(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIABLE = "UNVERIFIABLE"

class CheckResult(BaseModel):
    claim: dict
    status: Status
    evidence: str

# ── Helpers ──────────────────────────────────────────────────────────────────

DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}
DOC_NAMES = {"readme", "license", "changelog", "contributing", "authors", "notice"}
TEST_PATTERNS = [
    r"\bdef test_", r"\bit\(", r"\btest\(", r"\bdescribe\(", r"@Test\b", r"\bfunc Test",
    r"\bspec\b", r"\.test\.", r"\.spec\."
]
TEST_FILE_PATTERNS = [
    "test/", "tests/", "__tests__/", "_test.", ".test.", ".spec.", "test_.py",
]
COMMENT_RE = re.compile(
    r"^\s*(#|//|/\*|\*|<!--|-->|--)", re.MULTILINE
)

def _is_test_file(filename: str) -> bool:
    f = filename.lower()
    return any(p in f for p in TEST_FILE_PATTERNS)

def _is_doc_file(filename: str) -> bool:
    f = filename.lower()
    ext = "." + f.rsplit(".", 1)[-1] if "." in f else ""
    basename = f.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return ext in DOC_EXTENSIONS or basename in DOC_NAMES or "docs/" in f

def _added_lines(patch: str) -> List[str]:
    return [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]

def _removed_lines(patch: str) -> List[str]:
    return [l[1:] for l in patch.splitlines() if l.startswith("-") and not l.startswith("---")]

def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    row = list(range(len(b) + 1))
    for c in a:
        new_row = [row[0] + 1]
        for j, d in enumerate(b):
            new_row.append(min(new_row[-1] + 1, row[j + 1] + 1, row[j] + (c != d)))
        row = new_row
    return row[-1]

def _is_substantive(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if COMMENT_RE.match(stripped):
        return False
    return True

# ── Checkers ─────────────────────────────────────────────────────────────────

def check_adds_tests(claim, pr) -> CheckResult:
    test_files = [f for f in pr.files if _is_test_file(f.filename)]
    if not test_files:
        return CheckResult(
            claim=claim.model_dump(), status=Status.CONTRADICTED,
            evidence=f"No test files were modified. Changed files: {[f.filename for f in pr.files] or ['(none)']}"
        )
    # Check that added lines contain a real test definition
    for f in test_files:
        if f.patch:
            for line in _added_lines(f.patch):
                if any(re.search(p, line) for p in TEST_PATTERNS):
                    return CheckResult(
                        claim=claim.model_dump(), status=Status.SUPPORTED,
                        evidence=f"Test definition found in added lines of `{f.filename}`."
                    )
    return CheckResult(
        claim=claim.model_dump(), status=Status.UNVERIFIABLE,
        evidence=f"Test file(s) modified ({[f.filename for f in test_files]}) but no new test definitions detected in added lines."
    )

def check_docs_only(claim, pr) -> CheckResult:
    if not pr.files:
        return CheckResult(claim=claim.model_dump(), status=Status.UNVERIFIABLE, evidence="No file data available.")
    non_doc = [f.filename for f in pr.files if not _is_doc_file(f.filename)]
    if non_doc:
        return CheckResult(
            claim=claim.model_dump(), status=Status.CONTRADICTED,
            evidence=f"Non-documentation file(s) were changed: {non_doc}"
        )
    return CheckResult(
        claim=claim.model_dump(), status=Status.SUPPORTED,
        evidence=f"All {len(pr.files)} changed file(s) are documentation."
    )

def check_typo_fix(claim, pr) -> CheckResult:
    total = pr.total_additions + pr.total_deletions
    if total == 0:
        return CheckResult(claim=claim.model_dump(), status=Status.UNVERIFIABLE, evidence="No line change data available.")
    if total > 10:
        return CheckResult(
            claim=claim.model_dump(), status=Status.CONTRADICTED,
            evidence=f"{total} lines changed (threshold is 10). This is larger than a typical typo fix."
        )
    # Check that changed line pairs have small edit distance
    suspicious = []
    for f in pr.files:
        if not f.patch:
            continue
        added = _added_lines(f.patch)
        removed = _removed_lines(f.patch)
        for a, b in zip(added, removed):
            a_s, b_s = a.strip(), b.strip()
            if a_s and b_s:
                dist = _levenshtein(a_s, b_s)
                threshold = max(3, int(len(b_s) * 0.2))
                if dist > threshold:
                    suspicious.append(f"`{b_s[:60]}` → `{a_s[:60]}` (edit distance {dist})")
    if suspicious:
        return CheckResult(
            claim=claim.model_dump(), status=Status.CONTRADICTED,
            evidence=f"Some line changes exceed typo-fix edit distance: {suspicious[:2]}"
        )
    return CheckResult(
        claim=claim.model_dump(), status=Status.SUPPORTED,
        evidence=f"Only {total} line(s) changed with small edit distances — consistent with a typo fix."
    )

def check_no_behavior_change(claim, pr) -> CheckResult:
    substantive = []
    unverifiable_files = []
    for f in pr.files:
        if not f.patch:
            unverifiable_files.append(f.filename)
            continue
        # Non-code files (docs) are excluded
        if _is_doc_file(f.filename):
            continue
        for line in _added_lines(f.patch) + _removed_lines(f.patch):
            if _is_substantive(line):
                substantive.append(f"`{line.strip()[:80]}`")
                if len(substantive) >= 3:
                    break
        if len(substantive) >= 3:
            break
    if substantive:
        return CheckResult(
            claim=claim.model_dump(), status=Status.CONTRADICTED,
            evidence=f"Substantive code lines were changed: {substantive}"
        )
    if unverifiable_files:
        return CheckResult(
            claim=claim.model_dump(), status=Status.UNVERIFIABLE,
            evidence=f"Patch unavailable for: {unverifiable_files} (binary or large files)."
        )
    return CheckResult(
        claim=claim.model_dump(), status=Status.SUPPORTED,
        evidence="Only whitespace, comments, or documentation changes detected."
    )

def check_references_symbol(claim, pr) -> CheckResult:
    symbols = claim.symbols
    if not symbols:
        return CheckResult(claim=claim.model_dump(), status=Status.UNVERIFIABLE, evidence="No symbols listed in claim.")
    missing = []
    for sym in symbols:
        found = any(
            sym in (f.filename or "") or sym in (f.patch or "")
            for f in pr.files
        )
        if not found:
            missing.append(sym)
    if missing:
        return CheckResult(
            claim=claim.model_dump(), status=Status.CONTRADICTED,
            evidence=f"Symbol(s) not found in any changed file or diff: {missing}"
        )
    return CheckResult(
        claim=claim.model_dump(), status=Status.SUPPORTED,
        evidence=f"All referenced symbol(s) {symbols} found in the diff."
    )

def check_other(claim, pr) -> CheckResult:
    return CheckResult(
        claim=claim.model_dump(), status=Status.UNVERIFIABLE,
        evidence="This claim type cannot be verified deterministically."
    )

# ── Registry ─────────────────────────────────────────────────────────────────

_DISPATCH = {
    "adds_tests": check_adds_tests,
    "docs_only": check_docs_only,
    "typo_fix": check_typo_fix,
    "no_behavior_change": check_no_behavior_change,
    "references_symbol": check_references_symbol,
    "other": check_other,
}

def verify_claims(claims, pr) -> List[CheckResult]:
    results = []
    for claim in claims:
        checker = _DISPATCH.get(claim.type.value, check_other)
        results.append(checker(claim, pr))
    return results
