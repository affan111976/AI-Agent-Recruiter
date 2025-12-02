import json
import uuid
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
# StateGraph -> defines the entire structure of graph
from langgraph.checkpoint.sqlite import SqliteSaver
from tools.post_to_linkedin_tool import post_to_linkedin_tool
from tools.schedule_interview_tool import schedule_interview_tool
from tools.send_email_tool import send_email_tool
from langgraph.errors import NodeInterrupt
import os
from dotenv import load_dotenv
from config import API_BASE_URL 
import sqlite3
from state import GraphState, Candidate, InterviewResult
from tools.sourcing_tool import candidate_sourcing_tool
from agents.analyst import create_job_analyst_agent
from agents.screener import create_resume_screener_agent
from agents.interviewer import create_interviewer_agent
from agents.decision_maker import create_decision_maker_agent

from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq

from langchain_google_genai import ChatGoogleGenerativeAI
load_dotenv()


from logging_config import setup_logger

logger = setup_logger("Workflow")

llm = ChatGroq(
    model="llama-3.3-70b-versatile",  
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY")  
)

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

def post_job_description(state: GraphState):
    """
    Post job description with Google Form link.
    Since we don't have LinkedIn, we'll create a shareable job post with the form.
    """
    print("--- POSTING JOB DESCRIPTION ---")
    
    job_desc_dict = json.loads(state["job_description"])
    job_id = state.get("job_id", str(uuid.uuid4()))
    
    # Get Google Form URL from environment
    google_form_url = os.getenv("GOOGLE_FORM_URL")
    
    if not google_form_url:
        print("⚠️  WARNING: GOOGLE_FORM_URL not set in .env")
        google_form_url = "https://forms.google.com/your-form-link"
    
    # Create a formatted job posting
    print("\n" + "="*70)
    print("🎯 JOB POSTING")
    print("="*70)
    print(f"Title: {job_desc_dict['title']}")
    print(f"Company: {job_desc_dict['company']}")
    print("\nResponsibilities:")
    for resp in job_desc_dict['responsibilities']:
        print(f"  • {resp}")
    print("\nQualifications:")
    for qual in job_desc_dict['qualifications']:
        print(f"  • {qual}")
    print("\nWhat We Offer:")
    for offer in job_desc_dict['offerings']:
        print(f"  • {offer}")
    print("\n" + "="*70)
    print(f"📝 APPLICATION FORM: {google_form_url}")
    print("="*70 + "\n")
    
    # Save job posting to file for reference
    with open(f"job_posting_{job_id}.txt", "w") as f:
        f.write(f"JOB POSTING - {job_desc_dict['title']}\n")
        f.write("="*70 + "\n\n")
        f.write(json.dumps(job_desc_dict, indent=2))
        f.write(f"\n\nAPPLY HERE: {google_form_url}\n")
    
    print(f"💾 Job posting saved to: job_posting_{job_id}.txt")
    print("📤 Share this file or the Google Form link with candidates\n")
    
    return {"job_id": job_id}

def run_candidate_sourcer(state: GraphState):
    """
    Sources candidates - now uses real applications from LinkedIn.
    """
    print("--- CHECKING FOR CANDIDATE APPLICATIONS ---")
    
    job_id = state.get("job_id", "UNKNOWN")
    
    # Check if candidates already exist in state (from webhook submissions)
    existing_candidates = state.get("candidates", [])
    
    if existing_candidates:
        print(f"✅ Found {len(existing_candidates)} applications already in system")
        return {"candidates": existing_candidates}
    
    # Otherwise, call the sourcing tool (which now reads from state)
    candidates = candidate_sourcing_tool.invoke(job_id)
    
    if not candidates:
        print("⚠️  No applications received yet.")
        print("💡 Candidates need to apply via the LinkedIn job posting.")
        return {"candidates": [], "error": "No candidates have applied yet. Please wait for applications."}
    
    print(f"✅ Loaded {len(candidates)} real applicants")
    return {"candidates": candidates}

def run_resume_screener(state: GraphState):
    """Screen candidates against job requirements."""
    logger.info("--- SCREENING RESUMES ---")
    
    # Validate we have candidates to screen
    candidates = state.get("candidates", [])
    if not candidates:
        logger.warning("No candidates to screen")
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
        logger.info(f"Screening complete. Passed: {len(passed_candidates)}")
        candidate_word = "candidate" if len(passed_candidates) == 1 else "candidates"
        print(f"Passed: {len(passed_candidates)} {candidate_word}")
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
        logger.error(f"Error during screening: {e}", exc_info=True)
        return {"error": str(e)}

