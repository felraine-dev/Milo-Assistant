from ddgs import DDGS
from ddgs.exceptions import DDGSException
from milo.safety import tool, RISK_LOW

@tool(risk=RISK_LOW)
def web_search(query: str, max_results: int = 5) -> str:
    """Search the live web using DuckDuckGo and return formatted results."""
    try:
        with DDGS() as ddgs:
            # Try 'lite' or 'html' backends which are less prone to blocking
            results = list(ddgs.text(query, max_results=max_results, backend="lite"))
            
        if not results:
            return f"No web results found for query: '{query}'. The search engine may be temporarily rate-limiting requests."
            
        formatted = []
        for idx, r in enumerate(results, 1):
            title = r.get("title", "No Title")
            href = r.get("href", "")
            body = r.get("body", "")
            formatted.append(f"{idx}. **{title}**\n   URL: {href}\n   Snippet: {body}")
            
        return "\n\n".join(formatted)
        
    except DDGSException:
        return f"Web search temporarily unavailable or rate-limited by provider for query: '{query}'."
    except Exception as e:
        return f"Error executing web search: {str(e)}"