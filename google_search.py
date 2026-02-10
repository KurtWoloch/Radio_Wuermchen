import os
import requests
import json
from urllib.parse import urlencode

# --- CONFIGURATION ---
# IMPORTANT: Replace these with your actual key and ID.
# For security, you should use environment variables or a separate config file
# instead of hardcoding these, but we'll use placeholder strings for now.
API_KEY = "YOUR_GOOGLE_API_KEY"
CX_ID = "YOUR_SEARCH_ENGINE_ID" 

GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

def google_search(query: str, num: int = 5, **kwargs) -> list:
    """
    Performs a Google Custom Search and returns a list of results.
    
    Args:
        query: The search query string.
        num: The number of results to return (max 10).
        **kwargs: Additional parameters for the Google Search API.
        
    Returns:
        A list of dicts, where each dict is a search result item.
    """
    params = {
        'key': API_KEY,
        'cx': CX_ID,
        'q': query,
        'num': min(num, 10)  # Max 10 results allowed by API
    }
    params.update(kwargs)
    
    # Check if key and ID are set
    if API_KEY == "YOUR_GOOGLE_API_KEY" or CX_ID == "YOUR_SEARCH_ENGINE_ID":
        print("ERROR: Google API Key or CX ID not set in the script.")
        return []

    try:
        response = requests.get(GOOGLE_SEARCH_URL, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        data = response.json()
        
        # Extract and return the search items
        return data.get('items', [])
        
    except requests.exceptions.RequestException as e:
        print(f"ERROR during Google Search API request: {e}")
        return []
    except json.JSONDecodeError:
        print("ERROR: Failed to decode JSON response from Google Search API.")
        return []

if __name__ == '__main__':
    # Example usage:
    search_query = "latest liquidsoap news"
    print(f"Searching for: '{search_query}'")
    
    results = google_search(search_query, num=3)
    
    if results:
        print("\nSearch Results:")
        for i, item in enumerate(results):
            print(f"--- Result {i+1} ---")
            print(f"Title: {item.get('title')}")
            print(f"URL: {item.get('link')}")
            print(f"Snippet: {item.get('snippet')}\n")
    else:
        print("No results found or an error occurred.")
