import json
import requests
from config import setup_logger

logger = setup_logger("Tool:Weather")

async def get_weather(location: str = None, date: str = "now", sub_agent=None) -> str:
    """
    Fetches weather data from wttr.in.
    If location is not provided, it can be resolved automatically using a sub-agent.
    Args:
        location: Optional city name (e.g., 'London'). If omitted, will be auto-detected.
        date: When to get weather for. Options: 'now', 'today', 'tomorrow'. Defaults to 'now'.
    """
    if not location:
        if sub_agent:
            logger.debug("  [Tool] Location missing. Asking sub-agent to find current location...")
            res = await sub_agent.solve("What is the user's current city and region?")
            location = res.replace("Final Answer:", "").strip()
            logger.debug(f"  [Tool] Sub-agent resolved location to: {location}")
        else:
            return "Error: Location is required but no sub-agent available."

    logger.debug(f"  [Tool] Fetching weather for {location} (date: {date})...")
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
        logger.error(f"Weather Error: {e}")
        return f"Error: {str(e)}"
