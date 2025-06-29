# sports/tools/sports_tool_v2.py

import os
import requests
import yaml
import json
from typing import Optional
from langchain_core.tools import tool
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from sports.tools.scraper_tool import scrape_web
from sports.tools.export_utils import export_response

# === Load API keys and config ===
def load_sports_apis():
    with open("sports/data/sports_apis.yaml", "r") as f:
        return yaml.safe_load(f)

SPORTS_APIS = load_sports_apis()
VECTOR_PATH = "sports/chroma/default/"
OFFLINE_FILE = "sports/data/offline_sports.json"
EMBED_MODE = os.getenv("EMBED_MODE", "openai")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-ada-002")


# === Embedding selection ===
def get_embedder():
    if EMBED_MODE == "openai":
        return OpenAIEmbeddings(model=EMBED_MODEL)
    else:
        return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


# === Offline Fallback: Load & Search ===
def query_offline_vectorstore(query: str, k=3) -> str:
    embedder = get_embedder()
    vectordb = Chroma(persist_directory=VECTOR_PATH, embedding_function=embedder)
    results = vectordb.similarity_search(query, k=k)
    if not results:
        return "No offline info found."
    return "\n".join([f"- {doc.page_content[:300]}..." for doc in results])


# === Build Offline Vector Store (Only run once or on update) ===
def build_vectorstore():
    with open(OFFLINE_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)
    docs = [Document(page_content=json.dumps(item)) for item in records]
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    vectordb = Chroma.from_documents(chunks, get_embedder(), persist_directory=VECTOR_PATH)
    vectordb.persist()


# === Main Sports Tool ===
@tool
def SportsToolV2(query: str, export: Optional[bool] = False, allow_scrape: Optional[bool] = False) -> str:
    """
    Handles complex sports queries using multiple APIs, local vectors, scraping, and LLM.
    Allows export of result. Will scrape if allowed and all else fails.
    """
    # Try all APIs
    for api in SPORTS_APIS:
        name = api.get("name")
        endpoint = api.get("endpoint")
        key_name = api.get("key_name")
        key_value = api.get("key_value")
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
                result = parse_response(name, data, query)
                if export:
                    export_response(result, section="sports")
                return result
        except Exception:
            continue

    # If APIs fail → try offline
    fallback = query_offline_vectorstore(query)
    if fallback and fallback != "No offline info found.":
        if export:
            export_response(fallback, section="sports")
        return fallback

    # If allowed, scrape
    if allow_scrape:
        scraped = scrape_web(query)
        if scraped:
            if export:
                export_response(scraped, section="sports")
            return scraped

    return "Sorry, I couldn't find info from APIs, offline files, or scraping."


# === Minimal parser ===
def parse_response(api_name: str, data: dict, query: str) -> str:
    if api_name == "TheSportsDB":
        events = data.get("event") or data.get("teams") or data.get("player")
        if not events:
            return "No data found."
        result = ""
        for item in events[:3]:
            result += f"\n- {item.get('strEvent') or item.get('strTeam') or item.get('strPlayer')}"
        return f"[From {api_name}] Results for '{query}':\n{result}"

    elif api_name == "API-Football":
        response = data.get("response")
        if not response:
            return "No data found."
        result = ""
        for item in response[:3]:
            team = item.get("team", {}).get("name") or item.get("player", {}).get("name")
            result += f"\n- {team}"
        return f"[From {api_name}] Results for '{query}':\n{result}"

    return str(data)[:1000]
