import os
import requests
import json
from config import setup_logger

logger = setup_logger("Tool:Amazon")

def search_amazon(query: str) -> str:
    """
    Searches for products on Amazon using the Rainforest API.
    Returns a list of products with their titles, prices, and ratings.
    Args:
        query: The product name or search term.
    """
    api_key = os.environ.get("RAINFOREST_API_KEY")
    if not api_key:
        return "Error: RAINFOREST_API_KEY not set in .env. Get one at rainforestapi.com"

    logger.debug(f"  [Tool] Searching Amazon for: {query}...")
    
    try:
        url = "https://api.rainforestapi.com/request"
        params = {
            "api_key": api_key,
            "type": "search",
            "amazon_domain": "amazon.com",
            "search_term": query
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if not data.get('search_results'):
            return f"No results found for '{query}' on Amazon."

        results = []
        for item in data['search_results'][:5]: # Limit to top 5 for context efficiency
            results.append({
                "title": item.get('title'),
                "price": item.get('price', {}).get('raw', 'N/A'),
                "rating": item.get('rating', 'N/A'),
                "link": item.get('link')
            })
            
        return json.dumps({"query": query, "results": results})

    except Exception as e:
        logger.error(f"Amazon Search Error: {e}")
        return f"Error: {str(e)}"
