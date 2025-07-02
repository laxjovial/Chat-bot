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
# This import relies on the 'config' directory being a package.
from config.config_manager import config_manager 

# === Embedding Selector ===
def get_embedder():
    """
    Gets the appropriate embedder based on global config.
    Supports OpenAI and HuggingFace embeddings.
    """
    embedding_mode = config_manager.get('rag.embedding_mode', 'openai')
    embedding_model = config_manager.get('rag.embedding_model', 'text-embedding-ada-002')
    
    if embedding_mode == "openai":
        openai_api_key = config_manager.get_secret('openai.api_key')
        if not openai_api_key:
            raise ValueError("OpenAI API key not found in secrets.toml under [openai] api_key.")
        return OpenAIEmbeddings(model=embedding_model, openai_api_key=openai_api_key)
    elif embedding_mode == "huggingface":
        # For HuggingFace, ensure you have the model downloaded or accessible
        # HuggingFaceEmbeddings typically don't require an API key by default
        return HuggingFaceEmbeddings(model_name=embedding_model)
    else:
        raise ValueError(f"Unsupported embedding mode: {embedding_mode}")

# === LLM Selector ===
def get_llm():
    """
    Gets the appropriate LLM instance based on global config.
    Supports OpenAI, Google Gemini, and Ollama.
    """
    llm_provider = config_manager.get('llm.provider', 'openai').lower()
    llm_model = config_manager.get('llm.model', 'gpt-4o')
    temperature = config_manager.get('llm.temperature', 0.7)

    if llm_provider == "openai":
        openai_api_key = config_manager.get_secret('openai.api_key')
        if not openai_api_key:
            raise ValueError("OpenAI API key not found in secrets.toml under [openai] api_key.")
        return ChatOpenAI(model=llm_model, temperature=temperature, openai_api_key=openai_api_key)
    elif llm_provider == "google":
        google_api_key = config_manager.get_secret('google.api_key')
        if not google_api_key:
            raise ValueError("Google API key not found in secrets.toml under [google] api_key.")
        # Ensure model is appropriate for Google (e.g., "gemini-pro", "gemini-1.5-pro")
        return ChatGoogleGenerativeAI(model=llm_model, temperature=temperature, google_api_key=google_api_key)
    elif llm_provider == "ollama":
        # Ollama might not require an API key, check config for base_url
        ollama_base_url = config_manager.get('ollama.api_url', 'http://localhost:11434')
        return Ollama(model=llm_model, base_url=ollama_base_url, temperature=temperature)
    else:
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")

# === Document Loader ===
SUPPORTED_DOC_EXTS = [".pdf", ".txt", ".csv", ".md", ".docx"]

def load_document_file(file_path: Path) -> List[Document]:
    """
    Loads a document from the given path using the appropriate LangChain loader.
    Supports PDF, TXT, CSV, Markdown, and DOCX files.
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
    Loads a document from the given path and splits it into chunks using
    RecursiveCharacterTextSplitter, with parameters from global config.
    """
    docs = load_document_file(file_path)

    # Get chunk size and overlap from config, with defaults
    chunk_size = config_manager.get('rag.chunk_size', 1000)
    chunk_overlap = config_manager.get('rag.chunk_overlap', 150)

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(docs)

# CLI Test (optional, for direct testing outside Streamlit)
if __name__ == "__main__":
    import streamlit as st
    import logging
    import shutil
    import os

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"}
            self.google = {"api_key": "AIzaSy-mock-google-key"}
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}

    # Mock the global config_manager instance if it's not already initialized
    try:
        from config.config_manager import ConfigManager
        
        # Create dummy config.yml for the ConfigManager to load
        dummy_data_dir = Path("data")
        dummy_data_dir.mkdir(exist_ok=True)
        dummy_config_path = dummy_data_dir / "config.yml"
        with open(dummy_config_path, "w") as f:
            f.write("""
llm:
  provider: openai
  model: gpt-3.5-turbo
  temperature: 0.5
rag:
  embedding_mode: openai
  embedding_model: text-embedding-ada-002
  chunk_size: 500
  chunk_overlap: 50
""")
        
        # Initialize config_manager with mocked secrets
        if not hasattr(st, 'secrets'):
            st.secrets = MockSecrets()
            print("Mocked st.secrets for standalone testing.")
        
        # Ensure config_manager is a fresh instance for this test run
        ConfigManager._instance = None # Reset the singleton
        ConfigManager._is_loaded = False
        config_manager = ConfigManager()
        print("ConfigManager initialized for testing.")

    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Skipping tests.")
        config_manager = None # Set to None to skip tests

    print("\n--- Testing llm_embedding_utils.py ---")

    if config_manager:
        # Test get_embedder
        try:
            embedder = get_embedder()
            print(f"Embedder initialized: {type(embedder).__name__}")
        except Exception as e:
            print(f"Error getting embedder: {e}")

        # Test get_llm
        try:
            llm_model = get_llm()
            print(f"LLM initialized: {type(llm_model).__name__}")
        except Exception as e:
            print(f"Error getting LLM: {e}")
        
        # Test load_document_file and load_and_chunk_document
        dummy_file_path = Path("temp_test_doc_for_llm_utils.txt")
        with open(dummy_file_path, "w") as f:
            f.write("This is a test document for loading and chunking. " * 50)
        
        try:
            docs = load_document_file(dummy_file_path)
            print(f"Loaded {len(docs)} documents from {dummy_file_path.name}")
            
            chunks = load_and_chunk_document(dummy_file_path)
            print(f"Chunked into {len(chunks)} chunks.")
            print(f"First chunk content: {chunks[0].page_content[:100]}...")
        except Exception as e:
            print(f"Error loading/chunking document: {e}")
        finally:
            if dummy_file_path.exists():
                dummy_file_path.unlink()

    else:
        print("Skipping tests due to ConfigManager issues.")

    # Clean up dummy config files
    if dummy_data_dir.exists():
        if dummy_config_path.exists():
            dummy_config_path.unlink()
        if not list(dummy_data_dir.iterdir()):
            dummy_data_dir.rmdir()
