# media/tools/doc_summarizer.py

import os
from typing import List
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, CSVLoader,
    UnstructuredMarkdownLoader, UnstructuredWordDocumentLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from media.config.config_manager import get_model_settings


# === Load and chunk file ===
def load_and_chunk(file_path: Path) -> List[Document]:
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        docs = PyPDFLoader(str(file_path)).load()
    elif ext == ".txt":
        docs = TextLoader(str(file_path)).load()
    elif ext == ".csv":
        docs = CSVLoader(str(file_path)).load()
    elif ext == ".md":
        docs = UnstructuredMarkdownLoader(str(file_path)).load()
    elif ext == ".docx":
        docs = UnstructuredWordDocumentLoader(str(file_path)).load()
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    return splitter.split_documents(docs)


# === Summarize the file ===
def summarize_document(file_path: Path, user_id: str = "default") -> str:
    """
    Generates a summary from the uploaded document.
    """
    model_settings = get_model_settings(user_id)
    llm = ChatOpenAI(model=model_settings["llm_model"], temperature=model_settings["temperature"])

    docs = load_and_chunk(file_path)
    chain = load_summarize_chain(llm, chain_type="stuff")
    return chain.run(docs)


# === CLI Testing ===
if __name__ == "__main__":
    path = Path("media/uploads/victor/sample_show_guide.pdf")
    print(summarize_document(path, user_id="victor"))
