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
if 'current_interrupt' not in st.session_state:
    st.session_state.current_interrupt = None
if 'interview_selections' not in st.session_state:
    st.session_state.interview_selections = {}
if 'interview_feedback' not in st.session_state:
    st.session_state.interview_feedback = {}
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
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "ðŸš€ Start Workflow", 
    "âœ… Approvals", 
    "ðŸ Offer Responses", 
    "ðŸ Dashboard", 
    "ðy Debug"
])

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
                    
                    try:
                        st.session_state.workflow_stage = "Running..."
                        
                        # Create placeholders
                        status_placeholder = st.empty()
                        logs_placeholder = st.empty()
                        
                        # ✅ Run workflow node by node
                        for event in st.session_state.graph_app.stream(initial_state, config):
                            for node_name, node_output in event.items():
                                st.session_state.workflow_stage = f"Executing: {node_name}"
                                status_placeholder.info(f"🔄 **Current Node:** {node_name}")
                                
                                # Show output
                                with logs_placeholder.expander(f"📋 {node_name} Output", expanded=False):
                                    if isinstance(node_output, dict):
                                        st.json(node_output)
                                    else:
                                        st.write(node_output)
                            
                            # ✅ Check for interrupts AFTER EACH EVENT
                            config_check = {"configurable": {"thread_id": job_id}}
                            graph_state = st.session_state.graph_app.get_state(config_check)
                            
                            if graph_state.next:  # Workflow paused
                                next_node = graph_state.next[0] if isinstance(graph_state.next, list) else graph_state.next
                                
                                # Store in session state for Tab 2
                                st.session_state.workflow_stage = f"⏸️ Paused at: {next_node}"
                                st.session_state.workflow_started = True
                                
                                status_placeholder.empty()  # Clear spinning indicator
                                logs_placeholder.empty()
                                
                                st.success("✅ Workflow started successfully!")
                                
                                # Show specific message based on where it's paused
                                if next_node == "human_approval":
                                    st.info("📋 **Action Required:** Please go to the **'✅ Approvals'** tab to review the job description.")
                                elif next_node == "interviewer":
                                    st.info("🎤 **Action Required:** Please go to the **'✅ Approvals'** tab to select interview candidates.")
                                elif next_node == "final_offer_approval":
                                    st.info("💼 **Action Required:** Please go to the **'✅ Approvals'** tab to approve final offers.")
                                elif next_node == "wait_for_offer_responses":
                                    st.info("📨 **Action Required:** Waiting for candidate responses. Go to **'📨 Offer Responses'** tab.")
                                
                                break  # Stop processing
                        
                        # If loop completes without interrupt
                        if not graph_state.next:
                            st.session_state.workflow_started = True
                            st.session_state.workflow_stage = "✅ Completed"
                            st.success("🎉 Workflow completed successfully!")
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        st.exception(e)
    
    else:  # Workflow already started
        st.success("✅ Workflow is active!")
        st.info(f"**Job ID:** `{st.session_state.job_id}`")
        
        # Show current status
        try:
            config = {"configurable": {"thread_id": st.session_state.job_id}}
            graph_state = st.session_state.graph_app.get_state(config)
            
            if graph_state.next:
                next_node = graph_state.next[0] if isinstance(graph_state.next, list) else graph_state.next
                
                st.markdown("### ⏸️ Workflow Paused")
                st.warning(f"**Waiting at node:** `{next_node}`")
                
                # Show actionable message
                if next_node == "human_approval":
                    st.info("👉 Go to the **'✅ Approvals'** tab to review the job description.")
                elif next_node == "interviewer":
                    st.info("👉 Go to the **'✅ Approvals'** tab to select candidates for interviews.")
                elif next_node == "final_offer_approval":
                    st.info("👉 Go to the **'✅ Approvals'** tab to approve final offers.")
                elif next_node == "wait_for_offer_responses":
                    st.info("👉 Go to the **'📨 Offer Responses'** tab to simulate candidate responses.")
            else:
                st.success("✅ Workflow completed!")
        
        except Exception as e:
            st.error(f"Error checking status: {e}")

