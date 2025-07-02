# shared_tools/doc_summarizer.py

import logging
from pathlib import Path
from typing import List, Optional
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
    CSVLoader,
    EvernoteLoader,
    OutlookMessageLoader,
    UnstructuredEPubLoader,
    UnstructuredHTMLLoader,
    UnstructuredImageLoader,
    UnstructuredPowerPointLoader,
    UnstructuredWordDocumentLoader,
    JSONLoader,
    UnstructuredXMLLoader,
    UnstructuredExcelLoader # For .xlsx, .xls
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.tools import tool

# Import necessary components for LLM
from shared_tools.llm_embedding_utils import get_llm

# Import config_manager for RAG settings and user tier capabilities
from config.config_manager import config_manager
from utils.user_manager import get_user_tier_capability # For RBAC checks

logger = logging.getLogger(__name__)

# --- Supported Document Loaders Mapping ---
# Maps file extensions to their respective Langchain document loaders
FILE_LOADERS = {
    ".pdf": PyPDFLoader,
    ".docx": Docx2txtLoader,
    ".txt": TextLoader,
    ".md": UnstructuredMarkdownLoader,
    ".csv": CSVLoader,
    ".enex": EvernoteLoader, # Evernote Export Format
    ".msg": OutlookMessageLoader, # Outlook Message
    ".epub": UnstructuredEPubLoader,
    ".html": UnstructuredHTMLLoader,
    ".htm": UnstructuredHTMLLoader,
    ".png": UnstructuredImageLoader, # Requires `unstructured[image]`
    ".jpg": UnstructuredImageLoader,
    ".jpeg": UnstructuredImageLoader,
    ".ppt": UnstructuredPowerPointLoader,
    ".pptx": UnstructuredPowerPointLoader,
    ".doc": UnstructuredWordDocumentLoader, # For older .doc files
    ".json": JSONLoader, # Requires jq for schema, or custom jq_schema
    ".xml": UnstructuredXMLLoader,
    ".xlsx": UnstructuredExcelLoader,
    ".xls": UnstructuredExcelLoader,
}

# --- Helper Functions ---

def _load_document(file_path: Path) -> List[Document]:
    """Loads a document using the appropriate loader based on file extension."""
    file_extension = file_path.suffix.lower()
    loader_class = FILE_LOADERS.get(file_extension)

    if not loader_class:
        raise ValueError(f"Unsupported file type for summarization: {file_extension}")

    try:
        if file_extension == ".json":
            # JSONLoader requires a jq_schema. For general summarization,
            # we'll try to load the whole file as one doc, or you can specify a schema.
            # For simplicity, we'll load it as text for summarization.
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return [Document(page_content=content, metadata={"source": str(file_path), "type": "json"})]
        elif file_extension in [".xlsx", ".xls"]:
            # ExcelLoader loads each sheet as a separate document.
            loader = loader_class(str(file_path))
            return loader.load()
        else:
            loader = loader_class(str(file_path))
            return loader.load()
    except Exception as e:
        logger.error(f"Error loading document {file_path}: {e}", exc_info=True)
        raise ValueError(f"Failed to load document {file_path}: {e}")

def _split_documents(documents: List[Document]) -> List[Document]:
    """Splits documents into smaller chunks for processing."""
    chunk_size = config_manager.get('rag.chunk_size', 1000)
    chunk_overlap = config_manager.get('rag.chunk_overlap', 100)
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )
    return text_splitter.split_documents(documents)

# --- Main Tool Function ---

