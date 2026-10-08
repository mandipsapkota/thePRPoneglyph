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

def check_adds_tests(claim, pr):
    # Simplified logic
    for f in pr.files:
        if "test" in f.filename.lower() and f.additions > 0:
            return CheckResult(claim=claim.model_dump(), status=Status.SUPPORTED, evidence=f"Found added tests in {f.filename}")
    return CheckResult(claim=claim.model_dump(), status=Status.CONTRADICTED, evidence="No test files were modified or no lines added.")

def check_docs_only(claim, pr):
    for f in pr.files:
        if not (f.filename.endswith(".md") or "docs" in f.filename.lower()):
            return CheckResult(claim=claim.model_dump(), status=Status.CONTRADICTED, evidence=f"Found non-doc file: {f.filename}")
    return CheckResult(claim=claim.model_dump(), status=Status.SUPPORTED, evidence="Only docs files were modified.")

def check_typo_fix(claim, pr):
    if pr.total_additions + pr.total_deletions > 10:
        return CheckResult(claim=claim.model_dump(), status=Status.CONTRADICTED, evidence=f"Too many lines changed ({pr.total_additions + pr.total_deletions} > 10).")
    return CheckResult(claim=claim.model_dump(), status=Status.UNVERIFIABLE, evidence="Small change, assuming typo fix.")

def check_no_behavior_change(claim, pr):
    return CheckResult(claim=claim.model_dump(), status=Status.UNVERIFIABLE, evidence="Cannot deterministically verify behavior change yet.")

def check_references_symbol(claim, pr):
    return CheckResult(claim=claim.model_dump(), status=Status.UNVERIFIABLE, evidence="Symbol check not fully implemented.")

def check_other(claim, pr):
    return CheckResult(claim=claim.model_dump(), status=Status.UNVERIFIABLE, evidence="Unverifiable custom claim.")

def verify_claims(claims, pr):
    results = []
    dispatch = {
        "adds_tests": check_adds_tests,
        "docs_only": check_docs_only,
        "typo_fix": check_typo_fix,
        "no_behavior_change": check_no_behavior_change,
        "references_symbol": check_references_symbol,
        "other": check_other,
    }
    for claim in claims:
        checker = dispatch.get(claim.type.value, check_other)
        results.append(checker(claim, pr))
    return results
