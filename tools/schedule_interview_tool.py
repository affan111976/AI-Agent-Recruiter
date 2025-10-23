from langchain_core.tools import tool
from datetime import datetime, timedelta

# This is a placeholder for the real calendar API tool.
# In a real integration, we would import and use the actual calendar tool.
from .placeholder_calendar_api import generic_calendar

@tool
def schedule_interview_tool(candidate_name: str, job_title: str) -> str:
    """
    Schedules an interview on the calendar for a given candidate and job title.
    The interview is scheduled for the next business day at 10:00 AM.
    """
    print(f"--- SCHEDULING INTERVIEW for {candidate_name} ---")
    
    # Determine the date for tomorrow
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
    interview_time = f"{tomorrow}T1000" # 10:00 AM

    try:
        # Use the calendar tool to create the event
        event_title = f"Interview: {candidate_name} for {job_title}"
        
        # In a real scenario, we would call the actual API like this:
        # result = generic_calendar.create(
        #     title=event_title,
        #     start_datetime=interview_time,
        #     duration="1h",
        #     attendees=[candidate_email] # we'd need the candidate's email
        # )
        
        # We will simulate the successful creation for this example.
        print(f"(SIMULATED) Calendar event created: '{event_title}' at {interview_time}.")
        
        return f"Interview successfully scheduled for {candidate_name} at 10:00 AM tomorrow."

    except Exception as e:
        return f"Failed to schedule interview for {candidate_name}: {e}"