@tool
def summarize_document(file_path_str: str, user_token: Optional[str] = None) -> str:
    """
    Summarizes the content of a document located at the given file path.
    Supports various document types (PDF, DOCX, TXT, MD, CSV, etc.).
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/finance/annual_report.pdf"
        user_token (str, optional): The unique identifier for the user, used for RBAC checks.
                                   Required for tier-based access control.
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: summarize_document called for file: '{file_path_str}' for user: '{user_token}'")

    # --- RBAC Enforcement for Document Summarization ---
    # If user_token is provided, check if summarization is enabled for their tier.
    # If user_token is None (e.g., internal system call), assume full access or handle as needed.
    if user_token:
        is_summarization_enabled = get_user_tier_capability(user_token, 'document_summarization_enabled', False)
        if not is_summarization_enabled:
            return "Access Denied: Document summarization is not enabled for your current tier. Please upgrade your plan."

    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.error(f"Document not found at '{file_path_str}' for summarization.")
        return f"Error: Document not found at '{file_path_str}'."
    
    try:
        # Load the document
        documents = _load_document(file_path)
        if not documents:
            return f"Could not load any content from document: {file_path.name}. It might be empty or unreadable."

        # Split into chunks if necessary (for large documents)
        chunks = _split_documents(documents)
        
        # Combine chunks for summarization, or summarize each chunk and then combine summaries
        # For simplicity, we'll combine all chunks up to a certain limit for a single summary call.
        # For very large documents, a map-reduce summarization strategy would be better.
        combined_text = " ".join([chunk.page_content for chunk in chunks])
        
        # Cap combined text length for LLM input to avoid exceeding context window
        max_summary_input_chars = config_manager.get('llm.max_summary_input_chars', 10000)
        if len(combined_text) > max_summary_input_chars:
            logger.warning(f"Document text too long for single summary, truncating to {max_summary_input_chars} characters.")
            combined_text = combined_text[:max_summary_input_chars] + "..."

        if not combined_text.strip():
            return f"No readable text found in document: {file_path.name} after processing."

        llm = get_llm()
        
        # Define the summarization prompt
        summarization_prompt = f"""
        Please provide a concise and comprehensive summary of the following document content.
        Focus on the main points, key arguments, and conclusions.

        Document Content:
        {combined_text}

        Summary:
        """
        
        summary = llm.invoke(summarization_prompt).content
        
        return f"Summary of '{file_path.name}':\n{summary}"
    
    except ValueError as e:
        logger.error(f"Error summarizing document '{file_path_str}': {e}")
        return f"Error summarizing document: {e}"
    except Exception as e:
        logger.critical(f"An unexpected error occurred during summarization of '{file_path_str}': {e}", exc_info=True)
        return f"An unexpected error occurred during summarization: {e}"

# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import os
    import shutil
    from unittest.mock import MagicMock

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Required for LLM
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Required for Google LLM if used
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}
            # Mock user tokens for testing RBAC
            self.user_tokens = {
                "free_user_token": "mock_free_token",
                "basic_user_token": "mock_basic_token",
                "pro_user_token": "mock_pro_token",
                "admin_user_token": "mock_admin_token"
            }
        def get(self, key, default=None):
            parts = key.split('.')
            val = self
            for part in parts:
                if hasattr(val, part):
                    val = getattr(val, part)
                elif isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    return default
            return val

    # Mock user_manager.find_user_by_token and get_user_tier_capability for testing RBAC
    class MockUserManager:
        _mock_users = {
            "mock_free_token": {"username": "FreeUser", "email": "free@example.com", "tier": "free", "roles": ["user"]},
            "mock_basic_token": {"username": "BasicUser", "email": "basic@example.com", "tier": "basic", "roles": ["user"]},
            "mock_pro_token": {"username": "ProUser", "email": "pro@example.com", "tier": "pro", "roles": ["user"]},
            "mock_admin_token": {"username": "AdminUser", "email": "admin@example.com", "tier": "admin", "roles": ["user", "admin"]},
            "nonexistent_token": None
        }
        def find_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
            return self._mock_users.get(token)

        def get_user_tier_capability(self, user_token: Optional[str], capability_key: str, default_value: Any = None) -> Any:
            user = self.find_user_by_token(user_token)
            user_tier = user.get('tier', 'free') if user else 'free'
            user_roles = user.get('roles', []) if user else []

            if 'admin' in user_roles:
                if isinstance(default_value, bool): return True
                if isinstance(default_value, (int, float)): return float('inf')
                return default_value
            
            mock_tier_configs = {
                "free": {
                    "document_summarization_enabled": False
                },
                "basic": {
                    "document_summarization_enabled": False
                },
                "pro": {
                    "document_summarization_enabled": True
                },
                "elite": {
                    "document_summarization_enabled": True
                },
                "premium": {
                    "document_summarization_enabled": True
                }
            }
            tier_config = mock_tier_configs.get(user_tier, {})
            return tier_config.get(capability_key, default_value)


    # Patch the actual imports for testing
    import sys
    sys.modules['utils.user_manager'] = MockUserManager()
    # Mock config_manager to return the test config
    class MockConfigManager:
        _instance = None
        _is_loaded = False
        def __init__(self):
            if MockConfigManager._instance is not None:
                raise Exception("ConfigManager is a singleton. Use get_instance().")
            MockConfigManager._instance = self
            self._config_data = {
                'llm': {
                    'max_summary_input_chars': 10000 # Default for LLM section
                },
                'tiers': { # These are just for the mock, actual tiers are in the user_manager mock
                    'free': {}, 'basic': {}, 'pro': {}, 'elite': {}, 'premium': {}
                }
            }
            self._is_loaded = True
        
        def get(self, key, default=None):
            parts = key.split('.')
            val = self._config_data
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    return default
            return val
        
        def get_secret(self, key, default=None):
            return st.secrets.get(key, default)

    # Replace the actual config_manager with the mock
    sys.modules['config.config_manager'].config_manager = MockConfigManager()
    sys.modules['config.config_manager'].ConfigManager = MockConfigManager # Also replace the class for singleton check

    if not hasattr(st, 'secrets'):
        st.secrets = MockSecrets()
        print("Mocked st.secrets for standalone testing.")

    # Mock LLM for summarization
    class MockLLM:
        def invoke(self, prompt: str) -> MagicMock:
            mock_content = f"Mock summary of the provided text. Original content length: {len(prompt.split('Document Content:')[1].strip())} characters."
            mock_message = MagicMock()
            mock_message.content = mock_content
            return mock_message
    
    import shared_tools.llm_embedding_utils
    shared_tools.llm_embedding_utils.get_llm = lambda: MockLLM()

    print("\n--- Testing doc_summarizer.py with RBAC ---")
    
    # Create a dummy document for summarization
    test_upload_dir = Path("temp_uploads_for_summarization")
    test_upload_dir.mkdir(parents=True, exist_ok=True)
    test_file_path = test_upload_dir / "test_document.txt"
    with open(test_file_path, "w") as f:
        f.write("This is a test document for summarization. It contains some sample text that should be summarized by the tool. " * 50)
    print(f"Created dummy file for summarization: {test_file_path}")

    # Test with free user (should be denied)
    print("\n--- Free User (Access Denied) ---")
    free_user_token = st.secrets.user_tokens["free_user_token"]
    result_free = summarize_document(str(test_file_path), user_token=free_user_token)
    print(f"Free User Result:\n{result_free}")
    assert "Access Denied" in result_free

    # Test with basic user (should be denied)
    print("\n--- Basic User (Access Denied) ---")
    basic_user_token = st.secrets.user_tokens["basic_user_token"]
    result_basic = summarize_document(str(test_file_path), user_token=basic_user_token)
    print(f"Basic User Result:\n{result_basic}")
    assert "Access Denied" in result_basic

    # Test with pro user (should be allowed)
    print("\n--- Pro User (Allowed) ---")
    pro_user_token = st.secrets.user_tokens["pro_user_token"]
    result_pro = summarize_document(str(test_file_path), user_token=pro_user_token)
    print(f"Pro User Result (first 200 chars):\n{result_pro[:200]}...")
    assert "Access Denied" not in result_pro
    assert "Mock summary" in result_pro

    # Test with admin user (should be allowed)
    print("\n--- Admin User (Allowed) ---")
    admin_user_token = st.secrets.user_tokens["admin_user_token"]
    result_admin = summarize_document(str(test_file_path), user_token=admin_user_token)
    print(f"Admin User Result (first 200 chars):\n{result_admin[:200]}...")
    assert "Access Denied" not in result_admin
    assert "Mock summary" in result_admin

    # Clean up dummy files and directories
    if test_file_path.exists():
        os.remove(test_file_path)
    if test_upload_dir.exists():
        shutil.rmtree(test_upload_dir, ignore_errors=True)
    
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        for f in dummy_data_dir.iterdir():
            if f.is_file():
                os.remove(f)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)

    print("\n--- RBAC tests for doc_summarizer.py completed. ---")
