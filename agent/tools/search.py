from agent.config import get_genai_client, MODEL_ID, setup_logger

logger = setup_logger("Tool:Search")

def search_knowledge_base(query: str) -> str:
    """
    Searches the live web using Google Search via Gemini Grounding.
    Args:
        query: The search term or question to look up.
    """
    logger.debug(f"  [Tool] Searching Google (via Gemini) for: {query}...")

    try:
        client = get_genai_client()
        # Use a model that supports Google Search grounding
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=query,
            config={
                'tools': [{'google_search': {}}]
            }
        )

        # Extract the text and any grounding metadata if available
        answer = response.text
        return f"Gemini Search Result: {answer}"

    except Exception as e:
        logger.error(f"Search Error: {e}")
        return f"Gemini Search Error: {str(e)}"
