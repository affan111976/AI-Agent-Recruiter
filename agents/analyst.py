from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser 
from .schemas import JobDescription

def create_job_analyst_agent(llm):
    """
    Creates the agent that analyzes the user's request
    and generates a detailed job description.
    
    Args:
        llm: The language model to use for generating job descriptions
        
    Returns:
        A chain that takes user_request and returns a JobDescription object
    """
    # Instantiate the parser with your Pydantic model
    parser = JsonOutputParser(pydantic_object=JobDescription)

    # Update the prompt to include format instructions from the parser
    # This tells the LLM exactly how to format the JSON.
    prompt_template = """You are an expert HR analyst. Your task is to create a detailed, professional job description based on a user's request.

                        User's request: {user_request}

                        {format_instructions}

                        Important: Ensure you provide a complete job description with:
                        - A clear job title
                        - Company name (use a placeholder if not specified)
                        - Comprehensive list of responsibilities (at least 3-5 items)
                        - Detailed qualifications and required skills (at least 3-5 items)
                        - Benefits and offerings (at least 2-3 items)
                        """

    prompt = ChatPromptTemplate.from_template(
        prompt_template,
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    # Return the complete chain: prompt -> llm -> parser
    return prompt | llm | parser