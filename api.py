from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from graph import build_graph
from db import load_state, save_state
from typing import Optional
import uuid

app = FastAPI(
    title="HR Agent Webhook API",
    description="Webhook endpoints for the Advanced HR Agent workflow",
    version="1.0.0"
)

# Build the graph once at startup
graph_app = build_graph()


# Request models for validation
class InterviewReplyRequest(BaseModel):
    job_id: str
    candidate_name: str
    scheduled_time: Optional[str] = None


class OfferReplyRequest(BaseModel):
    job_id: str
    candidate_name: str
    reply: str  # "Accepted", "Rejected", or "Negotiation"


class OnboardingReplyRequest(BaseModel):
    job_id: str
    candidate_name: str
    joining_date: str
    documents_uploaded: Optional[bool] = False


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "HR Agent Webhook API",
        "version": "1.0.0"
    }


@app.post("/webhook/interview-reply")
async def handle_interview_reply(payload: InterviewReplyRequest):
    """
    Webhook endpoint for when a candidate confirms their interview via a scheduling link.
    
    This is called when:
    - Candidate clicks the scheduling link in their email
    - Candidate selects a time slot on the scheduling platform (e.g., Calendly)
    - The scheduling platform sends a webhook to this endpoint
    
    Args:
        payload: Interview confirmation data including job_id and candidate_name
        
    Returns:
        Success message with status
    """
    job_id = payload.job_id
    candidate_name = payload.candidate_name
    
    print(f"Received interview confirmation for {candidate_name} for job {job_id}")

    try:
        # Load the workflow configuration
        config = {"configurable": {"thread_id": job_id}}
        
        # Prepare input data with the confirmation
        input_data = {
            "interview_confirmation": {
                "candidate": candidate_name,
                "scheduled_time": payload.scheduled_time
            }
        }
        
        # Resume the graph from where it left off
        # The workflow should be at the "process_interview_confirmation" node
        for event in graph_app.stream(input_data, config):
            print(f"Processed node: {list(event.keys())}")
        
        return {
            "status": "success",
            "message": f"Interview confirmation processed for {candidate_name}",
            "job_id": job_id
        }
    
    except Exception as e:
        print(f"Error processing interview confirmation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process interview confirmation: {str(e)}"
        )


@app.post("/webhook/offer-reply")
async def handle_offer_reply(payload: OfferReplyRequest):
    """
    Webhook endpoint for when a candidate replies to an offer email.
    
    This is called when:
    - Candidate clicks "Accept", "Reject", or "Negotiate" in their offer email
    - The link redirects to a form that submits to this endpoint
    
    Args:
        payload: Offer reply data including job_id, candidate_name, and reply status
        
    Returns:
        Success message with status
    """
    job_id = payload.job_id
    candidate_name = payload.candidate_name
    reply = payload.reply

    # Validate reply status
    valid_replies = ["Accepted", "Rejected", "Negotiation"]
    if reply not in valid_replies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reply status. Must be one of: {', '.join(valid_replies)}"
        )

    print(f"Received offer reply from {candidate_name}: {reply}")

    try:
        # Load the workflow configuration
        config = {"configurable": {"thread_id": job_id}}
        
        # Prepare input data with the candidate's reply
        input_data = {
            "offer_reply": {
                "candidate": candidate_name,
                "status": reply
            }
        }
        
        # Resume the graph, feeding in the reply
        # The workflow should be at the "process_offer_reply" node
        for event in graph_app.stream(input_data, config):
            print(f"Processed node: {list(event.keys())}")

        return {
            "status": "success",
            "message": f"Offer reply '{reply}' processed for {candidate_name}",
            "job_id": job_id
        }
    
    except Exception as e:
        print(f"Error processing offer reply: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process offer reply: {str(e)}"
        )


@app.post("/webhook/onboarding-reply")
async def handle_onboarding_reply(payload: OnboardingReplyRequest):
    """
    Webhook endpoint for when a candidate submits their joining date and documents.
    
    This is called when:
    - Candidate fills out the onboarding form with their joining date
    - Candidate uploads required documents
    - The form submission triggers this webhook
    
    Args:
        payload: Onboarding data including job_id, candidate_name, and joining_date
        
    Returns:
        Success message with status
    """
    job_id = payload.job_id
    candidate_name = payload.candidate_name
    joining_date = payload.joining_date

    print(f"Received onboarding info from {candidate_name}: Joining on {joining_date}")

    try:
        # Load the workflow configuration
        config = {"configurable": {"thread_id": job_id}}
        
        # Prepare input data with the onboarding information
        input_data = {
            "onboarding_info": {
                "candidate": candidate_name,
                "joining_date": joining_date,
                "documents_uploaded": payload.documents_uploaded
            }
        }
        
        # Resume the graph, feeding in the new information
        # The workflow should be at the "finalize_onboarding" node
        for event in graph_app.stream(input_data, config):
            print(f"Processed node: {list(event.keys())}")

        return {
            "status": "success",
            "message": f"Onboarding information received for {candidate_name}",
            "job_id": job_id,
            "joining_date": joining_date
        }
    
    except Exception as e:
        print(f"Error processing onboarding info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process onboarding information: {str(e)}"
        )


@app.get("/workflow/status/{job_id}")
async def get_workflow_status(job_id: str):
    """
    Get the current status of a workflow.
    
    Args:
        job_id: The unique identifier for the job/workflow
        
    Returns:
        Current state of the workflow
    """
    try:
        state = load_state(job_id)
        
        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow with job_id '{job_id}' not found"
            )
        
        return {
            "status": "success",
            "job_id": job_id,
            "workflow_state": state
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve workflow status: {str(e)}"
        )


# To run the API server:
# uvicorn api:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
