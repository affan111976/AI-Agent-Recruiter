import streamlit as st
import requests
import uuid
import json
import time
from datetime import datetime
from graph import build_graph
from db import save_state, load_state
from config import API_BASE_URL  # ✅ Import API URL

# Page configuration
st.set_page_config(
    page_title="Advanced HR Agent",
    page_icon="👔",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration - Now imported from config.py
# API_BASE_URL comes from config and uses the machine's local IP

# Initialize session state
if 'workflow_started' not in st.session_state:
    st.session_state.workflow_started = False
if 'job_id' not in st.session_state:
    st.session_state.job_id = None
if 'workflow_stage' not in st.session_state:
    st.session_state.workflow_stage = "Not Started"
if 'graph_app' not in st.session_state:
    st.session_state.graph_app = build_graph()
if 'workflow_complete' not in st.session_state:
    st.session_state.workflow_complete = False

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stage-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #f0f2f6;
        margin: 1rem 0;
    }
    .success-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
    }
    .info-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
    .candidate-card {
        padding: 1rem;
        border-radius: 8px;
        background-color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">👔 Advanced HR Agent System</div>', unsafe_allow_html=True)

# ✅ Show API accessibility info
with st.expander("ℹ️ API Connection Info", expanded=False):
    st.info(f"**API Base URL:** `{API_BASE_URL}`")
    st.markdown("""
    - 💻 **On this computer:** Use `http://localhost:8000` or the URL above
    - 📱 **On mobile (same WiFi):** Use the URL above to access offer links
    - 🔗 **Email links will use:** The URL above (so they work on any device)
    """)

# Sidebar - Workflow Status
with st.sidebar:
    st.header("📊 Workflow Status")
    
    if st.session_state.job_id:
        st.success(f"**Job ID:** `{st.session_state.job_id[:8]}...`")
        st.info(f"**Current Stage:** {st.session_state.workflow_stage}")
        
        # Load and display current state
        if st.button("🔄 Refresh Status"):
            state = load_state(st.session_state.job_id)
            if state:
                st.session_state.workflow_stage = "Active"
        
        # Progress tracking
        stages = [
            "Job Description",
            "Posting",
            "Sourcing",
            "Screening",
            "Interviews",
            "Decision",
            "Offers",
            "Onboarding"
        ]
        
        st.markdown("### 📋 Pipeline Stages")
        for stage in stages:
            st.text(f"{'✅' if stage in st.session_state.workflow_stage else '⏸️'} {stage}")
    else:
        st.warning("No active workflow")
    
    st.markdown("---")
    st.markdown("### 🛠️ Actions")
    if st.button("🗑️ Clear Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Main content area with tabs
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Start Workflow", "📨 Offer Responses", "📊 Dashboard", "🔍 Debug"])

# Tab 1: Start Workflow
with tab1:
    st.header("Start New Hiring Process")
    
    if not st.session_state.workflow_started:
        with st.form("start_workflow_form"):
            st.markdown("### What position are you hiring for?")
            job_request = st.text_area(
                "Job Requirements",
                placeholder="Example: We need to hire a senior Python developer with experience in building web applications...",
                height=150
            )
            
            submitted = st.form_submit_button("🚀 Start Hiring Process", use_container_width=True)
            
            if submitted and job_request:
                with st.spinner("Initializing workflow..."):
                    # Create unique job ID
                    job_id = str(uuid.uuid4())
                    st.session_state.job_id = job_id
                    
                    # Prepare initial state
                    initial_state = {
                        "initial_request": job_request,
                        "job_id": job_id,
                        "offers_sent": [],
                        "offer_responses": []
                    }
                    
                    config = {
                        "configurable": {"thread_id": job_id},
                        "recursion_limit": 50
                    }
                    
                    # Save initial state
                    save_state(job_id, initial_state)
                    
                    # Start workflow
                    try:
                        st.session_state.workflow_stage = "Running..."
                        
                        # Create a placeholder for real-time updates
                        status_placeholder = st.empty()
                        logs_placeholder = st.empty()
                        
                        # Run the workflow
                        for event in st.session_state.graph_app.stream(initial_state, config):
                            for node_name, node_output in event.items():
                                st.session_state.workflow_stage = f"Executing: {node_name}"
                                status_placeholder.info(f"🔄 **Current Node:** {node_name}")
                                
                                # Show relevant output
                                with logs_placeholder.expander(f"📋 {node_name} Output", expanded=True):
                                    if isinstance(node_output, dict):
                                        st.json(node_output)
                                    else:
                                        st.write(node_output)
                        
                        st.session_state.workflow_started = True
                        st.session_state.workflow_stage = "Paused - Waiting for Offer Responses"
                        
                        st.success("✅ Workflow executed successfully!")
                        st.info("📧 Offer emails have been sent. Please check the 'Offer Responses' tab to simulate candidate replies.")
                        
                        # ✅ Load from LangGraph state, not db.py
                        try:
                            config = {"configurable": {"thread_id": job_id}}
                            final_graph_state = st.session_state.graph_app.get_state(config)
                            final_state = final_graph_state.values
                            
                            if final_state and 'offers_sent' in final_state and final_state['offers_sent']:
                                st.markdown("### 📤 Offers Sent To:")
                                for candidate in final_state['offers_sent']:
                                    st.markdown(f"- ✉️ **{candidate}**")
                            else:
                                st.warning("No offers were sent. Check the workflow logs above.")
                        except Exception as e:
                            st.error(f"Error loading offer status: {str(e)}")
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        st.exception(e)
    else:
        st.success("✅ Workflow is active!")
        st.info(f"**Job ID:** `{st.session_state.job_id}`")
        st.markdown("Navigate to the **Offer Responses** tab to continue the workflow.")

# Tab 2: Offer Responses (Simulated Webhook Interface)
with tab2:
    st.header("📨 Candidate Offer Responses")
    
    if not st.session_state.job_id:
        st.warning("⚠️ Please start a workflow first in the 'Start Workflow' tab.")
    else:
        # ✅ CRITICAL FIX: Read from LangGraph state, not db.py
        col_refresh, col_spacer = st.columns([1, 4])
        with col_refresh:
            if st.button("🔄 Refresh Status", use_container_width=True):
                st.rerun()
        try:
            config = {"configurable": {"thread_id": st.session_state.job_id}}
            graph_state = st.session_state.graph_app.get_state(config)
            current_state = graph_state.values
            
            if current_state and 'offers_sent' in current_state:
                offers_sent = current_state.get('offers_sent', [])
                offer_responses = current_state.get('offer_responses', [])
                
                # Show progress
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📤 Offers Sent", len(offers_sent))
                with col2:
                    st.metric("✅ Responses Received", len(offer_responses))
                with col3:
                    st.metric("⏳ Pending", len(offers_sent) - len(offer_responses))
                
                st.markdown("---")
                
                # Get candidates who haven't responded
                responded_candidates = [r['candidate'] for r in offer_responses]
                pending_candidates = [c for c in offers_sent if c not in responded_candidates]
                
                if pending_candidates:
                    st.markdown("### 📋 Pending Responses")
                    st.info(f"Waiting for responses from {len(pending_candidates)} candidate(s)")
                    
                    # Create response form for each pending candidate
                    for candidate in pending_candidates:
                        with st.expander(f"💬 Respond as: **{candidate}**", expanded=False):
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                response = st.radio(
                                    f"Select {candidate}'s response:",
                                    ["Accepted", "Rejected", "Negotiation"],
                                    key=f"response_{candidate}",
                                    horizontal=True
                                )
                            
                            with col2:
                                if st.button("📤 Submit", key=f"submit_{candidate}", use_container_width=True):
                                    with st.spinner(f"Processing {candidate}'s response..."):
                                        try:
                                            # Update state with offer reply
                                            st.session_state.graph_app.update_state(
                                                config,
                                                {
                                                    "offer_reply": {
                                                        "candidate": candidate,
                                                        "status": response
                                                    }
                                                }
                                            )
                                            
                                            # Resume the graph
                                            for event in st.session_state.graph_app.stream(None, config):
                                                pass
                                            
                                            st.success(f"✅ Response from {candidate} ({response}) processed!")
                                            st.balloons()
                                            time.sleep(1)
                                            st.rerun()
                                            
                                        except Exception as e:
                                            st.error(f"Error: {str(e)}")
                                            st.exception(e)
                else:
                    st.success("🎉 All candidates have responded!")
                    
                    # Show summary
                    st.markdown("### 📊 Response Summary")
                    
                    acceptances = [r for r in offer_responses if r['status'] == 'Accepted']
                    rejections = [r for r in offer_responses if r['status'] == 'Rejected']
                    negotiations = [r for r in offer_responses if r['status'] == 'Negotiation']
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown('<div class="success-box">', unsafe_allow_html=True)
                        st.markdown(f"### ✅ Accepted ({len(acceptances)})")
                        for acc in acceptances:
                            st.write(f"- {acc['candidate']}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown('<div class="warning-box">', unsafe_allow_html=True)
                        st.markdown(f"### ❌ Rejected ({len(rejections)})")
                        for rej in rejections:
                            st.write(f"- {rej['candidate']}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown('<div class="info-box">', unsafe_allow_html=True)
                        st.markdown(f"### 💬 Negotiation ({len(negotiations)})")
                        for neg in negotiations:
                            st.write(f"- {neg['candidate']}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    if acceptances and 'onboarding_submissions' in current_state:
                        st.markdown("### 📋 Onboarding Information Received")
                        
                        # ✅ Loop through the submissions list
                        all_submissions = current_state['onboarding_submissions']
                        
                        for submission in all_submissions:
                            st.markdown(f"""
                            <div class="info-box">
                                <h4>✅ {submission['candidate']}</h4>
                                <p><strong>Start Date:</strong> {submission.get('joining_date', 'Not provided')}</p>
                                <p><strong>Comments:</strong> {submission.get('comments', 'None')}</p>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Only show error if there are NO acceptances at all
                    elif not acceptances:
                        st.error("😞 No candidates accepted the offer. Hiring process concluded.")
                        st.session_state.workflow_complete = True
            else:
                st.info("⏳ No offers have been sent yet. Complete the workflow in the 'Start Workflow' tab first.")
        except Exception as e:
            st.error(f"Error loading offer status: {str(e)}")
            st.exception(e)
    
    st.info("💡 Candidates respond via onboarding forms sent in offer emails")
    st.markdown("Response options: **Accept** (with joining date), **Negotiate**, or **Reject**")

# Tab 3: Dashboard
with tab3:
    st.header("📊 Workflow Dashboard")
    
    if st.session_state.job_id:
        # ✅ Read from LangGraph state
        try:
            config = {"configurable": {"thread_id": st.session_state.job_id}}
            graph_state = st.session_state.graph_app.get_state(config)
            state = graph_state.values
            
            if state:
            # Job Description Section
                if 'job_description' in state and state['job_description']:
                    with st.expander("📝 Job Description", expanded=False):
                        try:
                            job_desc = json.loads(state['job_description'])
                            st.markdown(f"### {job_desc.get('title', 'N/A')}")
                            st.markdown(f"**Company:** {job_desc.get('company', 'N/A')}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("**Responsibilities:**")
                                for resp in job_desc.get('responsibilities', []):
                                    st.markdown(f"- {resp}")
                            
                            with col2:
                                st.markdown("**Qualifications:**")
                                for qual in job_desc.get('qualifications', []):
                                    st.markdown(f"- {qual}")
                        except:
                            st.text(state['job_description'])
            
                # Candidates Section
                if 'candidates' in state and state['candidates']:
                    with st.expander(f"👥 Sourced Candidates ({len(state['candidates'])})", expanded=False):
                        for i, candidate in enumerate(state['candidates'], 1):
                            st.markdown(f"**{i}. {candidate['name']}**")
                            st.caption(candidate['resume'][:200] + "...")
                            st.markdown("---")
                
                # Screened Candidates
                if 'screened_candidates' in state and state['screened_candidates']:
                    with st.expander(f"✅ Screened Candidates ({len(state['screened_candidates'])})", expanded=True):
                        for candidate in state['screened_candidates']:
                            st.markdown(f"**✓ {candidate['name']}**")
                
                # Interview Results
                if 'interview_results' in state and state['interview_results']:
                    with st.expander(f"🎤 Interview Results ({len(state['interview_results'])})", expanded=True):
                        for result in state['interview_results']:
                            status_emoji = "✅" if result['recommendation'] == 'Progress' else "❌"
                            st.markdown(f"{status_emoji} **{result['candidate_name']}** - {result['recommendation']}")
                            with st.container():
                                st.caption(f"**Evaluation:** {result['evaluation']}")
                
                # Final Shortlist
                if 'final_shortlist' in state and state['final_shortlist']:
                    st.markdown("### 🏆 Final Shortlist")
                    for candidate in state['final_shortlist']:
                        st.success(f"⭐ {candidate}")
            
                # Full State (collapsible)
                with st.expander("🔍 Full State (Debug)", expanded=False):
                    st.json(state)
        except Exception as e:
            st.error(f"Error loading workflow state: {str(e)}")
            st.exception(e)
    else:
        st.info("Start a workflow to see the dashboard")

# Tab 4: Debug
with tab4:
    st.header("🔍 Debug Information")
    
    st.markdown("### Session State")
    # Don't show the graph_app object itself (too large)
    session_dict = {k: v for k, v in dict(st.session_state).items() if k != 'graph_app'}
    st.json(session_dict)
    
    if st.session_state.job_id:
        st.markdown("### LangGraph State")
        try:
            config = {"configurable": {"thread_id": st.session_state.job_id}}
            graph_state = st.session_state.graph_app.get_state(config)
            
            st.write("**Values:**")
            st.json(graph_state.values)
            st.write(f"**Next Node:** {graph_state.next}")
            st.write(f"**Metadata:** {graph_state.metadata}")
            
            # Also show what db.py has (for comparison)
            st.markdown("### DB File State (for comparison)")
            db_state = load_state(st.session_state.job_id)
            if db_state:
                st.json(db_state)
            else:
                st.info("No state in db.py file")
                
        except Exception as e:
            st.error(f"Error getting graph state: {e}")
            st.exception(e)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "Advanced HR Agent System | Built with LangGraph & Streamlit"
    "</div>",
    unsafe_allow_html=True
)