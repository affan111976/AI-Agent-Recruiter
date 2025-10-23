from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List

# Define the structured output
class FinalShortlist(BaseModel):
    shortlisted_candidates: List[str] = Field(description="The final list of candidate names to be presented to the hiring manager.")

def create_decision_maker_agent(llm):
    """Creates the decision maker agent."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the head of HR. Your task is to review the interview results and create a final shortlist of candidates. "
                "Only include candidates who were recommended to 'Progress' in the interview stage. "
                "Synthesize all the information and provide the final list of names.",
            ),
            (
                "human",
                "Job Description:\n{job_description}\n\n"
                "Interview Results:\n{interview_results}\n\n"
                "Please provide the final shortlist."
            ),
        ]
    )
    
    return prompt | llm.with_structured_output(FinalShortlist)