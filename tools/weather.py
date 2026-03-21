import json
import requests

def get_weather(location: str, date: str = "now") -> str:
    """
    Fetches weather data from wttr.in.
    Args:
        location: The city name (e.g., 'London', 'Tokyo').
        date: When to get weather for. Options: 'now', 'today', 'tomorrow'. Defaults to 'now'.
    """
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
