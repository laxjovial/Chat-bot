# media/tools/import_utils.py

import os
import shutil
import uuid
from typing import List
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    CSVLoader,
    UnstructuredMarkdownLoader,
    UnstructuredWordDocumentLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

from media.config.config_manager import get_embedding_config

# === Base Directories ===
BASE_UPLOAD_DIR = Path("media/uploads")
BASE_VECTOR_DIR = Path("media/chroma")
SUPPORTED_EXTS = [".pdf", ".txt", ".csv", ".md", ".docx"]


# === Embedding Selection ===
def get_embedder(user_token: str):
    config = get_embedding_config(user_token)
    if config["mode"] == "openai":
        return OpenAIEmbeddings(model=config["model"])
    else:
        return HuggingFaceEmbeddings(model_name=config["model"])


# === File Loader ===
def load_file(file_path: Path) -> List[Document]:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return PyPDFLoader(str(file_path)).load()
    elif ext == ".txt":
        return TextLoader(str(file_path)).load()
    elif ext == ".csv":
        return CSVLoader(str(file_path)).load()
    elif ext == ".md":
        return UnstructuredMarkdownLoader(str(file_path)).load()
    elif ext == ".docx":
        return UnstructuredWordDocumentLoader(str(file_path)).load()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# === Upload + Embed ===
def process_upload(file, user_token: str, section: str = "media") -> str:
    """
    Saves and embeds uploaded file into vector store for user & section.
    """
    # 1. Save
    upload_dir = BASE_UPLOAD_DIR / user_token / section
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_ext = Path(file.name).suffix
    if file_ext.lower() not in SUPPORTED_EXTS:
        raise ValueError(f"Unsupported file type: {file_ext}")

    file_id = str(uuid.uuid4())
    saved_path = upload_dir / f"{file_id}{file_ext}"
    with open(saved_path, "wb") as f:
        f.write(file.read())

    # 2. Chunk
    docs = load_file(saved_path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    # 3. Vectorize
    vector_dir = BASE_VECTOR_DIR / user_token / section
    embedder = get_embedder(user_token)
    vectordb = Chroma.from_documents(chunks, embedder, persist_directory=str(vector_dir))
    vectordb.persist()

    return f"✅ Uploaded and embedded: {saved_path.name}"


# === Optional Cleanup ===
def delete_user_section_vectors(user_token: str, section: str):
    dir_path = BASE_VECTOR_DIR / user_token / section
    if dir_path.exists():
        shutil.rmtree(dir_path)
        return True
    return False