def run_interview_scheduler(state: GraphState):
    print("--- SENDING INTERVIEW INVITATIONS ---")
    
    job_title = json.loads(state["job_description"])["title"]
    job_id = state.get("job_id", str(uuid.uuid4())) 
    
    # ✅ Your real Calendly link
    CALENDLY_LINK = "https://calendly.com/affanahmadbst/new-meeting"
    
    for candidate in state["screened_candidates"]:
        candidate_name = candidate["name"]
        candidate_email = candidate.get("email")  # ✅ Get email from candidate data
        
        if not candidate_email:
            print(f"⚠️ No email found for candidate: {candidate_name}")
            continue  # Skip this candidate and move to next one
        
        # ✅ THIS CODE MUST BE OUTSIDE THE "if not" BLOCK
        # Create scheduling link with UTM parameters to track candidate
        scheduling_link = f"{CALENDLY_LINK}?name={candidate_name}&email={candidate_email}"
        
        # Email subject and body
        subject = f"Interview Invitation - {job_title} Position"
        email_body = (
            f"Dear {candidate_name},\n\n"
            f"We were impressed with your background and would like to invite you for an interview for the {job_title} position.\n\n"
            f"Please use the following link to select a time that works for you:\n{scheduling_link}\n\n"
            "We look forward to speaking with you.\n\n"
            "Best regards,\n"
            "Affan Ahmad\nHR Team"
        )
        
        # Send the email
        try:
            result = send_email_tool.invoke({
                "recipient_email": candidate_email,
                "subject": subject,
                "body": email_body
            })
            print(f"✅ {result}")
        except Exception as e:
            print(f"❌ Failed to send email to {candidate_name}: {e}")

    print("--- Interview invitations sent. Waiting for candidates to schedule. ---")
    return {"job_id": job_id}

def process_interview_confirmation(state: GraphState):
    """Processes the confirmation that an interview has been scheduled."""
    confirmation_data = state.get("interview_confirmation")
    candidate_name = confirmation_data["candidate"]
    
    print(f"--- CONFIRMATION RECEIVED: {candidate_name} has scheduled an interview. ---")
    
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
    
    # ✅ Only process candidates who have confirmed their interviews
    screened_candidates = state.get("screened_candidates", [])
    
    print(f"\n{'='*70}")
    print(f"📋 {len(screened_candidates)} shortlisted candidates")
    print(f"{'='*70}\n")
    
    # ✅ Loop through confirmed candidates and ask for approval
    for candidate in screened_candidates:
        print(f"\n{'─'*70}")
        print(f"📌 CANDIDATE: {candidate['name']}")
        print(f"{'─'*70}")
        print(f"Resume Preview:")
        print(f"  {candidate['resume'][:200]}...")  # Show first 200 chars
        print(f"{'─'*70}\n")
        
        # ✅ Ask for human approval before generating interview kit
        while True:
            approval = input(f"Generate interview kit for {candidate['name']}? (yes/no/skip): ").lower().strip()
            
            if approval == 'yes':
                print(f"\n✅ Generating interview kit for {candidate['name']}...\n")
                break
            elif approval == 'no':
                print(f"❌ Skipping {candidate['name']} - will not interview this candidate.\n")
                # Add a rejection entry
                human_feedback_results.append({
                    "candidate_name": candidate["name"],
                    "interview_questions": [],
                    "evaluation": "Candidate skipped by HR - not interviewed", 
                    "recommendation": "Reject"
                })
                break
            elif approval == 'skip':
                print(f"⏭️ Skipping {candidate['name']} for now.\n")
                break
            else:
                print("❌ Invalid input. Please enter 'yes', 'no', or 'skip'.")
        
        # If user said 'no' or 'skip', continue to next candidate
        if approval != 'yes':
            continue
        
        # ✅ Generate interview kit (only if approved)
        print(f"--- Generating Interview Kit for: {candidate['name']} ---")
        
        try:
            # AI generates the prep kit
            prep_kit = interviewer_prep_agent.invoke({
                "job_description": state["job_description"],
                "candidate_name": candidate["name"],
                "candidate_resume": candidate["resume"]
            })
            
            print("\n" + "="*70)
            print(f"📝 INTERVIEW PREPARATION KIT - {candidate['name']}")
            print("="*70)
            print(f"\n🔍 AI Evaluation Summary:")
            print(f"   {prep_kit.evaluation}\n")
            print(f"❓ Suggested Interview Questions:")
            for i, q in enumerate(prep_kit.questions, 1):
                print(f"   {i}. {q}")
            print("\n" + "="*70)
            
            # ✅ Graph pauses to collect human feedback after interview
            print(f"\n🎤 CONDUCT THE INTERVIEW WITH {candidate['name']}")
            print("="*70)
            
            conduct = input("\nHave you conducted the interview? (yes/skip): ").lower().strip()
            
            if conduct != 'yes':
                print(f"⏸️ Interview not conducted yet for {candidate['name']}. Skipping feedback.\n")
                continue
            
            print("\n📋 Please provide your feedback:")
            evaluation = input("  Enter your evaluation summary: ").strip()
            
            while True:
                recommendation = input("  Your recommendation (Progress/Reject): ").strip().capitalize()
                if recommendation in ['Progress', 'Reject']:
                    break
                print("  ❌ Please enter either 'Progress' or 'Reject'")
            
            human_feedback_results.append({
                "candidate_name": candidate["name"],
                "interview_questions": prep_kit.questions,
                "evaluation": evaluation, 
                "recommendation": recommendation
            })
            
            print(f"✅ Feedback recorded for {candidate['name']}\n")
            
        except Exception as e:
            print(f"❌ Error generating interview kit for {candidate['name']}: {e}")
            print("Skipping this candidate...\n")
            continue
    
    # ✅ Summary
    print("\n" + "="*70)
    print("📊 INTERVIEW STAGE SUMMARY")
    print("="*70)
    print(f"Total candidates confirmed: {len(screened_candidates)}")
    print(f"Interviews conducted: {len(human_feedback_results)}")
    
    if human_feedback_results:
        print("\nResults:")
        for result in human_feedback_results:
            status = "✅ Progress" if result['recommendation'] == 'Progress' else "❌ Reject"
            print(f"  • {result['candidate_name']}: {status}")
    else:
        print("\n⚠️ No interviews were conducted.")
    
    print("="*70 + "\n")
    
    return {"interview_results": human_feedback_results}

