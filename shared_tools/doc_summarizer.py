# shared_tools/doc_summarizer.py

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
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI # Added for Google Gemini
from langchain_community.llms import Ollama # Added for Ollama

from config.config_manager import config_manager # Use the new ConfigManager instance

# === Supported Document Extensions ===
SUPPORTED_DOC_EXTS = [".pdf", ".txt", ".csv", ".md", ".docx"]

# === File Loader ===
def load_and_chunk(file_path: Path) -> List[Document]:
    """
    Loads a document from the given path and splits it into chunks.
    Uses generic document loaders.
    """
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
        raise ValueError(f"Unsupported file type for summarization: {ext}. Supported types are: {', '.join(SUPPORTED_DOC_EXTS)}")

    # Get chunk size and overlap from config, with defaults
    chunk_size = config_manager.get('rag.chunk_size', 1000)
    chunk_overlap = config_manager.get('rag.chunk_overlap', 150)

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(docs)

# === LLM Selector ===
def get_llm_for_summarization():
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
        # Ensure model is appropriate for Google (e.g., "gemini-pro")
        return ChatGoogleGenerativeAI(model=llm_model, temperature=temperature, google_api_key=google_api_key)
    elif llm_provider == "ollama":
        # Ollama might not require an API key, check config for base_url
        ollama_base_url = config_manager.get('ollama.api_url', 'http://localhost:11434')
        return Ollama(model=llm_model, base_url=ollama_base_url, temperature=temperature)
    else:
        raise ValueError(f"Unsupported LLM provider for summarization: {llm_provider}")


# === Summarize a file ===
def summarize_document(file_path: Path) -> str:
    """
    Summarizes a document located at file_path using the configured LLM.
    """
    llm = get_llm_for_summarization()
    docs = load_and_chunk(file_path)

    # Use 'stuff' chain type for smaller documents, or 'map_reduce' for larger
    # For simplicity and general use, 'stuff' works well if chunks are combined first
    # Or for very large documents, consider 'map_reduce' with a custom prompt.
    # Here, we'll assume chunks fit within context for 'stuff' if summarized iteratively
    # Or, more robustly, use map_reduce or refine.
    
    # A simple 'stuff' chain for summarization (best for smaller documents / few chunks)
    # If the document is very large (many chunks), a map_reduce chain would be better.
    # For now, let's keep it simple. The chunking should help fit into context.
    
    # If a document has many chunks, and 'stuff' fails due to context window,
    # consider changing to 'map_reduce' or 'refine' type.
    # For now, assuming relatively small documents that fit in context after chunking,
    # or that the LLM is powerful enough to handle larger contexts.
    
    # Example for `stuff` with custom prompt (optional, but good for control)
    # prompt_template = """Write a concise summary of the following:
    # "{text}"
    # CONCISE SUMMARY:"""
    # PROMPT = PromptTemplate(template=prompt_template, input_variables=["text"])
    # chain = load_summarize_chain(llm, chain_type="stuff", prompt=PROMPT)

    chain = load_summarize_chain(llm, chain_type="stuff")
    summary = chain.run(docs)

    return summary

# CLI Test (optional, for direct testing outside Streamlit)
if __name__ == "__main__":
    # Mock Streamlit secrets and config for local testing if needed
    import streamlit as st
    import logging
    
    logging.basicConfig(level=logging.INFO)

    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Use a real key for actual testing
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Use a real key for actual testing
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}

    # Mock the global config_manager instance if it's not already initialized
    try:
        from config.config_manager import ConfigManager
        if not hasattr(ConfigManager, '_instance') or ConfigManager._instance is None:
            # Create a dummy config.yml for the ConfigManager to load
            dummy_data_dir = Path("data")
            dummy_data_dir.mkdir(exist_ok=True)
            with open(dummy_data_dir / "config.yml", "w") as f:
                f.write("llm:\n  provider: openai\n  model: gpt-3.5-turbo\n  temperature: 0.5\nrag:\n  chunk_size: 500\n  chunk_overlap: 50\n")
            
            # Initialize config_manager with mocked secrets
            if not hasattr(st, 'secrets'):
                st.secrets = MockSecrets()
                print("Mocked st.secrets for standalone testing.")
            
            # Ensure config_manager is a fresh instance for this test run
            config_manager = ConfigManager()
            print("ConfigManager initialized for testing.")

    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Skipping LLM-dependent tests.")
        config_manager = None # Set to None to skip tests


    print("Testing doc_summarizer.py:")

    # Create a dummy document for summarization
    dummy_file_path = Path("temp_test_doc.txt")
    with open(dummy_file_path, "w") as f:
        f.write("This is a very long test document. " * 50 + 
                "It contains multiple sentences that should be summarized. " * 30 +
                "The quick brown fox jumps over the lazy dog. " * 20 +
                "This document is for testing the summarization utility." * 10)
    
    if config_manager:
        try:
            print(f"\nAttempting to summarize: {dummy_file_path.name}")
            summary = summarize_document(dummy_file_path)
            print("--- Summary ---")
            print(summary)
            print("---------------")
        except Exception as e:
            print(f"Error during summarization test: {e}")
    else:
        print("Skipping summarization test due to Config
