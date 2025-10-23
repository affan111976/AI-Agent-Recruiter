import json
import uuid
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
# StateGraph -> defines the entire structure of graph
from tools.post_to_linkedin_tool import post_to_linkedin_tool
from tools.schedule_interview_tool import schedule_interview_tool
from tools.send_email_tool import send_email_tool

import os
from dotenv import load_dotenv

from state import GraphState, Candidate, InterviewResult
from tools.sourcing_tool import candidate_sourcing_tool
from agents.analyst import create_job_analyst_agent
from agents.screener import create_resume_screener_agent
from agents.interviewer import create_interviewer_agent
from agents.decision_maker import create_decision_maker_agent

from langgraph.checkpoint.memory import MemorySaver

from langchain_google_genai import ChatGoogleGenerativeAI
load_dotenv()

# Initialize the LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0, convert_system_message_to_human=True)

# using analyst agent for creating job description
def run_job_analyst(state: GraphState):
    print("--- CREATING JOB DESCRIPTION ---")
    agent = create_job_analyst_agent(llm)
    job_description = agent.invoke({"user_request": state["initial_request"]})
    return {"job_description": json.dumps(job_description, indent=2)}

def get_human_approval(state: GraphState):
    print("--- AWAITING JOB DESCRIPTION APPROVAL ---")
    job_desc_json = state["job_description"]
    print("Generated Job Description:")
    print(job_desc_json)
    
    while True:
        approval = input("Approve this job description? (yes/no): ").lower()
        if approval == 'yes':
            return {}
        elif approval == 'no':
            return {"error": "Job description rejected by user."}

# Post job description
def post_job_description(state: GraphState):
    print("--- POSTING JOB DESCRIPTION ---")
    # In a real app, get the token securely
    job_desc_dict = json.loads(state["job_description"])
    
    # Call the new linkedin tool
    result = post_to_linkedin_tool.invoke({"job_description": job_desc_dict})
    
    print("(SIMULATED) Job posted successfully.")
    return {}

def run_candidate_sourcer(state: GraphState):
    """
    Sources candidates for the job position.
    
    In production, this would use the actual job_id from the job posting.
    Currently using dummy candidates from the sourcing_tool.
    """
    print("--- SOURCING CANDIDATES ---")
    
    # Get the job_id from state if available, otherwise use a placeholder
    job_id = state.get("job_id", "DUMMY_JOB_ID_12345")
    
    print(f"Looking for candidates for Job ID: {job_id}")
    
    # Call the sourcing tool
    # This will return dummy candidates by default
    # To use real ATS data, modify the sourcing_tool.py file and uncomment the API code
    candidates = candidate_sourcing_tool.invoke(job_id)
    
    if not candidates:
        print("--- WARNING: No candidates found! ---")
        return {"candidates": [], "error": "No candidates found for this position."}
    
    print(f"--- Found {len(candidates)} candidates ---")
    for i, candidate in enumerate(candidates, 1):
        print(f"{i}. {candidate['name']}")
    
    return {"candidates": candidates}

def run_resume_screener(state: GraphState):
    """Screen candidates against job requirements."""
    print("--- SCREENING RESUMES ---")
    
    # Validate we have candidates to screen
    candidates = state.get("candidates", [])
    if not candidates:
        print("--- ERROR: No candidates to screen ---")
        return {"error": "No candidates available for screening."}
    
    agent = create_resume_screener_agent(llm)
    
    # Format candidates for the LLM
    candidates_str = "\n\n".join([
        f"=== CANDIDATE {i+1} ===\nName: {c['name']}\nResume: {c['resume']}"
        for i, c in enumerate(candidates)
    ])
    print(candidates_str)
    print(f"Screening {len(candidates)} candidates...")
    
    try:
        screened_results = agent.invoke({
            "job_description": state["job_description"],
            "candidates": candidates_str
        })
        print(screened_results)
        # Log the reasoning
        if hasattr(screened_results, 'reasoning'):
            print(f"\n--- SCREENING REASONING ---")
            print(screened_results.reasoning)
        
        # Map passed candidate names to full candidate objects
        all_candidates_map = {c['name']: c for c in candidates}
        print(all_candidates_map)

        passed_candidates = [
            all_candidates_map[name] 
            for name in screened_results.passed 
            if name in all_candidates_map
        ]
        print(passed_candidates)
        
        # Log results
        print(f"\n--- SCREENING RESULTS ---")
        print(f"Passed: {len(passed_candidates)} candidates")
        for name in screened_results.passed:
            print(f"  ✓ {name}")
        
        if screened_results.failed:
            print(f"Failed: {len(screened_results.failed)} candidates")
            for name in screened_results.failed:
                print(f"  ✗ {name}")
        
        if not passed_candidates:
            print("\n--- WARNING: NO CANDIDATES PASSED SCREENING ---")
            return {"error": "No candidates passed the screening stage."}
        
        return {"screened_candidates": passed_candidates}
    
    except Exception as e:
        print(f"--- ERROR DURING SCREENING: {e} ---")
        return {"error": f"Screening failed: {str(e)}"}