# In graph.py - run_decision_maker function
def run_decision_maker(state: GraphState):
    print("--- MAKING FINAL DECISION ---")
    agent = create_decision_maker_agent(llm)
    results_str = json.dumps(state["interview_results"], indent=2)
    
    # ✅ ADD THIS
    print(f"\n🔍 DEBUG: Interview results names:")
    for result in state["interview_results"]:
        print(f"   - {result['candidate_name']}")
    
    final_decision = agent.invoke({
        "job_description": state["job_description"],
        "interview_results": results_str
    })
    
    # ✅ AND THIS
    print(f"\n🔍 DEBUG: Final shortlist names:")
    for name in final_decision.shortlisted_candidates:
        print(f"   - {name}")
    
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
    """Send offer emails with onboarding form link."""
    print("--- SENDING OFFERS WITH ONBOARDING FORMS ---")
    final_shortlist = state["final_shortlist"]
    job_id = state.get("job_id", "unknown")
    job_title = json.loads(state["job_description"])["title"]
    
    candidates_by_name = {c["name"]: c for c in state.get("screened_candidates", [])}

    offers_sent = []
    
    for name in final_shortlist:
        candidate = candidates_by_name.get(name)
        if not candidate or not candidate.get("email"):
            print(f"❌ No email for {name}")
            continue
        
        candidate_email = candidate["email"]
            
        # ✅ Single onboarding form link (replaces 3 separate links)
        onboarding_link = f"{API_BASE_URL}/webhook/onboarding-offer?job_id={job_id}&candidate={name}"
        
        subject = f"Job Offer - {job_title} Position"
        email_body = (
            f"Dear {name},\n\n"
            f"We are pleased to offer you the position of {job_title}.\n\n"
            "Offer Details:\n"
            "- Competitive salary package\n"
            "- Comprehensive benefits\n"
            "- Flexible work arrangements\n\n"
            "TO ACCEPT THIS OFFER:\n"
            f"Please complete the onboarding form: {onboarding_link}\n\n"
            "TO REJECT OR NEGOTIATE:\n"
            "You can also use the form to decline or request changes.\n\n"
            "We look forward to your response.\n\n"
            "Best regards,\n"
            "HR Team"
        )
        
        try:
            result = send_email_tool.invoke({
                "recipient_email": candidate_email,
                "subject": subject,
                "body": email_body
            })
            print(f"✅ {result}")
            offers_sent.append(name)
        except Exception as e:
            print(f"❌ Failed to send offer to {name}: {e}")

    print(f"\n--- Offers sent to {len(offers_sent)} candidates ---")
    
    # Save state
    from db import save_state
    save_state(job_id, {
        "offers_sent": offers_sent,
        "offer_responses": [],
        "job_description": state["job_description"],
        "screened_candidates": state["screened_candidates"]
    })

    return {
        "offers_sent": offers_sent,
        "offer_responses": []
    }

