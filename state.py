from typing import TypedDict, List, Optional, Dict

class Candidate(TypedDict):
    """Represents a candidate with their information."""
    name: str
    resume: str

class InterviewResult(TypedDict):
    """Represents the result of an interview."""
    candidate_name: str
    interview_questions: List[str]
    evaluation: str
    recommendation: str

class GraphState(TypedDict):
    """Defines the state schema for the recruitment workflow graph."""
    
    # Initial input
    initial_request: Optional[str]
    
    # Job description stage
    job_description: Optional[str]
    job_id: Optional[str]
    
    # Candidate sourcing stage
    candidates: Optional[List[Candidate]]
    
    # Screening stage
    screened_candidates: Optional[List[Candidate]]
    
    # Interview stage
    confirmed_candidates: Optional[List[Candidate]]
    interview_confirmation: Optional[Dict[str, str]]
    interview_results: Optional[List[InterviewResult]]
    
    # Decision stage
    final_shortlist: Optional[List[str]]
    
    # Offer stage
    offer_reply: Optional[Dict[str, str]]
    last_offer_reply: Optional[str]
    
    # Onboarding stage
    onboarding_status: Optional[str]
    onboarding_info: Optional[Dict[str, str]]
    joining_date: Optional[str]
    
    # Error handling
    error: Optional[str]


