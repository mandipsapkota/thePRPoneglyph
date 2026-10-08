import os
import sys
import importlib
import concurrent.futures
import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

# Force reload prauditor modules on each run
for module_name in list(sys.modules.keys()):
    if module_name.startswith("prauditor"):
        try:
            importlib.reload(sys.modules[module_name])
        except Exception:
            pass

from prauditor.github import list_open_prs, ensure_files_loaded, close_pr
from prauditor.backends import get_backend
from prauditor.claims import extract_claims
from prauditor.checkers.base import verify_claims
from prauditor.verdict import evaluate_verdict

st.set_page_config(layout="wide", page_title="thePRPoneglyph", page_icon="🏴‍☠️")

# Session state defaults
for key in ["prs", "selected_pr", "audit_results"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "prs" else (None if key == "selected_pr" else {})

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏴‍☠️ thePRPoneglyph")
    st.caption("Is your PR genuine?")
    st.divider()

    token = os.getenv("GITHUB_TOKEN")
    if token:
        st.success("GitHub Token connected")
    else:
        st.error("GITHUB_TOKEN missing in .env")

    repo_input = st.text_input("Repository", placeholder="owner/repo  e.g. psf/requests")
    backends_selected = st.multiselect(
        "LLM Backends", ["gemini", "ollama"], default=["gemini"],
        help="Select one or more backends to evaluate PRs with"
    )

    col_load, col_all = st.columns(2)
    with col_load:
        load_clicked = st.button("Load PRs", use_container_width=True)
    with col_all:
        eval_all_clicked = st.button("Evaluate All", use_container_width=True)

    if load_clicked:
        if not repo_input or "/" not in repo_input:
            st.error("Enter a valid owner/repo")
        else:
            owner, repo = repo_input.strip().split("/", 1)
            with st.spinner("Fetching open PRs..."):
                try:
                    prs = list_open_prs(owner, repo)
                    st.session_state.prs = prs
                    st.session_state.audit_results = {}
                    if not prs:
                        st.info("No open PRs found.")
                    else:
                        st.success(f"Loaded {len(prs)} open PR(s)")
                except Exception as e:
                    st.error(f"Error: {e}")

    if eval_all_clicked:
        if not st.session_state.prs:
            st.warning("Load PRs first.")
        elif not backends_selected:
            st.warning("Select at least one backend.")
        else:
            progress = st.progress(0, text="Evaluating...")
            tasks = [(pr, b) for pr in st.session_state.prs for b in backends_selected]
            total = len(tasks)
            done = 0

            def evaluate_single(pr, b_name):
                pr = ensure_files_loaded(pr)
                backend = get_backend(b_name)
                extraction = extract_claims(backend, pr.title, pr.body)
                if extraction.ok and extraction.claims:
                    results = verify_claims(backend, extraction.claims, pr)
                    verdict, reasons, improvements = evaluate_verdict(results)
                else:
                    verdict, reasons, improvements = "review_needed", [extraction.error or "No claims extracted."], []
                return pr, b_name, verdict, reasons, improvements, extraction.claims if extraction.ok else []

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_task = {executor.submit(evaluate_single, pr, b): (pr, b) for pr, b in tasks}
                for future in concurrent.futures.as_completed(future_to_task):
                    pr, b_name, verdict, reasons, improvements, claims = future.result()
                    st.session_state.audit_results[f"{pr.number}_{b_name}"] = {
                        "verdict": verdict, "reasons": reasons,
                        "improvements": improvements, "claims": claims
                    }
                    done += 1
                    progress.progress(done / total, text=f"Evaluated {done}/{total}")

            progress.empty()
            st.success("All PRs evaluated!")

# ── MAIN AREA ────────────────────────────────────────────────────────────────
col_list, col_detail = st.columns([1, 2], gap="large")

# LEFT: PR list
with col_list:
    st.subheader("Open Pull Requests")
    if not st.session_state.prs:
        st.info("Use the sidebar to load a repository.")
    else:
        for pr in st.session_state.prs:
            with st.container(border=True):
                st.markdown(f"**#{pr.number}** {pr.title}")
                st.caption(f"{pr.author}  |  `{pr.head}`")

                for b_name in backends_selected:
                    key = f"{pr.number}_{b_name}"
                    if key in st.session_state.audit_results:
                        v = st.session_state.audit_results[key]["verdict"]
                        badge = "Genuine" if v == "genuine" else "Review needed"
                        color = "green" if v == "genuine" else "orange"
                        st.markdown(f"`{b_name.upper()}` :{color}[{badge}]")

                if st.button(f"View details", key=f"view_{pr.number}", use_container_width=True):
                    st.session_state.selected_pr = pr

# RIGHT: Detail view
with col_detail:
    selected = st.session_state.selected_pr

    if selected is None:
        st.info("Select a PR from the list to see its full audit report.")
    else:
        close_col, _ = st.columns([1, 5])
        with close_col:
            if st.button("Close", use_container_width=True):
                st.session_state.selected_pr = None
                st.rerun()

        # Lazy-load files for this PR
        selected = ensure_files_loaded(selected)

        st.markdown(f"## [#{selected.number}] {selected.title}")
        st.caption(f"Author: **{selected.author}** | `{selected.base}` <- `{selected.head}` | [View on GitHub]({selected.url})")
        st.caption(f"+{selected.total_additions} additions, -{selected.total_deletions} deletions across {len(selected.files)} file(s)")
        st.divider()

        with st.expander("What the author wrote", expanded=True):
            st.markdown(selected.body if selected.body.strip() else "_No description provided._")

        if selected.files:
            with st.expander(f"Changed files ({len(selected.files)})"):
                for f in selected.files:
                    st.markdown(f"- `{f.filename}` **{f.status}** `+{f.additions}` `-{f.deletions}`")
                    if f.patch:
                        with st.expander(f"View diff: {f.filename}", expanded=False):
                            st.code(f.patch, language="diff")

        st.divider()

        # Audit controls
        st.subheader("Audit Verdict")
        if not backends_selected:
            st.warning("Select a backend in the sidebar first.")
        elif st.button("Audit this PR", type="primary", use_container_width=True):
            with st.spinner("Running audit pipeline..."):
                for b_name in backends_selected:
                    backend = get_backend(b_name)
                    extraction = extract_claims(backend, selected.title, selected.body)
                    if extraction.ok and extraction.claims:
                        results = verify_claims(backend, extraction.claims, selected)
                        verdict, reasons, improvements = evaluate_verdict(results)
                    else:
                        verdict = "review_needed"
                        reasons = [extraction.error or "No claims found in description."]
                        improvements = ["Add clear, specific claims to the PR description."]
                    st.session_state.audit_results[f"{selected.number}_{b_name}"] = {
                        "verdict": verdict, "reasons": reasons,
                        "improvements": improvements,
                        "claims": extraction.claims if extraction.ok else []
                    }

        # Display results per backend
        for b_name in backends_selected:
            key = f"{selected.number}_{b_name}"
            if key not in st.session_state.audit_results:
                continue

            res = st.session_state.audit_results[key]
            verdict = res["verdict"]

            st.markdown(f"### `{b_name.upper()}` Results")

            if verdict == "genuine":
                st.success("Verdict: **Genuine**. All claims are supported by the diff.")
            else:
                st.warning("Verdict: **Review Needed**. One or more claims could not be verified.")

            with st.expander("Detailed Reasoning", expanded=True):
                for r in res["reasons"]:
                    st.write(f"- {r}")

            if res.get("improvements"):
                with st.expander("Possible Improvements"):
                    for imp in res["improvements"]:
                        st.info(imp)

            if res.get("claims"):
                with st.expander("Raw extracted claims (LLM output)"):
                    st.json([c.model_dump() for c in res["claims"]])

            if verdict == "review_needed":
                st.divider()
                st.markdown("#### Actions")
                note = st.text_area(
                    "Rejection note (required)",
                    placeholder="Thank you for your contribution. After review, the claims in this PR could not be verified against the diff. Please see the audit report for details.",
                    key=f"note_{key}"
                )
                if st.button(f"Reject and Close PR #{selected.number}", key=f"close_{key}", type="primary"):
                    if not note.strip():
                        st.error("Please write a rejection note before closing.")
                    else:
                        try:
                            close_pr(selected.owner, selected.repo, selected.number)
                            st.success(f"PR #{selected.number} has been closed.")
                        except Exception as e:
                            st.error(f"Could not close PR: {e}")