def wait_for_offer_responses(state: GraphState):
    """Pause workflow until all candidates respond."""
    offers_sent = state.get("offers_sent", [])
    offer_responses = state.get("offer_responses", [])
    
    responded_candidates = [r['candidate'] for r in offer_responses]
    pending_candidates = [name for name in offers_sent if name not in responded_candidates]
    
    if pending_candidates:
        print(f"\n⏸️  WORKFLOW PAUSED")
        print(f"{'='*70}")
        print(f"Waiting for {len(pending_candidates)} candidate(s) to respond:")
        for name in pending_candidates:
            print(f"  ⏳ {name}")
        print(f"{'='*70}\n")
        
        # ✅ This keeps the workflow paused until webhook resumes it
        raise NodeInterrupt(
            f"Waiting for {len(pending_candidates)} candidates to respond"
        )
    
    # All responded - don't interrupt, just continue
    print("✅ All candidates have responded! Proceeding to route_final_decision...")
    return {}

def process_offer_reply(state: GraphState):
    """Process a single candidate's offer reply."""
    reply_data = state.get("offer_reply")
    
    if not reply_data:
        print("⏸️ No new offer reply - workflow is waiting")
        return {}
    
    candidate_name = reply_data['candidate']
    status = reply_data['status']
    
    print(f"\n{'='*70}")
    print(f"📬 OFFER RESPONSE RECEIVED")
    print(f"{'='*70}")
    print(f"Candidate: {candidate_name}")
    print(f"Response: {status}")
    
    # 🔍 Check if this is an acceptance with onboarding data
    if status == "Accepted" and state.get("onboarding_submission"):
        onboarding_data = state["onboarding_submission"]
        if onboarding_data.get("candidate") == candidate_name:
            print(f"✅ ONBOARDING DATA RECEIVED:")
            print(f"   Joining Date: {onboarding_data.get('joining_date')}")
            print(f"   Comments: {onboarding_data.get('comments', 'None')}")
    
    print(f"{'='*70}\n")
    
    # Get current responses
    offer_responses = state.get("offer_responses", [])
    
    # Check for duplicates
    if any(r['candidate'] == candidate_name for r in offer_responses):
        print(f"⚠️  Duplicate response from {candidate_name} - ignoring")
        return {}
    
    # Add new response with full data
    response_entry = {
        "candidate": candidate_name,
        "status": status
    }
    
    # Include additional data for negotiation
    if status == "Negotiation":
        response_entry["salary_expectation"] = reply_data.get("salary_expectation")
        response_entry["comments"] = reply_data.get("comments")
    elif status == "Rejected":
        response_entry["comments"] = reply_data.get("comments")
    
    offer_responses.append(response_entry)
    
    # Show progress
    offers_sent = state.get("offers_sent", [])
    print(f"📊 Progress: {len(offer_responses)}/{len(offers_sent)} responses received")
    
    # ✅ For acceptances, also store in onboarding_submissions list
    if status == "Accepted":
        onboarding_submissions = state.get("onboarding_submissions", [])
        onboarding_data = state.get("onboarding_submission")
        
        if onboarding_data and onboarding_data.get("candidate") == candidate_name:
            # Check if not already in list
            if not any(s['candidate'] == candidate_name for s in onboarding_submissions):
                onboarding_submissions.append(onboarding_data)
                print(f"✅ Added {candidate_name} to onboarding_submissions list")
    
    # Clear the offer_reply so it doesn't get processed again
    return {
        "offer_responses": offer_responses,
        "offer_reply": None,
        "onboarding_submissions": onboarding_submissions if status == "Accepted" else state.get("onboarding_submissions", []),
        "last_offer_reply": status
    }

