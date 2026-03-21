import firebase_admin
from main import ToolRegistry
from dotenv import load_dotenv

load_dotenv()

# Initialize Firebase if not already
if not firebase_admin._apps:
    firebase_admin.initialize_app()

print("--- Testing Tool Registry Retrieval ---")
registry = ToolRegistry()
query = "What is the weather in Tokyo?"
relevant_tools = registry.get_relevant_tools(query)

print(f"Query: {query}")
print(f"Found {len(relevant_tools)} tools.")
for t in relevant_tools:
    print(f" - {t['name']}: {t['description']}")

if any(t['name'] == 'get_weather' for t in relevant_tools):
    print("\nSUCCESS: 'get_weather' was correctly identified as a relevant tool.")
else:
    print("\nFAILURE: 'get_weather' was not among the top results.")
