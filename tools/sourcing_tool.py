import os
from langchain_core.tools import tool
from typing import List, Dict
from state import Candidate
from tools.google_form_tool import fetch_google_form_responses

@tool
def candidate_sourcing_tool(job_id: str) -> List[Candidate]:
    """
    Fetches real candidate applications from Google Forms.
    
    Workflow:
    1. First checks if candidates already loaded in workflow state
    2. If not, fetches from Google Form responses (Google Sheets)
    3. Returns list of candidates for screening
    """
    print(f"--- SOURCING CANDIDATES FOR JOB ID: {job_id} ---")
    
    # STEP 1: Check if candidates already in workflow state
    from graph import build_graph
    graph_app = build_graph()
    config = {"configurable": {"thread_id": job_id}}
    
    try:
        state = graph_app.get_state(config)
        existing_candidates = state.values.get('candidates', [])
        
        if existing_candidates:
            print(f"✅ Found {len(existing_candidates)} candidates in workflow state")
            return existing_candidates
    except Exception as e:
        print(f"⚠️  Could not check workflow state: {e}")
    
    # STEP 2: Fetch from Google Form
    sheet_id = os.getenv("GOOGLE_FORM_SHEET_ID")
    
    if not sheet_id:
        print("❌ ERROR: GOOGLE_FORM_SHEET_ID not set in .env file")
        return []
    
    print(f"📊 Fetching applications from Google Form...")
    candidates = fetch_google_form_responses.invoke(sheet_id)
    
    if not candidates:
        print("⚠️  No applications found in Google Form")
        print("💡 Make sure candidates have filled the form")
        return []
    
    print(f"✅ Loaded {len(candidates)} real applicants from Google Form")
    return candidates