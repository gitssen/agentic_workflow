import requests
import datetime
import json
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from config import get_genai_client, MODEL_ID

def get_breaking_news(topic: str, region: str = "US") -> str:
    """
    Finds current news headlines and snippets for a given topic using Google Search via Gemini.
    Returns a list of titles and URLs.
    """
    client = get_genai_client()
    query = f"latest news {topic}"
    
    # We use the built-in google_search tool in Gemini to get reliable results
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=f"Provide a list of 5-8 latest news URLs and titles for: {topic}",
            config={
                'tools': [{'google_search': {}}],
            }
        )
        
        # Extract the grounded search results or the model's text response
        return response.text
    except Exception as e:
        return f"Error fetching news for '{topic}': {str(e)}"

def search_web(query: str, num_results: int = 5) -> str:
    """
    Performs a general web search for information using Google Search via Gemini.
    Use this for historical context, general knowledge, or when breaking news isn't required.
    """
    client = get_genai_client()
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=f"Search the web and provide detailed information for: {query}",
            config={
                'tools': [{'google_search': {}}],
            }
        )
        return response.text
    except Exception as e:
        return f"Error during search for '{query}': {str(e)}"

def analyze_article_content(url: str) -> str:
    """
    Scrapes and extracts the main text content from a specific news article URL.
    Use this to get deeper details once you have a specific source.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.37 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.37'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:3000] + ("..." if len(text) > 3000 else "")
    except Exception as e:
        return f"Error analyzing article at {url}: {str(e)}"

async def cross_reference_query(query: str, sub_agent=None) -> str:
    """
    Specifically cross-references a query across multiple sources to identify bias or conflicting reports.
    This tool utilizes a SubAgent to perform deeper analysis. [Self-Resolving]
    """
    if sub_agent is None:
        return "Error: SubAgent capability not available for cross-referencing."
        
    prompt = (
        f"Investigate and cross-reference the following query: '{query}'.\n"
        "To avoid infinite loops, DO NOT use the 'cross_reference_query' tool again.\n"
        "Instead, use 'get_breaking_news' or 'search_web' to find sources and 'analyze_article_content' to read them. "
        "Then, compare the findings to identify conflicting viewpoints or common facts."
    )
    return await sub_agent.solve(prompt)
