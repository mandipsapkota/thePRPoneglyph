from prauditor.checkers.base import Status

IMPROVEMENTS = {
    "adds_tests": "Consider adding tests that cover edge cases and negative scenarios. Use descriptive test names that explain what is being tested.",
    "docs_only": "Ensure documentation is accurate, up-to-date, and includes examples where helpful.",
    "typo_fix": "Double-check surrounding text for any additional typos. Consistent grammar and spelling improves readability.",
    "no_behavior_change": "Add a comment in the code or PR description explaining exactly what was refactored and why, so reviewers can confirm no behavior changed.",
    "references_symbol": "Make sure every referenced symbol (function, class, variable) actually exists and is spelled correctly in the diff.",
    "other": "Provide more specific and verifiable claims in the PR description to help reviewers quickly understand the intent."
}

def evaluate_verdict(results):
    if not results:
        return "review_needed", ["No claims could be extracted from the PR description."], []
    
    reasons = []
    improvements = []
    has_supported = False
    
    for r in results:
        claim_type = r.claim.get("type", "other")
        if r.status == Status.CONTRADICTED:
            reasons.append(f"Claim not supported by the diff: \"{r.claim['text']}\" — {r.evidence}")
            improvements.append(IMPROVEMENTS.get(claim_type, IMPROVEMENTS["other"]))
        elif r.status == Status.UNVERIFIABLE:
            reasons.append(f"Could not verify: \"{r.claim['text']}\" — {r.evidence}")
            improvements.append(IMPROVEMENTS.get(claim_type, IMPROVEMENTS["other"]))
        elif r.status == Status.SUPPORTED:
            has_supported = True
            reasons.append(f"Supported: \"{r.claim['text']}\" — {r.evidence}")

    if any(r.status == Status.CONTRADICTED for r in results):
        return "review_needed", reasons, list(dict.fromkeys(improvements))  # deduplicate
        
    if has_supported and all(r.status == Status.SUPPORTED for r in results):
        return "genuine", reasons, []
        
    return "review_needed", reasons, list(dict.fromkeys(improvements))
