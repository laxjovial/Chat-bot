# sports/tools/scraper_tool.py

import requests
import yaml
from bs4 import BeautifulSoup
from langchain_core.tools import tool

# === Load search API config ===
def load_search_apis():
    try:
        with open("sports/data/search_apis.yaml", "r") as f:
            return yaml.safe_load(f)
    except:
        return []

SEARCH_APIS = load_search_apis()

@tool
def scrape_web(query: str, max_chars: int = 1000) -> str:
    """
    Smart search fallback: tries Search APIs first, then Wikipedia, then Google scraping.
    Returns first valid response or explains failure.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # === 1. Try Search APIs (SerpAPI, ContextualWeb, etc.) ===
    for api in SEARCH_APIS:
        try:
            endpoint = api.get("endpoint")
            key_name = api.get("key_name")
            key_value = api.get("key_value")
            query_param = api.get("query_param", "q")
            in_header = api.get("in_header", False)
            headers_api = api.get("headers", {}).copy()
            params = {query_param: query}

            if key_name and key_value:
                if in_header:
                    headers_api[key_name] = key_value
                else:
                    params[key_name] = key_value

            res = requests.get(endpoint, headers=headers_api, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                snippets = extract_snippets_from_api(data)
                if snippets:
                    return f"[From {api['name']}]\n" + "\n".join(snippets[:5])
        except Exception:
            continue

    # === 2. Try Wikipedia ===
    try:
        wiki_url = f"https://en.wikipedia.org/wiki/{query.strip().replace(' ', '_')}"
        res = requests.get(wiki_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            paras = soup.select("p")
            content = "\n".join([p.get_text().strip() for p in paras if p.get_text().strip()])
            if content:
                return f"[From Wikipedia]\n{content[:max_chars]}..."
    except Exception:
        pass

    # === 3. Fallback: Google search scrape ===
    try:
        search_url = f"https://www.google.com/search?q={query.strip().replace(' ', '+')}"
        res = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        snippets = soup.find_all("span")
        results = []
        for span in snippets:
            text = span.get_text().strip()
            if len(text) > 40 and text not in results:
                results.append(text)
            if len("\n".join(results)) >= max_chars:
                break

        if results:
            return f"[From Google Results]\n" + "\n".join(results[:10])
    except Exception:
        pass

    return "Nothing found via Search APIs, Wikipedia, or scraping."


def extract_snippets_from_api(data: dict) -> list:
    """Extracts text snippets from known search APIs. Customize per provider."""
    if "organic_results" in data:
        return [r.get("snippet") for r in data["organic_results"] if r.get("snippet")]
    elif "value" in data:  # ContextualWeb
        return [r.get("description") for r in data["value"] if r.get("description")]
    return []
