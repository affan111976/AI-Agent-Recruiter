from pydantic import BaseModel, Field
from typing import List

class JobDescription(BaseModel):
    """A detailed and professional job description."""
    title: str = Field(description="The title of the job position.")
    company: str = Field(description="The name of the company hiring.")
    responsibilities: List[str] = Field(description="A list of key responsibilities for the role.")
    qualifications: List[str] = Field(description="A list of required qualifications and skills.")
    offerings: List[str] = Field(description="A list of benefits or what the company offers.")