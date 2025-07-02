# shared_tools/llm_embedding_utils.py

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.llms import Ollama
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, CSVLoader,
    UnstructuredMarkdownLoader, UnstructuredWordDocumentLoader
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List
from pathlib import Path

# Assume config_manager is correctly initialized elsewhere and accessible
from config.config_manager import config_manager # Use the new ConfigManager instance

# === Embedding Selector ===
def get_embedder():
    """Gets the appropriate embedder based on global config."""
    embedding_mode = config_manager.get('rag.embedding_mode', 'openai')
    embedding_model = config_manager.get('rag.embedding_model', 'text-embedding-ada-002')
    
    if embedding_mode == "openai":
        openai_api_key = config_manager.get('openai.api_key')
        if not openai_api_key:
            raise ValueError("OpenAI API key not found in secrets.toml under [openai] api_key.")
        return OpenAIEmbeddings(model=embedding_model, openai_api_key=openai_api_key)
    elif embedding_mode == "huggingface":
        # For HuggingFace, ensure you have the model downloaded or accessible
        return HuggingFaceEmbeddings(model_name=embedding_model)
    else:
        raise ValueError(f"Unsupported embedding mode: {embedding_mode}")

# === LLM Selector ===
def get_llm():
    """Gets the appropriate LLM instance based on global config."""
    llm_provider = config_manager.get('llm.provider', 'openai').lower()
    llm_model = config_manager.get('llm.model', 'gpt-4o')
    temperature = config_manager.get('llm.temperature', 0.7)

    if llm_provider == "openai":
        openai_api_key = config_manager.get('openai.api_key')
        if not openai_api_key:
            raise ValueError("OpenAI API key not found in secrets.toml under [openai] api_key.")
        return ChatOpenAI(model=llm_model, temperature=temperature, openai_api_key=openai_api_key)
    elif llm_provider == "google":
        google_api_key = config_manager.get('google.api_key')
        if not google_api_key:
            raise ValueError("Google API key not found in secrets.toml under [google] api_key.")
        return ChatGoogleGenerativeAI(model=llm_model, temperature=temperature, google_api_key=google_api_key)
    elif llm_provider == "ollama":
        ollama_base_url = config_manager.get('ollama.api_url', 'http://localhost:11434')
        return Ollama(model=llm_model, base_url=ollama_base_url, temperature=temperature)
    else:
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")

# === Document Loader ===
SUPPORTED_DOC_EXTS = [".pdf", ".txt", ".csv", ".md", ".docx"]

def load_document_file(file_path: Path) -> List[Document]:
    """
    Loads a document from the given path using the appropriate loader.
    """
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
        raise ValueError(f"Unsupported file type: {ext}. Supported types are: {', '.join(SUPPORTED_DOC_EXTS)}")

def load_and_chunk_document(file_path: Path) -> List[Document]:
    """
    Loads a document from the given path and splits it into chunks.
    """
    docs = load_document_file(file_path)

    # Get chunk size and overlap from config, with defaults
    chunk_size = config_manager.get('rag.chunk_size', 1000)
    chunk_overlap = config_manager.get('rag.chunk_overlap', 150)

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(docs)
