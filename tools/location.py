import requests
import json
from config import setup_logger

logger = setup_logger("Tool:Location")

def get_current_location() -> str:
    """
    Determines the user's approximate location (City, Region, Country) based on their public IP address.
    No arguments required.
    """
    logger.info("  [Tool] Fetching location from IP...")
    try:
        # Using ip-api.com (free for non-commercial use, no API key required)
        response = requests.get("http://ip-api.com/json/")
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "fail":
            logger.error(f"IP-API Error: {data.get('message')}")
            return f"Error: {data.get('message', 'Unknown error')}"
            
        location_info = {
            "city": data.get("city"),
            "region": data.get("regionName"),
            "country": data.get("country"),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "timezone": data.get("timezone")
        }
        return json.dumps(location_info)
    except Exception as e:
        logger.error(f"Location Fetch Error: {e}")
        return f"Location Error: {str(e)}"
