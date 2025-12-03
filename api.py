from fastapi import FastAPI, Request, HTTPException
from fastapi import Form, UploadFile, File
from fastapi.responses import HTMLResponse  # ✅ Import at the top
from pydantic import BaseModel
from graph import build_graph
from typing import Optional
import traceback
import json 
from logging_config import setup_logger
from exceptions import FileProcessingError, ValidationException
from validators import validate_resume_file

# Initialize Logger
logger = setup_logger("API")

app = FastAPI(
    title="HR Agent Webhook API",
    description="Webhook endpoints for the Advanced HR Agent workflow",
    version="1.0.0"
)

# Build the graph once at startup
graph_app = build_graph()

class OfferReplyRequest(BaseModel):
    job_id: str
    candidate_name: str
    reply: str  # "Accepted", "Rejected", or "Negotiation"

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "HR Agent Webhook API",
        "version": "1.0.0"
    }

@app.get("/webhook/job-application")
async def show_application_form(job_id: str):
    """
    Display application form when candidates click 'Apply' on LinkedIn.
    This is the URL LinkedIn redirects to.
    """
    from datetime import datetime
    
    html_form = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Job Application</title>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
                margin: 0;
            }}
            .container {{
                max-width: 700px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                padding: 40px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            }}
            h1 {{
                color: #333;
                margin-bottom: 30px;
                text-align: center;
            }}
            .form-group {{
                margin-bottom: 20px;
            }}
            label {{
                display: block;
                font-weight: 600;
                margin-bottom: 8px;
                color: #555;
            }}
            input, textarea {{
                width: 100%;
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                box-sizing: border-box;
                transition: border-color 0.3s;
            }}
            input:focus, textarea:focus {{
                outline: none;
                border-color: #667eea;
            }}
            textarea {{
                resize: vertical;
                min-height: 150px;
                font-family: inherit;
            }}
            button {{
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s;
            }}
            button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }}
            .required {{
                color: red;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 Job Application</h1>
            <form action="/webhook/submit-application" method="post" enctype="multipart/form-data">
                <input type="hidden" name="job_id" value="{job_id}">
                
                <div class="form-group">
                    <label>Full Name <span class="required">*</span></label>
                    <input type="text" name="name" required placeholder="John Doe">
                </div>
                
                <div class="form-group">
                    <label>Email Address <span class="required">*</span></label>
                    <input type="email" name="email" required placeholder="john@example.com">
                </div>
                
                <div class="form-group">
                    <label>Phone Number</label>
                    <input type="tel" name="phone" placeholder="+91 98765 43210">
                </div>
                
                <div class="form-group">
                    <label>Resume/CV <span class="required">*</span></label>
                    <input type="file" name="resume" accept=".pdf,.doc,.docx" required>
                    <small style="color: #666;">Accepted formats: PDF, DOC, DOCX (Max 5MB)</small>
                </div>
                
                <div class="form-group">
                    <label>Cover Letter / Why do you want this role?</label>
                    <textarea name="cover_letter" placeholder="Tell us about yourself and why you're interested in this position..."></textarea>
                </div>
                
                <div class="form-group">
                    <label>LinkedIn Profile URL</label>
                    <input type="url" name="linkedin_url" placeholder="https://linkedin.com/in/yourprofile">
                </div>
                
                <button type="submit">Submit Application</button>
            </form>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_form, status_code=200)

@app.post("/webhook/submit-application")
async def submit_application(
    request: Request,
    job_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    cover_letter: str = Form(None),
    linkedin_url: str = Form(None),
    resume: UploadFile = File(...)
):
    """
    Process application submission and add to candidate pool.
    """
    try:
        # STEP 1: Read resume file
        logger.info(f"Processing application for {name}")
        resume_content = await resume.read()
        validate_resume_file(resume.filename, len(resume_content))
        resume_filename = resume.file.filename
        
        # STEP 2: Save resume to storage (or extract text)
        # For now, we'll extract text from PDF
        resume_text = extract_text_from_resume(resume_content, resume_filename)
        
        # STEP 3: Create candidate record
        candidate_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "resume": resume_text,
            "cover_letter": cover_letter,
            "linkedin_url": linkedin_url,
            "applied_at": datetime.now().isoformat()
        }
        
        # STEP 4: Add to workflow state
        config = {"configurable": {"thread_id": job_id}}
        current_state = graph_app.get_state(config)
        
        if not current_state.values:
            # Initialize state if job exists but no state yet
            candidates = [candidate_data]
        else:
            # Add to existing candidates
            candidates = current_state.values.get('candidates', [])
            candidates.append(candidate_data)
        
        # Update state
        graph_app.update_state(
            config,
            {"candidates": candidates},
            as_node="candidate_sourcer"
        )
        
        print(f"✅ New application received from {name} for job {job_id}")
        
        # STEP 5: Send confirmation email
        from tools.send_email_tool import send_email_tool
        send_email_tool.invoke({
            "recipient_email": email,
            "subject": "Application Received",
            "body": f"Dear {name},\n\nThank you for applying! We've received your application and will review it shortly.\n\nBest regards,\nHR Team"
        })
        
        # Success page
        success_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Application Submitted</title>
            <style>
                body {{
                    font-family: Arial;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 50px;
                    border-radius: 15px;
                    text-align: center;
                    max-width: 500px;
                }}
                .success-icon {{
                    font-size: 72px;
                    color: #10b981;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Application Submitted!</h1>
                <p>Thank you, <strong>{name}</strong>!</p>
                <p>We've received your application and will review it within 3-5 business days.</p>
                <p>A confirmation email has been sent to <strong>{email}</strong></p>
            </div>
        </body>
        </html>
        """

        logger.info(f"Application successfully processed for {name}")
        return HTMLResponse(content=success_html, status_code=200)

    except ValidationException as ve:
        logger.warning(f"Validation failed: {ve}")
        return HTMLResponse(content=f"<h1>Invalid Input</h1><p>{str(ve)}</p>", status_code=400)

    except Exception as e:
        logger.error(f"Critical error processing application: {e}", exc_info=True)
        return HTMLResponse(content=f"<h1>Error</h1><p>{str(e)}</p>", status_code=500)

def extract_text_from_resume(file_content: bytes, filename: str) -> str:
    """
    Extract text from resume file (PDF, DOC, DOCX).
    """
    try:
        if filename.endswith('.pdf'):
            # Use PyPDF2 or pdfplumber
            import io
            from PyPDF2 import PdfReader
            
            pdf_file = io.BytesIO(file_content)
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
            
        elif filename.endswith('.docx'):
            # Use python-docx
            import io
            from docx import Document
            
            doc_file = io.BytesIO(file_content)
            doc = Document(doc_file)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
            
        else:
            return "Resume text extraction not supported for this format"
            
    except Exception as e:
        print(f"Error extracting resume text: {e}")
        return f"Resume uploaded: {filename} (text extraction failed)"

@app.get("/webhook/offer-reply")
async def handle_offer_reply_get(
    job_id: str,
    candidate: str,
    reply: str
):
    """
    GET endpoint for email links.
    This handles when candidates click the links in their email.
    """
    # Validate reply
    valid_replies = ["Accepted", "Rejected", "Negotiation"]
    if reply not in valid_replies:
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Invalid Response</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: #fee;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ Invalid Response</h1>
                <p>Reply must be one of: {', '.join(valid_replies)}</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)
    
    print(f"\n{'='*70}")
    print(f"📧 EMAIL LINK CLICKED: {candidate} - {reply}")
    print(f"{'='*70}")
    print(f"Job ID: {job_id}")
    print(f"Candidate: {candidate}")
    print(f"Response: {reply}")
    print(f"{'='*70}\n")
    
    try:
        config = {"configurable": {"thread_id": job_id}}
        
        # ✅ Get current state to see what's actually stored
        current_state = graph_app.get_state(config)
        
        print(f"\n📊 Current State Debug:")
        print(f"  Next nodes: {current_state.next}")
        print(f"  Has values: {bool(current_state.values)}")
        print(f"  State keys: {list(current_state.values.keys()) if current_state.values else 'None'}")
        print(f"  Offers sent: {current_state.values.get('offers_sent', 'N/A')}")
        print(f"  Offer responses: {current_state.values.get('offer_responses', 'N/A')}")
        
        # Check if this is a valid workflow
        if not current_state.values:
            print(f"⚠️ State not found in memory for {job_id}. Attempting to restore from DB...")
            from db import load_state
            saved_state = load_state(job_id)
            if saved_state:
                print(f"✅ Restoring state from database...")
                graph_app.update_state(config, saved_state)
                current_state = graph_app.get_state(config)
            else:
                raise Exception(f"No workflow found for job_id: {job_id}")

        if 'offers_sent' not in current_state.values:
            raise Exception(f"Invalid workflow state - no offers have been sent yet for job_id: {job_id}")
        
        # Update state with offer reply
        print(f"\n✅ Updating state with reply from {candidate}: {reply}")
        graph_app.update_state(
            config,
            {
                "offer_reply": {
                    "candidate": candidate,
                    "status": reply
                }
            },
            as_node="wait_for_offer_responses"  # ✅ Resume from this specific node
        )
        
        # Resume the graph
        print("Resuming workflow from wait_for_offer_responses node...")
        for event in graph_app.stream(None, config):
            if isinstance(event, dict):
                print(f"  Processed: {list(event.keys())}")
        
        # Get final state
        final_state = graph_app.get_state(config)
        offers_sent = final_state.values.get('offers_sent', [])
        offer_responses = final_state.values.get('offer_responses', [])
        
        # Return HTML response
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Response Recorded</title>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
                    text-align: center;
                    max-width: 500px;
                }}
                .success {{
                    color: #10b981;
                    font-size: 48px;
                    margin-bottom: 20px;
                }}
                h1 {{
                    color: #1f2937;
                    margin-bottom: 10px;
                }}
                p {{
                    color: #6b7280;
                    font-size: 16px;
                    line-height: 1.6;
                }}
                .status {{
                    background: #f3f4f6;
                    padding: 15px;
                    border-radius: 5px;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✓</div>
                <h1>Thank You, {candidate}!</h1>
                <p>Your response "<strong>{reply}</strong>" has been recorded successfully.</p>
                <div class="status">
                    <p><strong>Status:</strong> {len(offer_responses)}/{len(offers_sent)} candidates have responded</p>
                </div>
                <p style="margin-top: 20px; font-size: 14px; color: #9ca3af;">
                    You can close this window now. Our HR team will be in touch shortly.
                </p>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(traceback.format_exc())
        
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: #fee;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    text-align: center;
                }}
                .error {{
                    color: #dc2626;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="error">❌ Error Processing Response</h1>
                <p>We encountered an error processing your response.</p>
                <p style="font-size: 12px; color: #6b7280; margin-top: 20px;">
                    Error: {str(e)[:100]}
                </p>
                <p style="font-size: 12px; color: #6b7280;">
                    Please contact HR directly or try again later.
                </p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)

@app.post("/webhook/offer-reply")
async def handle_offer_reply_post(payload: OfferReplyRequest):
    """
    POST endpoint for programmatic webhook calls.
    This resumes the paused workflow with the candidate's response.
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

    print(f"\n{'='*70}")
    print(f"📨 WEBHOOK RECEIVED: Offer reply from {candidate_name}")
    print(f"{'='*70}")
    print(f"Job ID: {job_id}")
    print(f"Candidate: {candidate_name}")
    print(f"Response: {reply}")
    print(f"{'='*70}\n")

    try:
        # Configure with the same thread_id
        config = {"configurable": {"thread_id": job_id}}
        
        # Get current state first to see where we are
        current_state = graph_app.get_state(config)
        print(f"Current workflow state: {current_state}")
        
        print(f"\n✅ Updating state with reply from {candidate}: {reply}")
        graph_app.update_state(
            config,
            {
                "offer_reply": {
                    "candidate": candidate_name,
                    "status": reply
                }
            },
            as_node="process_offer_reply" 
        )
        
        # Resume execution
        print("Resuming workflow with offer reply data...")
        for event in graph_app.stream(None, config):
            if isinstance(event, dict):
                print(f"  Processed: {list(event.keys())}")
                
        # Check final state
        final_state = graph_app.get_state(config)
        offers_sent = final_state.values.get('offers_sent', [])
        offer_responses = final_state.values.get('offer_responses', [])
        
        return {
            "status": "success",
            "message": f"Offer reply '{reply}' processed for {candidate_name}",
            "job_id": job_id,
            "workflow_state": "resumed",
            "offers_sent": len(offers_sent),
            "responses_received": len(offer_responses),
            "all_responded": len(offer_responses) >= len(offers_sent)
        }
    
    except Exception as e:
        print(f"❌ Error processing offer reply: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process offer reply: {str(e)}"
        )

@app.get("/workflow/status/{job_id}")
async def get_workflow_status(job_id: str):
    """Get the current status of a workflow."""
    try:
        config = {"configurable": {"thread_id": job_id}}
        state = graph_app.get_state(config)
        
        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow with job_id '{job_id}' not found"
            )
        
        return {
            "status": "success",
            "job_id": job_id,
            "workflow_state": state.values,
            "next_node": state.next,
            "metadata": state.metadata
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve workflow status: {str(e)}"
        )

@app.get("/webhook/onboarding")
async def handle_onboarding_submission(
    job_id: str,
    candidate: str,
    joining_date: str = None
):
    """
    GET endpoint for onboarding form submission.
    In production, this would be a proper form with multiple fields.
    """
    from datetime import datetime, timedelta  # ✅ Import here
    
    print(f"\n{'='*70}")
    print(f"📋 ONBOARDING FORM ACCESSED: {candidate}")
    print(f"{'='*70}\n")
    
    # If no joining_date yet, show the form
    if not joining_date:
        html_form = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Onboarding Form</title>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
                    max-width: 500px;
                    width: 100%;
                }}
                h1 {{
                    color: #1f2937;
                    margin-bottom: 20px;
                }}
                label {{
                    display: block;
                    margin-top: 15px;
                    font-weight: bold;
                }}
                input {{
                    width: 100%;
                    padding: 10px;
                    margin-top: 5px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    box-sizing: border-box;
                }}
                button {{
                    width: 100%;
                    padding: 15px;
                    margin-top: 20px;
                    background: #667eea;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 16px;
                    cursor: pointer;
                }}
                button:hover {{
                    background: #5568d3;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Welcome, {candidate}!</h1>
                <p>Please complete your onboarding information below:</p>
                <form method="get">
                    <input type="hidden" name="job_id" value="{job_id}">
                    <input type="hidden" name="candidate" value="{candidate}">
                    
                    <label>Preferred Start Date:</label>
                    <input type="date" name="joining_date" required min="{(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}">
                    
                    <button type="submit">Submit Onboarding Info</button>
                </form>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_form, status_code=200)  # ✅ Return the FORM, not success
    
    # Process the submission (this runs when joining_date IS provided)
    try:
        config = {"configurable": {"thread_id": job_id}}
        current_state = graph_app.get_state(config)
        
        if not current_state.values:
            raise Exception(f"No workflow found for job_id: {job_id}")
        
        # Update state with onboarding submission
        print(f"\n✅ Processing onboarding submission from {candidate}")
        graph_app.update_state(
            config,
            {
                "onboarding_submission": {
                    "candidate": candidate,
                    "joining_date": joining_date
                }
            },
            as_node="wait_for_onboarding_submissions"
        )
        
        # Resume the graph
        print("Resuming workflow...")
        for event in graph_app.stream(None, config):
            if isinstance(event, dict):
                print(f"  Processed: {list(event.keys())}")
        
        # Success page (this is what should be shown AFTER submission)
        success_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Submission Successful</title>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    text-align: center;
                }}
                .success {{
                    color: #10b981;
                    font-size: 48px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✓</div>
                <h1>Thank You, {candidate}!</h1>
                <p>Your onboarding information has been submitted.</p>
                <p><strong>Start Date:</strong> {joining_date}</p>
                <p>You'll receive a confirmation email shortly.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=success_html, status_code=200)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        print(traceback.format_exc())
        return HTMLResponse(content=f"<h1>Error</h1><p>{str(e)}</p>", status_code=500)

# In api.py, replace the /webhook/onboarding-offer endpoint:

@app.get("/webhook/onboarding-offer")
async def handle_onboarding_offer_form(
    job_id: str,
    candidate: str,
    decision: str = None,
    joining_date: str = None,
    salary_expectation: str = None,
    comments: str = None
):
    """
    Combined onboarding form that handles acceptance, rejection, or negotiation.
    """
    from datetime import datetime, timedelta
    
    # If no decision yet, show the form
    if not decision:
        html_form = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Job Offer Response - {candidate}</title>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                }}
                .content {{
                    padding: 40px;
                }}
                .section {{
                    margin-bottom: 30px;
                }}
                .section h2 {{
                    color: #333;
                    font-size: 20px;
                    margin-bottom: 15px;
                    border-bottom: 2px solid #667eea;
                    padding-bottom: 10px;
                }}
                label {{
                    display: block;
                    margin-top: 15px;
                    margin-bottom: 5px;
                    font-weight: 600;
                    color: #555;
                }}
                input, select, textarea {{
                    width: 100%;
                    padding: 12px;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    font-size: 14px;
                    box-sizing: border-box;
                    transition: border-color 0.3s;
                }}
                input:focus, select:focus, textarea:focus {{
                    outline: none;
                    border-color: #667eea;
                }}
                textarea {{
                    resize: vertical;
                    min-height: 100px;
                }}
                .radio-group {{
                    margin: 15px 0;
                }}
                .radio-option {{
                    display: flex;
                    align-items: center;
                    padding: 15px;
                    margin: 10px 0;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    cursor: pointer;
                    transition: all 0.3s;
                }}
                .radio-option:hover {{
                    border-color: #667eea;
                    background: #f8f9ff;
                }}
                .radio-option input[type="radio"] {{
                    width: auto;
                    margin-right: 15px;
                }}
                button {{
                    width: 100%;
                    padding: 15px;
                    margin-top: 30px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 18px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: transform 0.2s;
                }}
                button:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
                }}
                .conditional-field {{
                    display: none;
                    margin-top: 20px;
                    padding: 20px;
                    background: #f8f9ff;
                    border-radius: 8px;
                    border-left: 4px solid #667eea;
                }}
                .offer-details {{
                    background: #f8f9ff;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 30px;
                }}
                .offer-details h3 {{
                    margin-top: 0;
                    color: #667eea;
                }}
                .offer-details ul {{
                    margin: 10px 0;
                    padding-left: 20px;
                }}
                .offer-details li {{
                    margin: 8px 0;
                    color: #555;
                }}
            </style>
            <script>
                function toggleFields() {{
                    const decision = document.querySelector('input[name="decision"]:checked').value;
                    const acceptFields = document.getElementById('accept-fields');
                    const negotiateFields = document.getElementById('negotiate-fields');
                    
                    acceptFields.style.display = 'none';
                    negotiateFields.style.display = 'none';
                    
                    if (decision === 'Accept') {{
                        acceptFields.style.display = 'block';
                    }} else if (decision === 'Negotiate') {{
                        negotiateFields.style.display = 'block';
                    }}
                }}
                
                function validateForm(event) {{
                    const decision = document.querySelector('input[name="decision"]:checked');
                    if (!decision) {{
                        alert('Please select your response to the offer');
                        event.preventDefault();
                        return false;
                    }}
                    
                    if (decision.value === 'Accept') {{
                        const joiningDate = document.querySelector('input[name="joining_date"]').value;
                        if (!joiningDate) {{
                            alert('Please select your preferred joining date');
                            event.preventDefault();
                            return false;
                        }}
                    }}
                    
                    return true;
                }}
            </script>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎊 Job Offer Response</h1>
                    <p>Welcome, {candidate}!</p>
                </div>
                
                <div class="content">
                    <div class="offer-details">
                        <h3>📋 Offer Summary</h3>
                        <ul>
                            <li>💼 Competitive salary package</li>
                            <li>🏥 Comprehensive health benefits</li>
                            <li>🏠 Flexible work arrangements</li>
                            <li>📚 Professional development opportunities</li>
                            <li>🎯 Performance bonuses</li>
                        </ul>
                    </div>
                    
                    <form method="get" onsubmit="return validateForm(event)">
                        <input type="hidden" name="job_id" value="{job_id}">
                        <input type="hidden" name="candidate" value="{candidate}">
                        
                        <div class="section">
                            <h2>Your Response</h2>
                            <div class="radio-group">
                                <label class="radio-option">
                                    <input type="radio" name="decision" value="Accept" onchange="toggleFields()" required>
                                    <div>
                                        <strong>✅ Accept Offer</strong>
                                        <div style="font-size: 13px; color: #666; margin-top: 5px;">
                                            I accept the offer and am ready to join
                                        </div>
                                    </div>
                                </label>
                                
                                <label class="radio-option">
                                    <input type="radio" name="decision" value="Negotiate" onchange="toggleFields()" required>
                                    <div>
                                        <strong>💬 Request Negotiation</strong>
                                        <div style="font-size: 13px; color: #666; margin-top: 5px;">
                                            I'm interested but would like to discuss terms
                                        </div>
                                    </div>
                                </label>
                                
                                <label class="radio-option">
                                    <input type="radio" name="decision" value="Reject" onchange="toggleFields()" required>
                                    <div>
                                        <strong>❌ Decline Offer</strong>
                                        <div style="font-size: 13px; color: #666; margin-top: 5px;">
                                            I'm unable to accept at this time
                                        </div>
                                    </div>
                                </label>
                            </div>
                        </div>
                        
                        <!-- Conditional fields for Accept -->
                        <div id="accept-fields" class="conditional-field">
                            <h3>🎉 Onboarding Information</h3>
                            <label>Preferred Start Date: *</label>
                            <input type="date" name="joining_date" min="{(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}">
                            
                            <label>Additional Comments (Optional):</label>
                            <textarea name="comments" placeholder="Any questions or special requirements..."></textarea>
                        </div>
                        
                        <!-- Conditional fields for Negotiate -->
                        <div id="negotiate-fields" class="conditional-field">
                            <h3>💼 Negotiation Details</h3>
                            <label>Expected Salary (Optional):</label>
                            <input type="text" name="salary_expectation" placeholder="e.g., $120,000">
                            
                            <label>Your Comments/Requests:</label>
                            <textarea name="comments" placeholder="Please describe what you'd like to negotiate..."></textarea>
                        </div>
                        
                        <button type="submit">Submit Response</button>
                    </form>
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_form, status_code=200)
    
    # ✅ PROCESS THE SUBMISSION
    try:
        config = {"configurable": {"thread_id": job_id}}
        
        # Get current state
        current_state = graph_app.get_state(config)
        
        if not current_state.values:
            print(f"⚠️ State not found in memory for {job_id}. Attempting to restore from DB...")
            from db import load_state
            saved_state = load_state(job_id)

            if saved_state:
                print(f"✅ Restoring state from database...")
                graph_app.update_state(config, saved_state)
                current_state = graph_app.get_state(config)
            else:
                raise Exception(f"No workflow found for job_id: {job_id}")
        
        print(f"\n{'='*70}")
        print(f"📋 OFFER RESPONSE RECEIVED VIA FORM")
        print(f"{'='*70}")
        print(f"Job ID: {job_id}")
        print(f"Candidate: {candidate}")
        print(f"Decision: {decision}")
        if joining_date:
            print(f"Joining Date: {joining_date}")
        if salary_expectation:
            print(f"Salary Expectation: {salary_expectation}")
        if comments:
            print(f"Comments: {comments}")
        print(f"{'='*70}\n")
        
        # ✅ CRITICAL FIX: Directly update offer_responses and onboarding_submissions
        # Don't use the intermediate offer_reply field
        
        offers_sent = current_state.values.get('offers_sent', [])
        offer_responses = current_state.values.get('offer_responses', [])
        onboarding_submissions = current_state.values.get('onboarding_submissions', [])
        
        print(f"📊 Current state BEFORE update:")
        print(f"   Offers sent: {offers_sent}")
        print(f"   Responses: {len(offer_responses)}")
        print(f"   Onboarding submissions: {len(onboarding_submissions)}")
        
        # Check if already responded
        if any(r['candidate'] == candidate for r in offer_responses):
            print(f"⚠️  {candidate} already responded - showing cached result")
            # Still show success page
        else:
            # Build the response entry
            if decision == "Accept":
                response_entry = {"candidate": candidate, "status": "Accepted"}
                
                onboarding_entry = {
                    "candidate": candidate,
                    "joining_date": joining_date,
                    "comments": comments if comments else ""
                }
                
                # Add to lists
                offer_responses.append(response_entry)
                onboarding_submissions.append(onboarding_entry)
                
                # ✅ ADD THIS DEBUG OUTPUT
                print(f"\n🔍 DEBUG: Data to be saved:")
                print(f"   offer_responses: {offer_responses}")
                print(f"   onboarding_submissions: {onboarding_submissions}")
                
                # Update the state
                update_payload = {
                    "offer_responses": offer_responses,
                    "onboarding_submissions": onboarding_submissions
                }
                
                print(f"\n📤 UPDATE PAYLOAD:")
                print(json.dumps(update_payload, indent=2))
                
                graph_app.update_state(config, update_payload, as_node="wait_for_offer_responses")
                
                # ✅ VERIFY THE UPDATE WORKED
                verify_state = graph_app.get_state(config)
                print(f"\n✅ STATE AFTER UPDATE:")
                print(f"   offer_responses: {verify_state.values.get('offer_responses')}")
                print(f"   onboarding_submissions: {verify_state.values.get('onboarding_submissions')}")
                
            elif decision == "Negotiate":
                response_entry = {
                    "candidate": candidate,
                    "status": "Negotiation",
                    "salary_expectation": salary_expectation if salary_expectation else "",
                    "comments": comments if comments else ""
                }
                offer_responses.append(response_entry)
                print(f"✅ Added negotiation request: {response_entry}")
                
            else:  # Reject
                response_entry = {
                    "candidate": candidate,
                    "status": "Rejected",
                    "comments": comments if comments else ""
                }
                offer_responses.append(response_entry)
                print(f"✅ Added rejection: {response_entry}")
            
            # ✅ Update the state DIRECTLY - bypass the offer_reply mechanism
            update_payload = {
                "offer_responses": offer_responses,
                "onboarding_submissions": onboarding_submissions
            }
            
            print(f"\n🔄 Updating LangGraph state directly...")
            print(f"   New offer_responses count: {len(offer_responses)}")
            print(f"   New onboarding_submissions count: {len(onboarding_submissions)}")
            
            # Update as if coming FROM wait_for_offer_responses (which set the interrupt)
            graph_app.update_state(
                config,
                update_payload,
                as_node="wait_for_offer_responses"
            )
            
            # ✅ Check if all responses received
            if len(offer_responses) >= len(offers_sent):
                print(f"\n🎉 ALL CANDIDATES RESPONDED! Resuming workflow...")
                
                # Resume the workflow - this should move past the NodeInterrupt
                try:
                    event_count = 0
                    for event in graph_app.stream(None, config, stream_mode="values"):
                        event_count += 1
                        if event_count > 10:  # Safety limit
                            break
                        print(f"   Event {event_count}: {list(event.keys()) if isinstance(event, dict) else 'value update'}")
                    
                    print(f"✅ Workflow resumed - processed {event_count} events")
                except Exception as resume_error:
                    print(f"⚠️  Resume error (may be normal if workflow completed): {resume_error}")
            else:
                print(f"\n⏳ Still waiting for more responses ({len(offer_responses)}/{len(offers_sent)})")
        
        # Get final state for display
        final_state = graph_app.get_state(config)
        final_offer_responses = final_state.values.get('offer_responses', [])
        final_onboarding = final_state.values.get('onboarding_submissions', [])
        
        print(f"\n📊 FINAL STATE:")
        print(f"   Total responses: {len(final_offer_responses)}/{len(offers_sent)}")
        print(f"   Onboarding data: {len(final_onboarding)}")
        print(f"   Next node: {final_state.next}")
        print(f"{'='*70}\n")
        
        # Success page
        if decision == "Accept":
            icon = "🎉"
            message = "Thank you for accepting our offer!"
            details = f"<p><strong>Start Date:</strong> {joining_date}</p><p>You'll receive a confirmation email shortly.</p>"
        elif decision == "Negotiate":
            icon = "💬"
            message = "Your negotiation request has been received"
            details = "<p>Our HR team will review and contact you within 2 business days.</p>"
        else:
            icon = "😢"
            message = "We're sorry to see you decline"
            details = "<p>Thank you for considering our offer. Best wishes in your career!</p>"
        
        success_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Response Submitted</title>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 50px;
                    border-radius: 15px;
                    text-align: center;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    max-width: 500px;
                }}
                .icon {{
                    font-size: 72px;
                    margin-bottom: 20px;
                }}
                h1 {{
                    color: #333;
                    margin-bottom: 20px;
                }}
                p {{
                    color: #666;
                    line-height: 1.6;
                    font-size: 16px;
                }}
                .debug {{
                    margin-top: 30px;
                    padding: 15px;
                    background: #f0f7ff;
                    border-radius: 8px;
                    font-size: 13px;
                    text-align: left;
                    border: 1px solid #d0e7ff;
                }}
                .debug strong {{
                    color: #0066cc;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">{icon}</div>
                <h1>{message}</h1>
                <p><strong>{candidate}</strong></p>
                {details}
                <p style="margin-top: 30px; font-size: 14px; color: #999;">
                    You can close this window now.
                </p>
                <div class="debug">
                    <strong>✅ Response Recorded Successfully</strong><br><br>
                    Job ID: {job_id[:12]}...<br>
                    Your decision: <strong>{decision}</strong><br>
                    Total responses: {len(final_offer_responses)}/{len(offers_sent)}<br>
                    Workflow status: {"✅ All responded - processing" if len(final_offer_responses) >= len(offers_sent) else f"⏳ Waiting for {len(offers_sent) - len(final_offer_responses)} more"}
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=success_html, status_code=200)
        
    except Exception as e:
        print(f"❌ ERROR processing form submission:")
        print(f"   Error: {str(e)}")
        print(traceback.format_exc())
        
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <style>
                body {{
                    font-family: Arial;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    background: #ffe6e6;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    max-width: 600px;
                }}
                .error {{ color: #cc0000; }}
                pre {{
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 5px;
                    overflow-x: auto;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="error">❌ Error Processing Response</h1>
                <p>We encountered an error. Please contact HR directly.</p>
                <p><strong>Error details:</strong></p>
                <pre>{str(e)}</pre>
                <p><strong>Job ID:</strong> {job_id}</p>
                <p><strong>Candidate:</strong> {candidate}</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)

@app.get("/debug/submissions/{job_id}")
async def debug_submissions(job_id: str):
    """Debug endpoint to see all submissions for a job."""
    try:
        config = {"configurable": {"thread_id": job_id}}
        state = graph_app.get_state(config)
        
        if not state.values:
            return HTMLResponse(content="<h1>No workflow found</h1>", status_code=404)
        
        offers_sent = state.values.get('offers_sent', [])
        offer_responses = state.values.get('offer_responses', [])
        onboarding_submission = state.values.get('onboarding_submission')
        onboarding_submissions = state.values.get('onboarding_submissions', [])
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Debug: Submissions for {job_id}</title>
            <style>
                body {{ font-family: Arial; padding: 20px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; }}
                pre {{ background: #f5f5f5; padding: 10px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <h1>📋 Submission Debug Info</h1>
            <p><strong>Job ID:</strong> {job_id}</p>
            
            <div class="section">
                <h2>📤 Offers Sent ({len(offers_sent)})</h2>
                <pre>{json.dumps(offers_sent, indent=2)}</pre>
            </div>
            
            <div class="section">
                <h2>✅ Offer Responses ({len(offer_responses)})</h2>
                <pre>{json.dumps(offer_responses, indent=2)}</pre>
            </div>
            
            <div class="section">
                <h2>📝 Current Onboarding Submission (Single)</h2>
                <pre>{json.dumps(onboarding_submission, indent=2)}</pre>
            </div>
            
            <div class="section">
                <h2>📝 All Onboarding Submissions (List)</h2>
                <pre>{json.dumps(onboarding_submissions, indent=2)}</pre>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html, status_code=200)
    
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error:</h1><p>{str(e)}</p>", status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
