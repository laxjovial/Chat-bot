# sports/tools/vector_query_tool.py

from typing import Optional
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from sports.config.config_manager import get_embedding_config, get_user_tier
from sports.tools.export_utils import export_vector_results
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

import os

# === Get Embedder Based on Config ===
def get_embedder(user_token: str):
    config = get_embedding_config(user_token)
    if config["mode"] == "openai":
        return OpenAIEmbeddings(model=config["model"])
    else:
        return HuggingFaceEmbeddings(model_name=config["model"])


# === Main Vector Query Tool ===
@tool
def QueryUploadedDocs(query: str, user_token: str = "default", section: str = "sports", export: Optional[bool] = False) -> str:
    """
    Queries uploaded and indexed documents for a user and section using vector similarity search.
    Returns text chunks or saves results if export is enabled.
    """
    vector_path = f"sports/chroma/{user_token}/{section}"
    if not os.path.exists(vector_path):
        return "No indexed data found for this section. Please upload a document first."

    vectordb = Chroma(persist_directory=vector_path, embedding_function=get_embedder(user_token))
    results: list[Document] = vectordb.similarity_search(query, k=5)

    if not results:
        return "No matching results found in uploaded content."

    combined = "\n\n".join([r.page_content.strip() for r in results])

    if export:
        export_vector_results(results, query=query, section=section, user_id=user_token)

    return combined

