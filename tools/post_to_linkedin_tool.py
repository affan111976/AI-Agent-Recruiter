from langchain_core.tools import tool
import requests
import os
from datetime import datetime

@tool
def post_to_linkedin_tool(job_description: dict) -> str:
    """
    Posts a job description to LinkedIn with an embedded application form.
    Returns the job posting URL where candidates can apply.
    """
    
    # STEP 1: Get LinkedIn API credentials
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    company_id = os.getenv("LINKEDIN_COMPANY_ID")  # Your company's LinkedIn ID
    
    if not access_token or not company_id:
        return "Error: LinkedIn credentials missing. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_COMPANY_ID"
    
    # STEP 2: LinkedIn Job Posting API endpoint
    post_url = "https://api.linkedin.com/rest/jobs"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": "202304",  # Use current API version
        "X-RestLi-Protocol-Version": "2.0.0"
    }
    
    # STEP 3: Create application form URL
    # This will be YOUR webhook endpoint that receives applications
    from config import API_BASE_URL
    application_webhook = f"{API_BASE_URL}/webhook/job-application"
    
    # STEP 4: Build the job posting payload
    payload = {
        "company": f"urn:li:organization:{company_id}",
        "title": job_description.get("title", "Position Available"),
        "description": format_job_description(job_description),
        "location": {
            "country": "IN",
            "city": "Roorkee",
            "postalCode": "247667"
        },
        "employmentStatus": "FULL_TIME",
        "jobFunctions": ["INFORMATION_TECHNOLOGY"],
        "industries": ["COMPUTER_SOFTWARE"],
        "applyMethod": {
            "companyApplyUrl": application_webhook  # ✅ Your form URL
        },
        "listedAt": int(datetime.now().timestamp() * 1000),
        "expireAt": int((datetime.now().timestamp() + 30*24*60*60) * 1000)  # 30 days
    }
    
    # STEP 5: Post to LinkedIn
    try:
        response = requests.post(post_url, headers=headers, json=payload)
        response.raise_for_status()
        
        job_data = response.json()
        job_id = job_data.get("id")
        job_url = f"https://www.linkedin.com/jobs/view/{job_id}"
        
        print(f"✅ Job posted to LinkedIn successfully!")
        print(f"📍 Job URL: {job_url}")
        print(f"📝 Application Form: {application_webhook}")
        
        return f"Job posted successfully! URL: {job_url}"
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to post job: {e}")
        return f"Failed to post job to LinkedIn: {str(e)}"

def format_job_description(job_desc: dict) -> str:
    """Convert job description dict to HTML for LinkedIn."""
    html = f"<h2>{job_desc.get('title', 'N/A')}</h2>"
    html += f"<h3>About {job_desc.get('company', 'Our Company')}</h3>"
    
    html += "<h3>Responsibilities:</h3><ul>"
    for resp in job_desc.get("responsibilities", []):
        html += f"<li>{resp}</li>"
    html += "</ul>"
    
    html += "<h3>Qualifications:</h3><ul>"
    for qual in job_desc.get("qualifications", []):
        html += f"<li>{qual}</li>"
    html += "</ul>"
    
    html += "<h3>What We Offer:</h3><ul>"
    for offer in job_desc.get("offerings", []):
        html += f"<li>{offer}</li>"
    html += "</ul>"
    
    return html