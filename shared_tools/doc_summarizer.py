# shared_tools/doc_summarizer.py

import os
from typing import List
from pathlib import Path

from langchain.chains.summarize import load_summarize_chain
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

# Import from the new shared utility file
from shared_tools.llm_embedding_utils import get_llm, load_and_chunk_document, SUPPORTED_DOC_EXTS

from config.config_manager import config_manager # Use the new ConfigManager instance


# === Summarize a file ===
def summarize_document(file_path: Path) -> str:
    """
    Summarizes a document located at file_path using the configured LLM.
    """
    llm = get_llm()
    docs = load_and_chunk_document(file_path) # Use the shared loading and chunking function

    # Use 'stuff' chain type for smaller documents, or 'map_reduce' for larger
    # For simplicity and general use, 'stuff' works well if chunks are combined first
    # Or for very large documents, consider 'map_reduce' with a custom prompt.
    # Here, we'll assume chunks fit within context for 'stuff' if summarized iteratively
    # Or, more robustly, use map_reduce or refine.
    
    # If a document has many chunks, and 'stuff' fails due to context window,
    # consider changing to 'map_reduce' or 'refine' type.
    # For now, assuming relatively small documents that fit in context after chunking,
    # or that the LLM is powerful enough to handle larger contexts.
    
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
            global config_manager # Declare global to assign
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
        print("Skipping summarization test due to Config")
    
    if dummy_file_path.exists():
        dummy_file_path.unlink()
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        if (dummy_data_dir / "config.yml").exists():
            (dummy_data_dir / "config.yml").unlink()
        if not list(dummy_data_dir.iterdir()):
            dummy_data_dir.rmdir()
