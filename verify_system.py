import requests
import json
import sys
import time

def run_test(query, persona="general"):
    base_url = "http://localhost:8000"
    payload = {
        "message": query,
        "persona": persona
    }
    
    print(f"\n--- Testing: '{query}' ---")
    try:
        with requests.post(f"{base_url}/chat", json=payload, stream=True) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        data = json.loads(decoded_line[6:])
                        step_type = data.get("type")
                        
                        if step_type == "action":
                            print(f"   [Action] {data.get('tool')} with {data.get('args')}")
                        elif step_type == "observation":
                            content = data.get("content", "")
                            print(f"   [Observation] {content[:100]}...")
                        elif step_type == "final_answer":
                            print(f"✅ [Final Answer] {data.get('content')}")
                        elif step_type == "error":
                            print(f"❌ [Agent Error] {data.get('content')}")
                            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False
    return True

def verify_system():
    base_url = "http://localhost:8000"
    
    print(f"--- Checking Connectivity ---")
    try:
        requests.get(f"{base_url}/personas").raise_for_status()
        print("✅ Backend is reachable.")
    except Exception as e:
        print(f"❌ Backend unreachable: {e}")
        sys.exit(1)

    tests = [
        "What is the weather?",           # Tests sub-agent location resolution
        "What is the weather in London?", # Tests argument mapping
        "Where am I right now?",           # Tests zero-argument tool
        "Calculate 2**10 and then diff(sin(x), x)", # Tests multiple tools / complex logic
    ]
    
    all_passed = True
    for t in tests:
        if not run_test(t):
            all_passed = False
            
    if all_passed:
        print("\n✨ ALL TESTS PASSED!")
    else:
        print("\n⚠️ SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    verify_system()
