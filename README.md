# thePRPoneglyph

An open-source tool that answers one question: **Is your Pull Request genuine?**

thePRPoneglyph reads the title and description of a GitHub PR, extracts every claim the author makes, and then deterministically checks each claim against the actual code diff. The final verdict comes from rules, never from model opinion.

It never closes, merges, or deletes anything unless you explicitly ask it to.

## How It Works

```
PR Title + Description
        |
        v
  Gemma 4 (via Gemini API)
  Extracts structured claims
        |
        v
  Deterministic Python checkers
  Compare each claim against the diff
        |
        v
  Verdict: "genuine" or "review_needed"
  with detailed reasoning and improvement suggestions
```

### Claim Types

| Type | What the checker does |
|---|---|
| `adds_tests` | Scans added lines for test function definitions (`def test_`, `it(`, `@Test`, etc.) |
| `docs_only` | Verifies all changed files have documentation extensions (`.md`, `.rst`, etc.) |
| `typo_fix` | Checks total lines changed (max 10) and computes Levenshtein distance on changed line pairs |
| `no_behavior_change` | Strips whitespace and comment lines, checks if any substantive code was changed |
| `references_symbol` | Searches every referenced symbol (function, class, variable) in all diff patches |
| `other` | Falls back to the LLM: sends the diff with the claim and asks for a structured SUPPORTED/CONTRADICTED/UNVERIFIABLE verdict |

## Features

- **Multiple LLM backends**: Evaluate with Gemini, Ollama, or both side by side
- **Evaluate All PRs**: One click to audit every open PR concurrently
- **Evaluate single PR**: Click into any PR for a detailed audit
- **Detailed reasoning**: See exactly which claims passed, failed, or were unverifiable and why
- **Improvement suggestions**: Concrete advice for fixing each flagged claim
- **Reject and Close**: Close PRs directly from the dashboard when claims are not supported (requires a rejection note)
- **Diff viewer**: Browse every changed file with syntax-highlighted diffs
- **Disk caching**: LLM responses are cached to `.cache/` so re-runs are instant
- **Lazy loading**: File diffs are fetched on demand, not upfront, so loading PRs is fast

## Prerequisites

- Python 3.10+
- A [GitHub Personal Access Token](https://github.com/settings/tokens) with the `repo` scope
- A [Gemini API Key](https://aistudio.google.com/apikey)
- (Optional) [Ollama](https://ollama.com) running locally with a Gemma model

## Quick Start

```bash
# Clone the repository
git clone https://github.com/mandipsapkota/thePRPoneglyph.git
cd thePRPoneglyph

# Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Configure your secrets
cp .env.example .env
# Edit .env and add your tokens
```

Create a `.env` file with the following:

```
GITHUB_TOKEN=ghp_your_token_here
GEMINI_API_KEY=your_gemini_api_key_here
GEMMA_MODEL=gemma-4-31b-it
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=gemma4:e4b
```

Run the dashboard:

```bash
streamlit run dashboard/app.py
```

## Usage

1. Enter a repository in `owner/repo` format (e.g. `psf/requests`)
2. Click **Load PRs** to fetch all open pull requests
3. Click **Evaluate All** to audit every PR at once, or click into a single PR and click **Audit this PR**
4. Review the verdict, reasoning, and improvement suggestions
5. If a PR shows "Review Needed", you can optionally reject and close it with a note

## Project Structure

```
thePRPoneglyph/
  dashboard/
    app.py              # Streamlit dashboard
  prauditor/
    backends.py         # Gemini and Ollama API clients with caching
    claims.py           # LLM-based claim extraction from PR text
    github.py           # GitHub API integration (PRs, diffs, comments, close)
    verdict.py          # Rules for computing final verdict from check results
    checkers/
      base.py           # Deterministic checkers (tests, docs, typo, symbols, etc.)
  tests/                # Test suite
  eval/                 # Evaluation harness
  scripts/              # Utility scripts
```

## Design Principles

1. **LLM extracts, code decides.** The language model only extracts structured claims. Deterministic Python code checks each claim against the diff. The final verdict comes from rules, not from model opinion.
2. **Never say "fake".** The tool says "claim not supported by the diff." It never accuses the author.
3. **Read-only by default.** The tool only prints reports. It never closes, merges, or deletes anything unless you explicitly click a button.
4. **Secrets stay safe.** All credentials come from environment variables or `.env`. Nothing is hardcoded or committed.

## License

MIT
