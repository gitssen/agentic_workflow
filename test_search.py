from googlesearch import search
import sys

try:
    print("Testing googlesearch...")
    results = list(search("test query", num_results=5))
    print(f"Found {len(results)} results:")
    for r in results:
        print(f" - {r}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
