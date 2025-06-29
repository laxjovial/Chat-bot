# sports/tools/sports_tool.py

import os
import requests
import yaml
import json
from typing import Optional
from langchain_core.tools import tool
from sports.tools.scraper_tool import scrape_web
from sports.tools.sports_vector import query_vectorstore
from sports.config.config_manager import get_api_key

# === Load unified sports APIs from YAML ===
def load_sports_apis():
    with open("sports/data/sports_apis.yaml", "r") as f:
        all_apis = yaml.safe_load(f)
        return [api for api in all_apis if api.get("type") == "sports"]

SPORTS_APIS = load_sports_apis()

# === Main Unified Sports Tool (API + vector + scraper) ===
@tool
def SportsTool(query: str, user_token: str = "default", export: Optional[bool] = False, allow_scrape: Optional[bool] = False) -> str:
    """
    Handles sports-related queries using API, vector fallback, and web scraping.
    """
    for api in SPORTS_APIS:
        name = api.get("name")
        endpoint = api.get("endpoint")
        key_name = api.get("key_name")
        key_value = get_api_key(name, user_token) if api.get("key_value") == "USE_USER_KEY" else api.get("key_value")
        headers = api.get("headers", {})
        params = api.get("default_params", {})
        query_param = api.get("query_param", "q")
        response_format = api.get("response_format", "json")

        if key_name and key_value:
            if api.get("in_header"):
                headers[key_name] = key_value
            else:
                params[key_name] = key_value

        params[query_param] = query

        try:
            res = requests.get(endpoint, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json() if response_format == "json" else res.text
                return parse_response(name, data, query)
        except Exception:
            continue

    # === Offline fallback ===
    fallback = query_vectorstore(query, user_token=user_token)
    if fallback and fallback != "No vector results found.":
        return fallback

    # === Scraping fallback ===
    if allow_scrape:
        scraped = scrape_web(query, user_token=user_token)
        if scraped:
            return scraped

    return "Sorry, I couldn't retrieve sports data from any source."


# === API response parser ===
def parse_response(api_name: str, data: dict, query: str) -> str:
    if api_name == "TheSportsDB":
        events = data.get("event") or data.get("teams") or data.get("player")
        if not events:
            return "No data found."
        result = ""
        for item in events[:3]:
            result += f"\n- {item.get('strEvent') or item.get('strTeam') or item.get('strPlayer') or 'Unknown'}"
        return f"[From {api_name}] Results for '{query}':\n" + result

    elif api_name == "API-Football":
        response = data.get("response")
        if not response:
            return "No data found."
        result = ""
        for item in response[:3]:
            team = item.get("team", {}).get("name") or item.get("player", {}).get("name")
            result += f"\n- {team or 'Unknown'}"
        return f"[From {api_name}] Results for '{query}':\n" + result

    return "[Generic API Response]\n" + str(data)[:1000]


