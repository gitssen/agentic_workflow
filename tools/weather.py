import json
import requests

def get_weather(location: str = None, date: str = "now", sub_agent=None) -> str:
    """
    Fetches weather data from wttr.in.
    If location is not provided, it can be resolved automatically using a sub-agent.
    Args:
        location: Optional city name (e.g., 'London'). If omitted, will be auto-detected.
        date: When to get weather for. Options: 'now', 'today', 'tomorrow'. Defaults to 'now'.
    """
    if not location:
        if sub_agent:
            print("  [Tool] Location missing. Asking sub-agent to find current location...")
            # Natural language discovery - no hardcoded tool names!
            res = sub_agent.solve("What is the user's current city and region?")
            # We use a simple regex or split to get the location from the sub-agent's answer
            # In a real system, we'd use the LLM to extract this reliably
            location = res.replace("Final Answer:", "").strip()
            print(f"  [Tool] Sub-agent resolved location to: {location}")
        else:
            return "Error: Location is required but no sub-agent available."

    print(f"  [Tool] Fetching weather for {location} (date: {date})...")
    try:
        response = requests.get(f"https://wttr.in/{location}?format=j1")
        response.raise_for_status()
        data = response.json()
        
        if date.lower() == "now":
            current = data['current_condition'][0]
            return json.dumps({
                "location": location, "temp_c": current['temp_C'], 
                "condition": current['weatherDesc'][0]['value']
            })
        
        day_index = 1 if "tomorrow" in date.lower() else 0
        forecast = data['weather'][day_index]
        return json.dumps({
            "location": location, "date": forecast['date'],
            "avg_temp_c": forecast['avgtempC'],
            "condition": forecast['hourly'][4]['weatherDesc'][0]['value']
        })
    except Exception as e:
        return f"Error: {str(e)}"
