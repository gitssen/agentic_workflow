import os
import requests
import json
from agent.config import setup_logger

logger = setup_logger("Tool:Traffic")

async def get_traffic_info(destination: str, origin: str = None, sub_agent=None) -> str:
    """
    Gets detailed travel time and traffic information using the Google Maps Routes API (v2).
    If origin is not provided, it can be resolved automatically using a sub-agent.
    Args:
        destination: Ending location (address or city).
        origin: Optional starting location. If omitted, will be auto-detected.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY not set in .env"

    if not origin:
        if sub_agent:
            logger.debug("  [Tool] Origin missing. Asking sub-agent to find current location...")
            res = await sub_agent.solve("What is the user's current city and region?")
            origin = res.replace("Final Answer:", "").strip()
            logger.debug(f"  [Tool] Sub-agent resolved origin to: {origin}")
        else:
            return "Error: origin is required but no sub-agent available."

    logger.debug(f"  [Tool] Computing route from {origin} to {destination} via Routes API...")
    
    try:
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.localizedValues"
        }
        
        body = {
            "origin": {"address": str(origin)},
            "destination": {"address": str(destination)},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": False,
            "routeModifiers": {
                "avoidTolls": False,
                "avoidHighways": False,
                "avoidFerries": False
            },
            "languageCode": "en-US",
            "units": "IMPERIAL"
        }

        response = requests.post(url, headers=headers, json=body)
        
        if not response.ok:
            error_data = response.json() if response.text else response.reason
            logger.error(f"Routes API Error (HTTP {response.status_code}): {error_data}")
            return f"Error from Google Maps: {error_data}"

        data = response.json()

        if not data.get('routes'):
            return f"Error: No routes found from {origin} to {destination}."

        route = data['routes'][0]
        localized = route.get('localizedValues', {})

        result = {
            "origin": origin,
            "destination": destination,
            "distance": localized.get('distance', {}).get('text', 'N/A'),
            "duration": localized.get('duration', {}).get('text', 'N/A'),
            "status": "Success (Traffic Aware)"
        }
        return json.dumps(result)

    except Exception as e:
        logger.error(f"Routes API Exception: {e}")
        return f"Error: {str(e)}"
