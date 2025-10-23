import os
import requests
from langchain_core.tools import tool
from typing import List, Dict
from state import Candidate 

@tool
def candidate_sourcing_tool(job_id: str) -> List[Candidate]:
    """
    Fetches new candidate applications from the company's ATS (e.g., Greenhouse) for a given job ID.
    
    Currently using simulated dummy data for testing purposes.
    To use real ATS data, uncomment the API integration code below and set GREENHOUSE_API_KEY.
    
    Returns an empty list if no candidates are found or if an error occurs.
    """
    print(f"--- FETCHING NEW APPLICANTS FROM ATS FOR JOB ID: {job_id} ---")

    # ============================================================================
    # DUMMY DATA MODE (DEFAULT) - Using simulated candidates for testing
    # ============================================================================
    print("Using simulated candidate data for testing purposes.")
    dummy_candidates = [
        {
            "name": "Alice Johnson", 
            "resume": "Experienced Python developer with 5+ years of experience. Strong background in web scraping, data analysis, and building REST APIs. Proficient in Django, Flask, and FastAPI. Has worked on multiple e-commerce platforms and data pipeline projects."
        },
        {
            "name": "Bob Smith", 
            "resume": "Full-stack engineer with 4 years of expertise in Django, React, and PostgreSQL. Built scalable web applications serving 100K+ users. Experience with AWS, Docker, and CI/CD pipelines. Strong knowledge of microservices architecture."
        },
        {
            "name": "Priya Sharma", 
            "resume": "Data scientist skilled in machine learning, pandas, and scikit-learn with 3 years of experience. Has developed predictive models and recommendation systems. Proficient in Python, SQL, and data visualization tools like Matplotlib and Plotly."
        },
        {
            "name": "Carlos Rodriguez",
            "resume": "Backend developer with 6 years of experience in Python and Node.js. Expert in API design, database optimization, and system architecture. Has led teams of 5+ developers on enterprise applications."
        },
        {
            "name": "Emily Chen",
            "resume": "Software engineer with 2 years of experience in Python and JavaScript. Recently completed projects in web automation and data processing. Familiar with Django, pandas, and modern web technologies."
        }
    ]
    
    return dummy_candidates

    # ============================================================================
    # REAL ATS INTEGRATION (COMMENTED OUT) - Uncomment to use actual Greenhouse API
    # ============================================================================
    # 
    # api_key = os.getenv("GREENHOUSE_API_KEY")
    # if not api_key:
    #     print("Error: GREENHOUSE_API_KEY not found in environment variables.")
    #     print("Falling back to simulated data...")
    #     return dummy_candidates
    #
    # url = f"https://harvest.greenhouse.io/v1/applications?job_id={job_id}"
    # headers = {
    #     "Authorization": f"Basic {api_key}",
    #     "Content-Type": "application/json",
    # }
    #
    # try:
    #     response = requests.get(url, headers=headers)
    #     response.raise_for_status()
    #     applications_from_api = response.json()
    #     
    #     fetched_candidates = []
    #     for app in applications_from_api:
    #         # Extract candidate information from Greenhouse API response
    #         candidate_info = app.get("candidate", {})
    #         
    #         # we may need to fetch the full resume separately using the candidate's ID
    #         candidate_id = candidate_info.get("id")
    #         resume_url = f"https://harvest.greenhouse.io/v1/candidates/{candidate_id}/resumes"
    #         
    #         candidate_data = {
    #             "name": candidate_info.get("first_name", "") + " " + candidate_info.get("last_name", ""),
    #             "resume": f"Resume for {candidate_info.get('first_name', 'N/A')} {candidate_info.get('last_name', '')}. Content would be fetched from resume endpoint."
    #             # In production, fetch actual resume content:
    #             # "resume": fetch_resume_content(resume_url, headers)
    #         }
    #         fetched_candidates.append(candidate_data)
    #     
    #     if not fetched_candidates:
    #         print("--- No new applicants found in ATS. ---")
    #         return []
    #         
    #     print(f"--- Successfully fetched {len(fetched_candidates)} candidates from ATS. ---")
    #     return fetched_candidates
    #
    # except requests.exceptions.RequestException as e:
    #     print(f"Error: Failed to connect to the ATS API: {e}")
    #     print("Falling back to simulated data...")
    #     return dummy_candidates


# Helper function for fetching resume content (for real implementation)
# def fetch_resume_content(resume_url: str, headers: dict) -> str:
#     """
#     Fetches and parses resume content from Greenhouse API.
#     This is a placeholder - implement based on your ATS structure.
#     """
#     try:
#         response = requests.get(resume_url, headers=headers)
#         response.raise_for_status()
#         resume_data = response.json()
#         # Parse and return resume text content
#         return resume_data.get("content", "Resume content not available")
#     except Exception as e:
#         return f"Error fetching resume: {e}"
