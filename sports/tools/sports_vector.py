# sports/tools/sports_vector.py

import os
import json
from typing import List
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

from sports.config.config_manager import get_embedding_config

# === Base Paths ===
BASE_VECTOR_DIR = Path("sports/chroma")
OFFLINE_FILE = Path("sports/data/offline_sports.json")


# === Embedding Selection per user ===
def get_embedder(user_token: str):
    config = get_embedding_config(user_token)
    if config["mode"] == "openai":
        return OpenAIEmbeddings(model=config["model"])
    else:
        return HuggingFaceEmbeddings(model_name=config["model"])


# === Load & Embed Data ===
def load_offline_docs() -> List[Document]:
    """Loads offline sports data from JSON into LangChain Documents."""
    with open(OFFLINE_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)
    return [Document(page_content=json.dumps(item)) for item in records]


def build_vectorstore(user_token: str = "default"):
    """Builds and saves the Chroma vector DB from offline_sports.json."""
    docs = load_offline_docs()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    vector_dir = BASE_VECTOR_DIR / user_token / "sports"
    vectordb = Chroma.from_documents(chunks, get_embedder(user_token), persist_directory=str(vector_dir))
    vectordb.persist()
    print("✅ Vectorstore built at:", vector_dir)


def query_vectorstore(query: str, user_token: str = "default", k: int = 3) -> str:
    """Search the vector DB for semantic matches."""
    vector_dir = BASE_VECTOR_DIR / user_token / "sports"
    if not vector_dir.exists():
        return "No vector results found."

    vectordb = Chroma(persist_directory=str(vector_dir), embedding_function=get_embedder(user_token))
    results = vectordb.similarity_search(query, k=k)
    if not results:
        return "No vector results found."
    return "\n".join([f"- {doc.page_content[:300]}..." for doc in results])


# CLI testing (optional)
if __name__ == "__main__":
    from utils.user_manager import get_user_token
    token = get_user_token("victor@gmail.com")
    build_vectorstore(token)
    print(query_vectorstore("Which club has won the most EPL trophies?", token))

