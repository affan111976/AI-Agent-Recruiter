from langchain_core.tools import tool
import requests
import os

@tool
def post_to_linkedin_tool(job_description: dict) -> str:
    """
    Posts a job description to LinkedIn using its API.
    Requires a valid OAuth 2.0 access token with the necessary permissions.
    """
    # LinkedIn API endpoint for posting jobs.
    post_url = "https://api.linkedin.com/v2/jobs"

    # The access token is retrieved from environment variables.
    access_token = os.getenv("LINKEDIN_API_TOKEN")
    if not access_token:
        return "Error: LINKEDIN_API_TOKEN not found in environment variables."

    # The 'urn:li:person:{id}' of the person posting the job.
    # This would typically be retrieved after the user authenticates.
    author_urn = os.getenv("LINKEDIN_AUTHOR_URN")
    if not author_urn:
        return "Error: LINKEDIN_AUTHOR_URN not found in environment variables."

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }

    # Transform the job_description dict into the format required by the LinkedIn API.
    # This is a simplified example payload. Refer to LinkedIn's documentation for all fields.
    payload = {
        "company": f"urn:li:organization:{os.getenv('LINKEDIN_COMPANY_ID')}", # Your company's LinkedIn URN
        "title": job_description.get("title", "N/A"),
        "description": {
            "text": "<h3>Responsibilities:</h3><ul>" + "".join([f"<li>{resp}</li>" for resp in job_description.get("responsibilities", [])]) + "</ul>" \
                    + "<h3>Qualifications:</h3><ul>" + "".join([f"<li>{qual}</li>" for qual in job_description.get("qualifications", [])]) + "</ul>"
        },
        "onboardingInfo": {
            "applicationMethods": {
                "email": "careers@yourcompany.com" 
            }
        },
        "employmentStatus": "FULL_TIME", 
        "externalJobPosting": {
            "externalId": f"job-{os.urandom(6).hex()}",
            "postingUrl": "https://careers.yourcompany.com/job/123" 
        },
        "listedAt": 1672531200000, 
        "poster": author_urn,
        "location": "Roorkee, Uttarakhand, India" 
    }

    try:
        # In a real application, you would uncomment these lines to make the actual API call.
        # response = requests.post(post_url, headers=headers, json=payload)
        # response.raise_for_status()
        
        # We are simulating the successful post for this example.
        print(f"--- (SIMULATED) POSTING JOB TO LINKEDIN: {payload['title']} ---")
        return "Job posted successfully to LinkedIn."
    except requests.exceptions.RequestException as e:
        return f"Failed to post job to LinkedIn: {e}"