# media/tools/vector_query_tool.py

from typing import Optional
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

from media.config.config_manager import get_embedding_config, get_user_tier
from media.tools.export_utils import export_vector_results

import os


# === Select embedder based on user's config ===
def get_embedder(user_token: str):
    config = get_embedding_config(user_token)
    if config["mode"] == "openai":
        return OpenAIEmbeddings(model=config["model"])
    else:
        return HuggingFaceEmbeddings(model_name=config["model"])


# === Main LangChain tool ===
@tool
def QueryUploadedDocs(
    query: str,
    user_token: str = "default",
    section: str = "media",
    export: Optional[bool] = False
) -> str:
    """
    Queries uploaded & embedded documents using semantic similarity search.
    Returns top matching chunks or exports them to markdown.
    """
    vector_path = f"media/chroma/{user_token}/{section}"
    if not os.path.exists(vector_path):
        return "No vector index found for this section. Upload a document first."

    vectordb = Chroma(persist_directory=vector_path, embedding_function=get_embedder(user_token))
    results: list[Document] = vectordb.similarity_search(query, k=5)

    if not results:
        return "No matches found in your uploaded media content."

    combined = "\n\n".join([r.page_content.strip() for r in results])

    if export:
        export_vector_results(results, query=query, section=section, user_id=user_token)

    return combined