def run_interview_scheduler(state: GraphState):
    print("--- SENDING INTERVIEW INVITATIONS ---")
    
    job_title = json.loads(state["job_description"])["title"]
    job_id = state.get("job_id", str(uuid.uuid4())) 
    
    candidate_emails = { "Affan Ahmad": "affan.ahmad@email.com" } 
    
    for candidate in state["screened_candidates"]:
        candidate_name = candidate["name"]
        
        if candidate_name in candidate_emails:
            # Create a unique scheduling link with metadata for the webhook
            scheduling_link = f"https://calendly.com/your-company/interview?job_id={job_id}&candidate={candidate_name}"
            
            # Change the email body to be a call-to-action
            email_body = (
                f"Dear {candidate_name},\n\n"
                f"We were impressed with your background and would like to invite you for an interview for the {job_title} position.\n\n"
                f"Please use the following link to select a time that works for you:\n{scheduling_link}\n\n"
                "We look forward to speaking with you."
            )
            
            # send_email_tool.invoke(...)
            print(f"(SIMULATED) Sending scheduling link to {candidate_name}.")

    # 3. The node finishes. The graph now pauses and waits for the webhook.
    print("--- Workflow paused. Waiting for candidates to schedule interviews. ---")
    return {"job_id": job_id} 

def process_interview_confirmation(state: GraphState):
    """Processes the confirmation that an interview has been scheduled."""
    confirmation_data = state.get("interview_confirmation")
    candidate_name = confirmation_data["candidate"]
    
    print(f"--- CONFIRMATION RECEIVED: {candidate_name} has scheduled an interview. ---")
    
    # We now add the confirmed candidate to a new list in the state
    # This ensures the 'run_interviewer' node only runs for confirmed candidates
    confirmed_candidates = state.get("confirmed_candidates", [])
    
    # Find the full candidate object
    candidate_to_interview = next((c for c in state["screened_candidates"] if c["name"] == candidate_name), None)
    
    if candidate_to_interview:
        confirmed_candidates.append(candidate_to_interview)
        
    return {"confirmed_candidates": confirmed_candidates}

def run_interviewer(state: GraphState):
    print("--- PREPARING INTERVIEWS ---")
    interviewer_prep_agent = create_interviewer_agent(llm) 
    human_feedback_results = []
    
    candidates_to_interview = state.get("confirmed_candidates") or state.get("screened_candidates", [])

    for candidate in state["screened_candidates"]:
        print(f"--- Generating Interview Kit for: {candidate['name']} ---")
        
        # AI generates the prep kit
        prep_kit = interviewer_prep_agent.invoke({
            "job_description": state["job_description"],
            "candidate_name": candidate["name"],
            "candidate_resume": candidate["resume"]
        })
        
        print("\n--- INTERVIEW PREPARATION KIT ---")
        print(f"Questions for {candidate['name']}:")
        for q in prep_kit.questions:
            print(f"- {q}")
        print(f"AI Evaluation Summary: {prep_kit.evaluation}")
        
        # Graph pauses to collect human feedback
        print("\n--- PLEASE CONDUCT THE INTERVIEW AND PROVIDE FEEDBACK ---")
        evaluation = input("Enter your evaluation summary: ")
        recommendation = input("Your recommendation (Progress/Reject): ").capitalize()
        
        human_feedback_results.append({
            "candidate_name": candidate["name"],
            "interview_questions": prep_kit.questions,
            "evaluation": evaluation, # Storing human feedback
            "recommendation": recommendation
        })
        
    return {"interview_results": human_feedback_results}

