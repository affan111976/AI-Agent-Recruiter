from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List

# Define the structured output
class ScreenedCandidates(BaseModel):
    """Structured output for candidate screening results."""
    passed: List[str] = Field(
        description="List of candidate names who passed the screening and meet the job requirements.",
        default=[]
    )
    failed: List[str] = Field(
        description="List of candidate names who did not pass the screening.",
        default=[]
    )
    reasoning: str = Field(
        description="Brief explanation of the screening decisions.",
        default="No reasoning provided."
    )

def create_resume_screener_agent(llm):
    """
    Creates the resume screener agent.
    
    This agent analyzes candidate resumes against job requirements and determines
    which candidates should proceed to the interview stage.
    
    Args:
        llm: The language model to use for screening
        
    Returns:
        A chain that takes job_description and candidates, returns ScreenedCandidates
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an expert technical recruiter with years of experience in candidate screening. "
                "Your task is to screen candidate resumes against a job description and decide who is a good fit.\n\n"
                "SCREENING CRITERIA:\n"
                "- Match technical skills and qualifications listed in the job description\n"
                "- Evaluate relevant experience and years in the field\n"
                "- Consider cultural fit indicators and soft skills\n"
                "- Be fair and unbiased in your assessment\n\n"
                "IMPORTANT GUIDELINES:\n"
                "1. A candidate PASSES if they meet at least 70% of the required qualifications\n"
                "2. Consider transferable skills and growth potential\n"
                "3. Don't be overly strict on exact keyword matches\n"
                "4. Focus on core competencies rather than every minor requirement\n\n"
                "Analyze each candidate carefully and provide your screening results in the requested structured format."
            ),
            (
                "human",
                "Job Description:\n{job_description}\n\n"
                "Candidates to Screen:\n{candidates}\n\n"
                "Please screen these candidates and provide:\n"
                "1. Names of candidates who PASSED (meet requirements)\n"
                "2. Names of candidates who FAILED (don't meet requirements)\n"
                "3. Brief reasoning for your decisions"
            ),
        ]
    )

    # Return the complete chain with structured output
    return prompt | llm.with_structured_output(ScreenedCandidates)