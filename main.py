import uuid
# In Python terminal or a test script:
from graph import build_graph

graph_app = build_graph()
config = {"configurable": {"thread_id": "400b158a-e493-4cb6-80ed-50395eca88fa"}}

# Check current state
state = graph_app.get_state(config)
print("Current state:", state.values)

# If Alice's data is there but workflow is stuck, resume it
for event in graph_app.stream(None, config):
    print(event)