def run_decision_maker(state: GraphState):
    print("--- MAKING FINAL DECISION ---")
    agent = create_decision_maker_agent(llm)
    results_str = json.dumps(state["interview_results"], indent=2)
    final_decision = agent.invoke({
        "job_description": state["job_description"],
        "interview_results": results_str
    })
    return {"final_shortlist": final_decision.shortlisted_candidates}

# Get final approval before sending offers
def get_final_offer_approval(state: GraphState):
    print("--- AWAITING FINAL OFFER APPROVAL ---")
    final_shortlist = state["final_shortlist"]
    
    if not final_shortlist:
        print("AI recommended no candidates for the final shortlist.")
        return {"error": "No candidates to make offers to."}

    print("AI has recommended the following candidates for offers:")
    for name in final_shortlist:
        print(f"- {name}")
    
    while True:
        approval = input("Do you approve sending offers to this shortlist? (yes/no): ").lower()
        if approval == 'yes':
            return {} 
        elif approval == 'no':
            return {"error": "Final shortlist rejected by user. Halting process."}

def send_offers(state: GraphState):
    print("--- SENDING OFFERS ---")
    final_shortlist = state["final_shortlist"]
    job_id = state.get("job_id", "unknown")
    
    # In a real app, you'd have the candidates' emails
    candidate_emails = {"Alice Johnson": "alice@email.com", "Diana Miller": "diana@email.com"}
    
    for name in final_shortlist:
        if name in candidate_emails:
            # Here you would generate the email body, perhaps with another LLM call
            email_body = f"Dear {name},\n\nWe are pleased to offer you the position... "
            # send_email_tool.invoke(...)
            print(f"(SIMULATED) Sending offer email to {name}.")
    print("--- Waiting for offer replies via webhook ---")
    return {"job_id": job_id}  

def process_offer_reply(state: GraphState):
    """Processes the reply from the candidate."""
    reply_data = state.get("offer_reply")
    
    if not reply_data:
        print("--- ERROR: No offer reply data found in state ---")
        return {"error": "No offer reply data available"}
    
    print(f"--- PROCESSING OFFER REPLY for {reply_data['candidate']}: {reply_data['status']} ---")
    return {"last_offer_reply": reply_data['status']}

def route_offer_reply(state: GraphState):
    status = state.get("last_offer_reply")

    if not status:  
        return "end"

    if status == "Accepted":
        return "acceptance"
    elif status == "Rejected":
        return "rejection"
    else: 
        return "end"

def handle_acceptance(state: GraphState):
    print("--- CANDIDATE ACCEPTED OFFER - PROCESS COMPLETE ---")
    return {}

def handle_rejection(state: GraphState):
    print("--- CANDIDATE REJECTED OFFER ---")
    return {}

# Starts the onboarding process
def initiate_onboarding(state: GraphState):
    """Sends a welcome email asking for joining info."""
    print("--- INITIATING ONBOARDING PROCESS ---")
    reply_data = state.get("offer_reply")
    
    if not reply_data:
        print("--- ERROR: No offer reply data for onboarding ---")
        return {"error": "Missing offer reply data"}
    
    candidate_name = reply_data["candidate"]
    job_id = state["job_id"] 

    # In a real app, you'd have the candidate's email
    candidate_email = "alice@email.com" 

    # Create a link to a secure portal/form for the candidate to submit their info
    onboarding_form_link = f"https://yourapi.com/onboarding-form?job_id={job_id}&candidate={candidate_name}"

    email_body = (
        f"Dear {candidate_name},\n\n"
        f"Welcome to the team! We are thrilled to have you join us.\n\n"
        f"To begin the onboarding process, please use the secure link below to provide your preferred joining date and upload any necessary documents:\n{onboarding_form_link}\n\n"
        "We will be in touch shortly after you submit your information.\n\n"
        "Best regards,\n"
        "HR Department"
    )

    # send_email_tool.invoke(...)
    print(f"(SIMULATED) Sending onboarding email to {candidate_name}.")

    # The graph now pauses and waits for the candidate to fill out the form.
    return {"onboarding_status": "pending_candidate_info"}

