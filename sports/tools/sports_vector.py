# sports/tools/sports_vector.py

import os
import json
from typing import List
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

# === Paths and Settings ===
VECTOR_PATH = "sports/chroma/default/"
OFFLINE_FILE = "sports/data/offline_sports.json"
EMBED_MODE = os.getenv("EMBED_MODE", "openai")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-ada-002")


# === Embedding Selection ===
def get_embedder():
    if EMBED_MODE == "openai":
        return OpenAIEmbeddings(model=EMBED_MODEL)
    else:
        return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


# === Load & Embed Data ===
def load_offline_docs() -> List[Document]:
    """Loads offline sports data from JSON into LangChain Documents."""
    with open(OFFLINE_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)
    return [Document(page_content=json.dumps(item)) for item in records]


def build_vectorstore():
    """Builds and saves the Chroma vector DB from offline_sports.json."""
    docs = load_offline_docs()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)
    vectordb = Chroma.from_documents(chunks, get_embedder(), persist_directory=VECTOR_PATH)
    vectordb.persist()
    print("✅ Vectorstore built at:", VECTOR_PATH)


def query_vectorstore(query: str, k: int = 3) -> str:
    """Search the vector DB for semantic matches."""
    vectordb = Chroma(persist_directory=VECTOR_PATH, embedding_function=get_embedder())
    results = vectordb.similarity_search(query, k=k)
    if not results:
        return "No vector results found."
    return "\n".join([f"- {doc.page_content[:300]}..." for doc in results])


# CLI testing (optional)
if __name__ == "__main__":
    build_vectorstore()
    print(query_vectorstore("Which club has won the most EPL trophies?"))
