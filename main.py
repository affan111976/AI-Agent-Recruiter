import uuid
from graph import build_graph
from db import save_state

def main():
    app = build_graph() # Your resumable graph
    
    print("Welcome to the Autonomous HR Agent - Workflow Initiator!")
    
    user_input = input("\nHR Agent> What position are you hiring for? ")
    if user_input:
        # Create a unique ID for this entire hiring process
        job_id = str(uuid.uuid4())
        print(f"--- Starting New Hiring Workflow with ID: {job_id} ---")
        
        # Define the initial state and the configuration for the resumable run
        initial_state = {"initial_request": user_input,
                        "job_id": job_id}
        config = {"configurable": {"thread_id": job_id},
                    "recursion_limit": 50}
        
        # Save the initial state to our DB
        save_state(job_id, initial_state)
        
        # Run the graph until the first pause point (e.g., after interview scheduler)
        # The stream will run all synchronous steps
        for event in app.stream(initial_state, config):
            for key, value in event.items():
                print(f"--- Executing Node: {key} ---")

        print(f"\n--- Workflow paused. Waiting for external triggers (webhooks) for job ID: {job_id} ---")

if __name__ == "__main__":
    main()