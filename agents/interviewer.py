from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List

# Define the structured output
class InterviewEvaluation(BaseModel):
    candidate_name: str = Field(description="The name of the candidate being interviewed.")
    questions: List[str] = Field(description="A list of 3-5 technical and behavioral questions.")
    evaluation: str = Field(description="A summary of the candidate's strengths and weaknesses based on their resume.")
    recommendation: str = Field(description="Your recommendation: 'Progress' or 'Reject'.")

def create_interviewer_agent(llm):
    """Creates the interviewer agent."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a senior hiring manager. Your task is to conduct an interview for a candidate. "
                "Based on the job description and the candidate's resume, you need to generate relevant interview questions, "
                "provide an evaluation of their fit for the role, and make a recommendation. "
                "Output the result in the requested structured format.",
            ),
            (
                "human",
                "Job Description:\n{job_description}\n\n"
                "Candidate Resume:\n{candidate_resume}\n\n"
                "Please conduct the interview for {candidate_name}."
            ),
        ]
    )
    
    return prompt | llm.with_structured_output(InterviewEvaluation)