# media/tools/media_tool.py

import requests
import yaml
from typing import Optional
from langchain_core.tools import tool


# === Load all media-related APIs ===
def load_media_apis():
    with open("media/data/media_apis.yaml", "r") as f:
        all_apis = yaml.safe_load(f)
        return [api for api in all_apis if api.get("type") == "media"]

MEDIA_APIS = load_media_apis()


# === Tool entry point for LangChain agents ===
@tool
def MediaTool(query: str, max_results: int = 3) -> str:
    """
    Unified tool for movie, TV, anime, music, and media-related questions.
    Routes to one or more APIs defined in media_apis.yaml.
    """
    for api in MEDIA_APIS:
        name = api.get("name")
        endpoint = api.get("endpoint")
        key_name = api.get("key_name")
        key_value = api.get("key_value")
        headers = api.get("headers", {}).copy()
        params = api.get("default_params", {}).copy()
        query_param = api.get("query_param", "q")
        response_format = api.get("response_format", "json")

        # Inject API key
        if key_name and key_value:
            if api.get("in_header", False):
                headers[key_name] = key_value
            else:
                params[key_name] = key_value

        # Add query string
        params[query_param] = query

        try:
            res = requests.get(endpoint, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                if response_format == "json":
                    return parse_media_response(name, res.json(), query, max_results)
                else:
                    return res.text
        except Exception:
            continue

    return "No media info found from any available source."


# === API-specific response formatting ===
def parse_media_response(api_name: str, data: dict, query: str, max_results: int = 3) -> str:
    if api_name == "TMDb":
        results = data.get("results", [])
        if not results:
            return "TMDb: No results found."
        out = f"[From {api_name}] Results for '{query}':\n"
        for item in results[:max_results]:
            title = item.get("title") or item.get("name") or "Unknown"
            date = item.get("release_date") or item.get("first_air_date", "N/A")
            overview = item.get("overview", "").strip()
            out += f"\n- **{title}** ({date})\n  {overview[:200]}...\n"
        return out

    elif api_name == "Jikan (MyAnimeList)":
        results = data.get("data", [])
        if not results:
            return "Jikan: No anime found."
        out = f"[From {api_name}] Anime matches for '{query}':\n"
        for anime in results[:max_results]:
            title = anime.get("title", "Unknown")
            synopsis = anime.get("synopsis", "")
            out += f"\n- **{title}**: {synopsis[:200]}...\n"
        return out

    elif api_name == "Deezer":
        results = data.get("data", [])
        if not results:
            return "Deezer: No music tracks found."
        out = f"[From {api_name}] Music results for '{query}':\n"
        for track in results[:max_results]:
            title = track.get("title", "Unknown")
            artist = track.get("artist", {}).get("name", "Unknown")
            out += f"\n- {title} by {artist}"
        return out

    elif api_name == "YouTube":
        results = data.get("items", [])
        if not results:
            return "YouTube: No videos found."
        out = f"[From {api_name}] YouTube results for '{query}':\n"
        for item in results[:max_results]:
            snippet = item.get("snippet", {})
            title = snippet.get("title", "Untitled")
            channel = snippet.get("channelTitle", "Unknown Channel")
            out += f"\n- {title} ({channel})"
        return out

    return f"[Generic API Response from {api_name}]\n" + str(data)[:500]
