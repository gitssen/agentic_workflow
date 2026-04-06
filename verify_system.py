import requests
import json
import sys
import time

def run_test(query, persona="supervisor"):
    base_url = "http://192.168.1.100:8000"
    payload = {
        "message": query,
        "persona": persona
    }
    
    print(f"\n--- Testing Multi-Agent: '{query}' ---")
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
                        elif step_type == "delegation":
                            print(f"   [Delegation] {data.get('content')}")
                        elif step_type == "observation":
                            content = data.get("content", "")
                            print(f"   [Observation] {content[:100]}...")
                        elif step_type == "thought":
                            content = data.get("content", "")
                            print(f"   [Thought] {content[:100]}...")
                        elif step_type == "final_answer":
                            print(f"\n✅ [Final Approved Artifact] {data.get('content')}")
                        elif step_type == "error":
                            print(f"❌ [Agent Error] {data.get('content')}")
                            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False
    return True

def verify_system():
    base_url = "http://192.168.1.100:8000"
    
    print(f"--- Checking Connectivity ---")
    try:
        requests.get(f"{base_url}/personas").raise_for_status()
        print("✅ Backend is reachable.")
    except Exception as e:
        print(f"❌ Backend unreachable: {e}")
        sys.exit(1)

    tests = [
        "Write a 100 word blog about Artificial Intelligence. Then rewrite it to sound like William Shakespeare.",
        "Write a Python script that defines a function to compute the 10th Fibonacci number. Then test it to make sure it works."
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