def route_offer_reply(state: GraphState):
    """Route based on final responses."""
    offer_responses = state.get("offer_responses", [])
    
    # Check if ANY candidate accepted
    acceptances = [r for r in offer_responses if r['status'] == 'Accepted']
    
    if acceptances:
        print(f"\n🎉 {len(acceptances)} candidate(s) accepted!")
        for acc in acceptances:
            print(f"   ✅ {acc['candidate']}")
        return "process_acceptances"
    else:
        print("❌ No acceptances received")
        return "all_rejected"

def process_all_acceptances(state: GraphState):
    """Process onboarding for accepted candidates - data already collected."""
    print("--- PROCESSING ACCEPTANCES ---")
    
    offer_responses = state.get("offer_responses", [])
    acceptances = [r for r in offer_responses if r['status'] == 'Accepted']
    
    print(f"🎊 Processing {len(acceptances)} new hire(s)")
    
    # ✅ Build a lookup of all onboarding submissions
    all_submissions = state.get("onboarding_submissions", [])
    single_submission = state.get("onboarding_submission")
    if single_submission:
        candidate_name = single_submission.get('candidate')
        if candidate_name and not any(s.get('candidate') == candidate_name for s in all_submissions):
            all_submissions.append(single_submission)
            print(f"📋 Added {candidate_name} from single submission field")
    
    submissions_by_candidate = {s['candidate']: s for s in all_submissions}
    
    print(f"📋 Available onboarding data for: {list(submissions_by_candidate.keys())}")
    print(f"📋 Acceptances to process: {[a['candidate'] for a in acceptances]}")
    
    # ✅ FIX: Build email lookup with fuzzy matching support
    screened_candidates = state.get("screened_candidates", [])
    
    # Create both exact match and fuzzy match lookups
    candidate_emails = {}
    candidate_name_variations = {}  # Maps short name -> full name
    
    for c in screened_candidates:
        full_name = c['name']
        email = c.get('email')
        if email:
            # Exact match
            candidate_emails[full_name] = email
            
            # Also add first name only for fuzzy matching
            first_name = full_name.split()[0] if full_name else ""
            if first_name:
                candidate_name_variations[first_name] = full_name
    
    print(f"📧 Email lookup built for: {list(candidate_emails.keys())}")
    print(f"🔍 Name variations: {candidate_name_variations}")
    
    confirmations_sent = []
    
    for acceptance in acceptances:
        candidate_name = acceptance['candidate']
        candidate_onboarding = submissions_by_candidate.get(candidate_name)
        
        # ✅ Try exact match first, then fuzzy match
        candidate_email = candidate_emails.get(candidate_name)
        
        if not candidate_email and candidate_name in candidate_name_variations:
            # Try fuzzy match using first name
            full_name = candidate_name_variations[candidate_name]
            candidate_email = candidate_emails.get(full_name)
            print(f"🔍 Fuzzy matched '{candidate_name}' -> '{full_name}'")
        
        if not candidate_email:
            print(f"⚠️ No email address found for {candidate_name} - skipping confirmation")
            print(f"   Available names: {list(candidate_emails.keys())}")
            continue
        
        # ✅ Rest of the code stays the same
        if candidate_onboarding:
            joining_date = candidate_onboarding.get('joining_date', 'TBD')
            comments = candidate_onboarding.get('comments', '')
            print(f"✅ Found onboarding data for {candidate_name}")
        else:
            joining_date = "To be confirmed"
            comments = ""
            print(f"⚠️ No onboarding data for {candidate_name}, sending basic confirmation")
        
        subject = f"Welcome Aboard! Start Date: {joining_date}"
        
        body = (
            f"Dear {candidate_name},\n\n"
            f"Congratulations! We're excited to confirm your acceptance.\n\n"
            f"YOUR START DATE: {joining_date}\n\n"
            f"NEXT STEPS:\n"
            f"- You'll receive laptop and access credentials on Day 1\n"
            f"- Your manager will contact you before your start date\n"
            f"- Please arrive at 9:00 AM for orientation\n\n"
        )
        
        if comments:
            body += f"YOUR COMMENTS:\n{comments}\n\n"
        
        body += (
            f"If you have any questions, please reach out.\n\n"
            f"Welcome to the team!\n\n"
            f"Best regards,\nHR Team"
        )
        
        try:
            from tools.send_email_tool import send_email_tool
            send_email_tool.invoke({
                "recipient_email": candidate_email,
                "subject": subject,
                "body": body
            })
            print(f"✅ Confirmation sent to {candidate_name} at {candidate_email}")
            confirmations_sent.append(candidate_name)
        except Exception as e:
            print(f"❌ Failed to send confirmation to {candidate_name}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print(f"🎉 HIRING PROCESS COMPLETE!")
    print(f"{'='*70}")
    print(f"Confirmations sent to: {confirmations_sent}")
    print(f"{'='*70}\n")
    
    return {
        "hiring_status": "complete",
        "confirmations_sent": confirmations_sent
    }

def wait_for_onboarding_submissions(state: GraphState):
    """Pause workflow until candidates submit onboarding forms."""
    onboarding_sent = state.get("onboarding_forms_sent", [])
    onboarding_submissions = state.get("onboarding_submissions", [])
    
    submitted_candidates = [s['candidate'] for s in onboarding_submissions]
    pending_candidates = [name for name in onboarding_sent if name not in submitted_candidates]
    
    if pending_candidates:
        print(f"\n⏸️  WAITING FOR ONBOARDING SUBMISSIONS")
        print(f"{'='*70}")
        print(f"Waiting for {len(pending_candidates)} candidate(s) to submit:")
        for name in pending_candidates:
            print(f"  ⏳ {name}")
        print(f"{'='*70}\n")
        
        raise NodeInterrupt(
            f"Waiting for {len(pending_candidates)} candidates to submit onboarding info"
        )
    
    print("✅ All candidates have submitted onboarding info!")
    return {}

def process_onboarding_submission(state: GraphState):
    """Process a single candidate's onboarding submission."""
    submission_data = state.get("onboarding_submission")
    
    if not submission_data:
        print("⏸️ No new submission - workflow is waiting")
        return {}
    
    candidate_name = submission_data['candidate']
    joining_date = submission_data['joining_date']
    
    print(f"\n{'='*70}")
    print(f"📋 ONBOARDING SUBMISSION RECEIVED")
    print(f"{'='*70}")
    print(f"Candidate: {candidate_name}")
    print(f"Joining Date: {joining_date}")
    print(f"{'='*70}\n")
    
    # Get current submissions
    onboarding_submissions = state.get("onboarding_submissions", [])
    
    # Check for duplicates
    if any(s['candidate'] == candidate_name for s in onboarding_submissions):
        print(f"⚠️  Duplicate submission from {candidate_name} - ignoring")
        return {}
    
    # Add new submission
    onboarding_submissions.append({
        "candidate": candidate_name,
        "joining_date": joining_date
    })
    
    print(f"✅ Onboarding info recorded for {candidate_name}")
    
    return {
        "onboarding_submissions": onboarding_submissions,
        "onboarding_submission": None
    }

def send_final_confirmations(state: GraphState):
    """Send final confirmation emails with joining details."""
    print("--- SENDING FINAL CONFIRMATIONS ---")
    
    onboarding_submissions = state.get("onboarding_submissions", [])
    
    candidate_emails = {
        "Alice Johnson": "ayaanahmadbs@gmail.com",
        "Bob Smith": "imaffan99@gmail.com",
    }
    
    for submission in onboarding_submissions:
        candidate_name = submission['candidate']
        joining_date = submission['joining_date']
        
        if candidate_name in candidate_emails:
            candidate_email = candidate_emails[candidate_name]
            
            subject = f"Your Start Date Confirmed - {joining_date}"
            email_body = (
                f"Dear {candidate_name},\n\n"
                f"Thank you for completing your onboarding information!\n\n"
                f"Your start date is confirmed for: {joining_date}\n\n"
                f"WHAT TO EXPECT:\n"
                f"- You'll receive your laptop and access credentials on Day 1\n"
                f"- Your manager will be in touch before your start date\n"
                f"- Please arrive at 9:00 AM for orientation\n\n"
                f"If you have any questions, feel free to reach out.\n\n"
                f"We're excited to have you on the team!\n\n"
                f"Best regards,\n"
                f"HR Team"
            )
            
            try:
                result = send_email_tool.invoke({
                    "recipient_email": candidate_email,
                    "subject": subject,
                    "body": email_body
                })
                print(f"✅ {result}")
            except Exception as e:
                print(f"❌ Failed to send confirmation to {candidate_name}: {e}")
    
    print("🎉 HIRING PROCESS COMPLETE!")
    return {"hiring_status": "complete"}

def handle_all_rejections(state: GraphState):
    """Handle no acceptances."""
    print("--- ALL OFFERS REJECTED/DECLINED ---")
    print("❌ No candidates accepted the offer.")
    print("💡 Consider reviewing compensation package or re-recruiting.")
    return {"error": "All candidates rejected offer"}

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

def build_graph():
    """Build the complete workflow graph."""
    conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    
    # Pass the connection to the SqliteSaver constructor
    memory = SqliteSaver(conn=conn)
    workflow = StateGraph(GraphState)

    # ✅ Add ALL nodes FIRST (including onboarding nodes)
    workflow.add_node("job_analyst", run_job_analyst)
    workflow.add_node("human_approval", get_human_approval)
    workflow.add_node("post_job", post_job_description)
    workflow.add_node("candidate_sourcer", run_candidate_sourcer)
    workflow.add_node("resume_screener", run_resume_screener)
    workflow.add_node("interview_scheduler", run_interview_scheduler)
    workflow.add_node("interviewer", run_interviewer)
    workflow.add_node("decision_maker", run_decision_maker)
    workflow.add_node("final_offer_approval", get_final_offer_approval)
    workflow.add_node("send_offers", send_offers)
    workflow.add_node("wait_for_offer_responses", wait_for_offer_responses)
    workflow.add_node("process_offer_reply", process_offer_reply)
    workflow.add_node("route_final_decision", lambda state: {})
    workflow.add_node("process_all_acceptances", process_all_acceptances)
    workflow.add_node("handle_all_rejections", handle_all_rejections)
    
    # ✅ ONBOARDING NODES (ADDED)
    workflow.add_node("wait_for_onboarding_submissions", wait_for_onboarding_submissions)
    workflow.add_node("process_onboarding_submission", process_onboarding_submission)
    workflow.add_node("send_final_confirmations", send_final_confirmations)

    # Set entry point
    workflow.set_entry_point("job_analyst")

    # Early stage edges (unchanged)
    workflow.add_edge("job_analyst", "human_approval")
    workflow.add_conditional_edges(
        "human_approval",
        lambda state: "continue" if not state.get("error") else "end",
        {"continue": "post_job", "end": END}
    )
    workflow.add_edge("post_job", "candidate_sourcer")
    workflow.add_edge("candidate_sourcer", "resume_screener")
    workflow.add_conditional_edges(
        "resume_screener",
        lambda state: "end" if state.get("error") or not state.get("screened_candidates") else "continue",
        {"continue": "interview_scheduler", "end": END}
    )
    workflow.add_edge("interview_scheduler", "interviewer")
    workflow.add_edge("interviewer", "decision_maker")
    workflow.add_edge("decision_maker", "final_offer_approval")
    workflow.add_conditional_edges(
        "final_offer_approval",
        lambda state: "continue" if not state.get("error") else "end",
        {"continue": "send_offers", "end": END}
    )

    # Offer handling flow
    workflow.add_edge("send_offers", "wait_for_offer_responses")
    workflow.add_edge("wait_for_offer_responses", "process_offer_reply")
    
    workflow.add_conditional_edges(
        "process_offer_reply",
        lambda state: "check_more" if len(state.get("offer_responses", [])) < len(state.get("offers_sent", [])) else "all_done",
        {
            "check_more": "wait_for_offer_responses",
            "all_done": "route_final_decision"
        }
    )
    
    workflow.add_conditional_edges(
        "route_final_decision",
        route_offer_reply,
        {
            "process_acceptances": "process_all_acceptances",
            "all_rejected": "handle_all_rejections",
        }
    )

    # ✅ ONBOARDING FLOW (now works because nodes are defined above)
    workflow.add_edge("process_all_acceptances", END)

    # Compile with memory
    app = workflow.compile(checkpointer=memory)
    return app

if __name__ == "__main__":
    app = build_graph()

    initial_input = {
        "initial_request": "We need to hire a senior python developer."
    }
    config = {"configurable": {"thread_id": "test-123"}}
    
    for event in app.stream(initial_input, config):
        for key, value in event.items():
            print(f"Node '{key}' output:")
            print(value)
        print("\n" + "="*30 + "\n")