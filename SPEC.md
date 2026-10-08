# SPEC
## Architecture
1. Claim Extraction: Uses Gemma 4 (via Gemini API or Ollama) to extract claims from PR description.
2. Verification: Deterministic Python code checks the code diff to verify the extracted claims.
3. Verdict: Rules determine if the PR is genuine, needs review, or claims are unsupported.
4. Dashboard: Allows a human maintainer to safely merge/close PRs based on the advisory verdict.
