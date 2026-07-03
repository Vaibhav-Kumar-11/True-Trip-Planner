import os
from tavily import TavilyClient


def search(query: str, max_results: int = 5) -> list[dict]:
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.search(query=query, max_results=max_results)
    return response.get("results", [])