# Tab 2: Human Approvals
with tab2:
    st.header("✅ Human Approval Required")
    
    # ✅ REFRESH BUTTON
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔄 Refresh", key="refresh_approvals_top", use_container_width=True):
            st.rerun()
    
    if not st.session_state.job_id:
        st.warning("⚠️ Please start a workflow first in the 'Start Workflow' tab.")
    else:
        config = {"configurable": {"thread_id": st.session_state.job_id}}
        
        try:
            # ✅ FORCE FRESH STATE READ
            graph_state = st.session_state.graph_app.get_state(config)
            
            # ✅ CRITICAL DEBUG - ALWAYS EXPANDED SO YOU CAN SEE IT
            with st.expander("🔍 Debug: Current State", expanded=True):
                st.write(f"**Next Node (raw):** `{repr(graph_state.next)}`")
                st.write(f"**Next Node (type):** `{type(graph_state.next)}`")
                st.write(f"**Workflow Stage:** `{st.session_state.workflow_stage}`")
                
                # Show what we're checking
                if graph_state.next:
                    if isinstance(graph_state.next, tuple):
                        st.warning(f"⚠️ Next is a TUPLE: {graph_state.next}")
                        st.info("Converting tuple to string for comparison...")
                    elif isinstance(graph_state.next, list):
                        st.success(f"✅ Next is a LIST: {graph_state.next}")
                    else:
                        st.info(f"ℹ️ Next is: {type(graph_state.next)}")
                    
                    st.success("✅ Workflow IS interrupted - approval UI should appear")
                else:
                    st.warning("⚠️ Workflow is NOT interrupted (next is empty)")
            
            # ✅ FIX: Handle tuple properly
            if graph_state.next:
                # Convert whatever format to string
                if isinstance(graph_state.next, tuple):
                    next_node = graph_state.next[0] if len(graph_state.next) > 0 else None
                elif isinstance(graph_state.next, list):
                    next_node = graph_state.next[0] if len(graph_state.next) > 0 else None
                else:
                    next_node = str(graph_state.next)
                
                st.info(f"📍 **Detected Next Node:** `{next_node}`")
                
                # ==============================
                # 1. JOB DESCRIPTION APPROVAL
                # ==============================
                if next_node == "human_approval":
                    st.markdown("### 📝 Job Description Approval Required")
                    
                    job_desc_json = graph_state.values.get("job_description")
                    
                    if job_desc_json:
                        try:
                            job_desc = json.loads(job_desc_json)
                            
                            # Display job description
                            st.markdown(f"## {job_desc.get('title', 'N/A')}")
                            st.markdown(f"**Company:** {job_desc.get('company', 'N/A')}")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown("### 📋 Responsibilities")
                                for resp in job_desc.get('responsibilities', []):
                                    st.markdown(f"- {resp}")
                            
                            with col2:
                                st.markdown("### 🎓 Qualifications")
                                for qual in job_desc.get('qualifications', []):
                                    st.markdown(f"- {qual}")
                            
                            st.markdown("### 🎁 What We Offer")
                            for offer in job_desc.get('offerings', []):
                                st.markdown(f"- {offer}")
                            
                            # Approval buttons
                            st.markdown("---")
                            col1, col2, col3 = st.columns([1, 1, 2])
                            
                            with col1:
                                if st.button("✅ Approve", key="approve_job_desc", use_container_width=True):
                                    with st.spinner("Approving and continuing workflow..."):
                                        st.session_state.graph_app.update_state(
                                            config,
                                            {"job_description_approved": True}
                                        )
                                        # Resume workflow
                                        for event in st.session_state.graph_app.stream(None, config):
                                            pass
                                        st.success("✅ Job description approved!")
                                        time.sleep(1)
                                        st.rerun()
                            
                            with col2:
                                if st.button("❌ Reject", key="reject_job_desc", use_container_width=True):
                                    st.session_state.graph_app.update_state(
                                        config,
                                        {"job_description_approved": False}
                                    )
                                    # Resume workflow
                                    for event in st.session_state.graph_app.stream(None, config):
                                        pass
                                    st.error("❌ Job description rejected. Workflow ended.")
                                    time.sleep(1)
                                    st.rerun()
                        
                        except json.JSONDecodeError:
                            st.error("Error parsing job description")
                    else:
                        st.error("Job description not found in state")
                
                # ==============================
                # 2. INTERVIEW SELECTIONS
                # ==============================
                elif next_node == "interviewer":
                    st.markdown("### 🎤 Interview Candidate Selection")
                    
                    screened_candidates = graph_state.values.get("screened_candidates", [])
                    
                    if screened_candidates:
                        st.info(f"📊 {len(screened_candidates)} candidates passed screening. Select who to interview:")
                        
                        existing_selections = graph_state.values.get("interview_selections", {})
                        existing_feedback = graph_state.values.get("interview_feedback", {})
                        
                        # STAGE 1: Get selections
                        if not existing_selections:
                            with st.form("interview_selections_form"):
                                selections = {}
                                
                                for candidate in screened_candidates:
                                    st.markdown(f"#### {candidate['name']}")
                                    st.caption(candidate['resume'][:200] + "...")
                                    
                                    selections[candidate['name']] = st.radio(
                                        f"Decision for {candidate['name']}:",
                                        ["yes", "no", "skip"],
                                        format_func=lambda x: {"yes": "✅ Interview", "no": "❌ Reject", "skip": "⏭️ Skip"}[x],
                                        key=f"select_{candidate['name']}",
                                        horizontal=True
                                    )
                                    st.markdown("---")
                                
                                if st.form_submit_button("📤 Submit Selections", use_container_width=True):
                                    with st.spinner("Processing selections..."):
                                        st.session_state.graph_app.update_state(
                                            config,
                                            {"interview_selections": selections}
                                        )
                                        st.success("✅ Selections saved!")
                                        time.sleep(1)
                                        st.rerun()
                        
                        # STAGE 2: Get feedback
                        else:
                            st.success("✅ Initial selections recorded")
                            
                            to_interview = [name for name, sel in existing_selections.items() if sel == "yes"]
                            
                            if to_interview:
                                st.markdown(f"### 📝 Conducting Interviews ({len(to_interview)} candidates)")
                                
                                if len(existing_feedback) >= len(to_interview):
                                    st.success("✅ All interviews complete! Continuing workflow...")
                                    for event in st.session_state.graph_app.stream(None, config):
                                        pass
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    with st.form("interview_feedback_form"):
                                        feedback = {}
                                        
                                        for candidate_name in to_interview:
                                            if candidate_name not in existing_feedback:
                                                st.markdown(f"#### 🎤 Interview Feedback: {candidate_name}")
                                                
                                                feedback[candidate_name] = {
                                                    "evaluation": st.text_area(
                                                        f"Evaluation for {candidate_name}:",
                                                        key=f"eval_{candidate_name}",
                                                        height=100
                                                    ),
                                                    "recommendation": st.radio(
                                                        f"Recommendation for {candidate_name}:",
                                                        ["Progress", "Reject"],
                                                        key=f"rec_{candidate_name}",
                                                        horizontal=True
                                                    )
                                                }
                                                st.markdown("---")
                                        
                                        if st.form_submit_button("📤 Submit Feedback", use_container_width=True):
                                            with st.spinner("Processing feedback..."):
                                                all_feedback = {**existing_feedback, **feedback}
                                                
                                                st.session_state.graph_app.update_state(
                                                    config,
                                                    {"interview_feedback": all_feedback}
                                                )
                                                
                                                for event in st.session_state.graph_app.stream(None, config):
                                                    pass
                                                
                                                st.success("✅ Feedback submitted!")
                                                time.sleep(1)
                                                st.rerun()
                            else:
                                st.info("No candidates selected for interviews. Continuing workflow...")
                                for event in st.session_state.graph_app.stream(None, config):
                                    pass
                                time.sleep(1)
                                st.rerun()
                
                # ==============================
                # 3. FINAL OFFER APPROVAL
                # ==============================
                elif next_node == "final_offer_approval":
                    st.markdown("### 💼 Final Offer Approval")
                    
                    final_shortlist = graph_state.values.get("final_shortlist", [])
                    
                    if final_shortlist:
                        st.success(f"🏆 AI recommends sending offers to {len(final_shortlist)} candidate(s):")
                        
                        for candidate in final_shortlist:
                            st.markdown(f"- ✅ **{candidate}**")
                        
                        st.markdown("---")
                        col1, col2, col3 = st.columns([1, 1, 2])
                        
                        with col1:
                            if st.button("✅ Approve Offers", key="approve_offers", use_container_width=True):
                                with st.spinner("Approving and sending offers..."):
                                    st.session_state.graph_app.update_state(
                                        config,
                                        {"final_offer_approved": True}
                                    )
                                    for event in st.session_state.graph_app.stream(None, config):
                                        pass
                                    st.success("✅ Offers approved and sent!")
                                    time.sleep(1)
                                    st.rerun()
                        
                        with col2:
                            if st.button("❌ Reject", key="reject_offers", use_container_width=True):
                                st.session_state.graph_app.update_state(
                                    config,
                                    {"final_offer_approved": False}
                                )
                                for event in st.session_state.graph_app.stream(None, config):
                                    pass
                                st.error("❌ Offers rejected. Workflow ended.")
                                time.sleep(1)
                                st.rerun()
                    else:
                        st.warning("No candidates in final shortlist")
                
                else:
                    st.warning(f"⚠️ Unknown node: `{next_node}`")
                    st.info("Workflow is at an unhandled interrupt point")
            
            else:
                st.success("✅ No approvals needed right now. Workflow is running or completed.")
        
        except Exception as e:
            st.error(f"Error checking approval status: {str(e)}")
            st.exception(e)

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