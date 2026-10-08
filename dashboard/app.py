import os
import streamlit as st
from dotenv import load_dotenv

# Load env variables (Token and Keys)
load_dotenv(override=True)

import sys
import importlib

# Force reload modules so we bypass Streamlit/Python caching
for module_name in list(sys.modules.keys()):
    if module_name.startswith("prauditor"):
        importlib.reload(sys.modules[module_name])

from prauditor.github import fetch_pr, list_open_prs, get_pr_state, approve_pr, merge_pr, close_pr, get_authenticated_user, log_action
from prauditor.backends import get_backend
from prauditor.claims import extract_claims
from prauditor.checkers.base import Status, verify_claims
from prauditor.verdict import evaluate_verdict

st.set_page_config(layout="wide", page_title="prauditor")

# Default session state initialization
if "prs" not in st.session_state:
    st.session_state.prs = []
if "selected_pr" not in st.session_state:
    st.session_state.selected_pr = None
if "audit_results" not in st.session_state:
    st.session_state.audit_results = {}

# --- SIDEBAR ---
with st.sidebar:
    st.title("prauditor Setup")
    
    token = os.getenv("GITHUB_TOKEN")
    if token:
        st.success("GitHub Token: Valid (Hidden)")
    else:
        st.error("GitHub Token: Missing! (Please set GITHUB_TOKEN in .env)")
        
    repo_input = st.text_input("Repository", placeholder="e.g. psf/requests")
    backend_select = st.multiselect("LLM Backends", ["gemini", "ollama"], default=["gemini"])
    
    if st.button("Load open PRs"):
        if not repo_input or "/" not in repo_input:
            st.error("Please enter a valid owner/repo format.")
        else:
            owner, repo = repo_input.split("/")
            with st.spinner("Fetching open PRs..."):
                try:
                    prs = list_open_prs(owner, repo)
                    if not prs:
                        st.info("No open PRs found.")
                    st.session_state.prs = prs
                except Exception as e:
                    st.error(f"Error fetching PRs: {str(e)}")

    if st.button("Evaluate All PRs"):
        if not st.session_state.prs:
            st.warning("Please load PRs first.")
        elif not backend_select:
            st.warning("Please select at least one LLM Backend.")
        else:
            with st.spinner("Evaluating all PRs..."):
                for pr in st.session_state.prs:
                    for b_name in backend_select:
                        backend = get_backend(b_name)
                        extraction = extract_claims(backend, pr.title, pr.body)
                        if extraction.ok:
                            results = verify_claims(extraction.claims, pr)
                            verdict, reasons = evaluate_verdict(results)
                            st.session_state.audit_results[f"{pr.number}_{b_name}"] = {
                                "verdict": verdict,
                                "reasons": reasons,
                                "results": results
                            }

# --- MAIN LAYOUT ---
col1, col2 = st.columns([1, 2])

# Left Column: PR List
with col1:
    st.subheader("Open Pull Requests")
    
    if not st.session_state.prs:
        st.write("No PRs loaded yet. Use the sidebar to load a repository.")
    else:
        for pr in st.session_state.prs:
            with st.container(border=True):
                st.markdown(f"**#{pr.number}**: {pr.title}")
                st.caption(f"Author: {pr.author} | Branch: {pr.head}")
                
                # Show verdict summary if evaluated
                for b_name in ["gemini", "ollama"]:
                    key = f"{pr.number}_{b_name}"
                    if key in st.session_state.audit_results:
                        v = st.session_state.audit_results[key]["verdict"]
                        color = "green" if v == "genuine description" else "red" if v == "fake description" else "orange"
                        st.markdown(f"**{b_name.upper()}**: :{color}[{v}]")
                
                if st.button(f"View PR #{pr.number}", key=f"btn_view_{pr.number}"):
                    st.session_state.selected_pr = pr

# Right Column: Detail View
with col2:
    st.subheader("PR Detail View")
    
    selected = st.session_state.selected_pr
    if selected is None:
        st.info("Select a PR from the left to view details.")
    else:
        st.markdown(f"### [#{selected.number}] {selected.title}")
        st.caption(f"Author: {selected.author} | [View on GitHub]({selected.url})")
        
        st.markdown("#### What the author wrote")
        st.info(selected.body if selected.body else "_No description provided._")
        
        st.markdown("#### Audit Verdict")
        
        if st.button("Audit this PR", type="primary"):
            if not backend_select:
                st.warning("Please select at least one LLM Backend.")
            else:
                with st.spinner("Running Audit Pipeline..."):
                    for b_name in backend_select:
                        st.write(f"**Running with {b_name}...**")
                        backend = get_backend(b_name)
                        
                        extraction = extract_claims(backend, selected.title, selected.body)
                        if not extraction.ok:
                            st.error(f"Failed to extract claims: {extraction.error}")
                        else:
                            results = verify_claims(extraction.claims, selected)
                            verdict, reasons = evaluate_verdict(results)
                            
                            st.session_state.audit_results[f"{selected.number}_{b_name}"] = {
                                "verdict": verdict,
                                "reasons": reasons,
                                "results": results
                            }
        
        # Display results and Actions
        for b_name in ["gemini", "ollama"]:
            key = f"{selected.number}_{b_name}"
            if key in st.session_state.audit_results:
                res = st.session_state.audit_results[key]
                st.markdown(f"### Results from {b_name.upper()}")
                
                if res["verdict"] == "genuine description":
                    st.success("Verdict: Genuine Description")
                elif res["verdict"] == "fake description":
                    st.error("Verdict: Fake Description")
                    
                    st.markdown("#### Actions")
                    if st.button(f"Reject & Close PR (Delete)", key=f"del_{key}", type="primary"):
                        try:
                            # Note: GitHub doesn't allow deleting PRs, so we close it.
                            close_pr(selected.owner, selected.repo, selected.number)
                            st.success(f"Successfully closed PR #{selected.number}")
                        except Exception as e:
                            st.error(f"Failed to close PR: {str(e)}")
                else:
                    st.warning("Verdict: Needs human review")
                    
                with st.expander("Reasons", expanded=True):
                    for r in res["reasons"]:
                        st.write(f"- {r}")