# Processes the candidate's submitted info
def finalize_onboarding(state: GraphState):
    """Processes the joining date and sends a final confirmation."""
    print("--- FINALIZING ONBOARDING ---")
    onboarding_data = state.get("onboarding_info")
    
    if not onboarding_data:
        print("--- ERROR: No onboarding data found ---")
        return {"error": "Missing onboarding data"}
    
    candidate_name = onboarding_data["candidate"]
    joining_date = onboarding_data["joining_date"]

    print(f"Received joining date for {candidate_name}: {joining_date}")

    email_body = (
        f"Dear {candidate_name},\n\n"
        f"This email confirms that your start date is set for {joining_date}.\n\n"
        "We have begun preparing for your arrival. More details about your first day will be sent shortly.\n\n"
        "Welcome aboard!"
    )

    # send_email_tool.invoke(...)
    print(f"(SIMULATED) Sending final confirmation email to {candidate_name}.")

    return {"onboarding_status": "complete", "joining_date": joining_date}

# Define Conditional Edges
def should_continue(state: GraphState):
    if state.get("error"):
        return "end"
    if not state.get("screened_candidates"):
        return "end"
    return "continue"

# Define the Graph
def build_graph():
    memory = MemorySaver()
    
    # initializing the graph with name workflow
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("job_analyst", run_job_analyst) #(node name, function name)

    workflow.add_node("human_approval", get_human_approval) 
    workflow.add_node("post_job", post_job_description) 

    workflow.add_node("candidate_sourcer", run_candidate_sourcer)
    workflow.add_node("resume_screener", run_resume_screener)
    workflow.add_node("interview_scheduler", run_interview_scheduler)
    workflow.add_node("process_interview_confirmation", process_interview_confirmation)
    workflow.add_node("interviewer", run_interviewer)
    workflow.add_node("decision_maker", run_decision_maker)
    workflow.add_node("final_offer_approval", get_final_offer_approval)
    workflow.add_node("send_offers", send_offers) 
    workflow.add_node("process_offer_reply", process_offer_reply) 
    workflow.add_node("handle_acceptance", handle_acceptance) 
    workflow.add_node("handle_rejection", handle_rejection) 
    workflow.add_node("initiate_onboarding", initiate_onboarding)
    workflow.add_node("finalize_onboarding", finalize_onboarding)

    # Set the entry point
    workflow.set_entry_point("job_analyst")

    # Add edges
    workflow.add_edge("job_analyst", "human_approval")

    # Add a conditional edge for approval
    workflow.add_conditional_edges(
        "human_approval",
        lambda state: "continue" if not state.get("error") else "end",
        {"continue": "post_job", "end": END}
    )
    workflow.add_edge("post_job", "candidate_sourcer")
    workflow.add_edge("candidate_sourcer", "resume_screener")
    
    workflow.add_conditional_edges(
        "resume_screener",
        should_continue,
        {
            "continue": "interview_scheduler",
            "end": END,
        },
    )
    
    workflow.add_edge("interview_scheduler", "interviewer")
    workflow.add_edge("interviewer", "decision_maker")
    workflow.add_edge("decision_maker", "final_offer_approval")

    # Add a conditional edge for the final approval
    workflow.add_conditional_edges(
        "final_offer_approval",
        lambda state: "continue" if not state.get("error") else "end",
        {
            "continue": "send_offers", 
            "end": END
        }
    )

    workflow.add_edge("send_offers", "process_offer_reply")

    workflow.add_conditional_edges(
        "process_offer_reply",
        route_offer_reply,
        {
            "acceptance": "handle_acceptance",
            "rejection": "handle_rejection",
            "end": END
        }
    )
    workflow.add_edge("handle_acceptance", "initiate_onboarding")
    workflow.add_edge("initiate_onboarding", "finalize_onboarding")
    workflow.add_edge("finalize_onboarding", END)
    workflow.add_edge("handle_rejection", END) 


    # Compile the graph
    app = workflow.compile(checkpointer=memory)
    return app

# To run this file directly for testing
if __name__ == "__main__":
    app = build_graph()
    
    # Example invocation
    initial_input = {
        "initial_request": "We need to hire a senior python developer with experience in building web applications."
    }
    
    config = {"configurable": {"thread_id": "test-123"}} 
    
    for event in app.stream(initial_input, config):
        for key, value in event.items():
            print(f"Node '{key}' output:")
            print("---")
            print(value)
        print("\n" + "="*30 + "\n")