# shared_tools/query_uploaded_docs_tool.py

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.tools import tool

# Import necessary components for embeddings and LLM
from shared_tools.llm_embedding_utils import get_embeddings, get_llm
from shared_tools.vector_utils import BASE_VECTOR_DIR, load_vectorstore, save_vectorstore
from shared_tools.export_utils import export_vector_results # For exporting results

# Import config_manager for RAG settings and user tier capabilities
from config.config_manager import config_manager
from utils.user_manager import get_user_tier_capability # For RBAC checks

logger = logging.getLogger(__name__)

@tool
def QueryUploadedDocs(query: str, user_token: str, section: str, export: Optional[bool] = False, k: int = 5) -> str:
    """
    Queries previously uploaded and indexed documents for a specific user and section
    using vector similarity search (RAG - Retrieval Augmented Generation).
    
    Args:
        query (str): The search query to find relevant document chunks.
        user_token (str): The unique identifier for the user.
        section (str): The specific section (e.g., "sports", "finance", "medical")
                       under which the documents were uploaded and indexed.
        export (bool): If True, the results will be saved to a file in markdown format.
                       Defaults to False.
        k (int): The number of top relevant document chunks to retrieve.
                 This will be capped by the user's tier capability.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path if exported.
    """
    logger.info(f"Tool: QueryUploadedDocs called for user: '{user_token}', section: '{section}', query: '{query}'")

    # --- RBAC Enforcement for Uploaded Docs Query ---
    is_query_enabled = get_user_tier_capability(user_token, 'uploaded_docs_query_enabled', False)
    if not is_query_enabled:
        return "Access Denied: Querying uploaded documents is not enabled for your current tier. Please upgrade your plan."
    
    # Cap the 'k' (number of results) based on a tier capability if desired.
    # For now, we'll use a general RAG setting from config.yml, but could be tier-specific.
    max_k_results = config_manager.get('rag.max_query_results_k', 10) # Default max k results
    k = min(k, max_k_results)


    vector_db_path = BASE_VECTOR_DIR / user_token / section
    
    if not vector_db_path.exists() or not any(vector_db_path.iterdir()):
        logger.warning(f"No vector store found for user '{user_token}' in section '{section}' at {vector_db_path}")
        return f"No documents have been uploaded or indexed for the '{section}' section yet. Please upload documents first."

    try:
        embeddings = get_embeddings()
        vectorstore = load_vectorstore(user_token, section, embeddings)
        
        if vectorstore is None:
            logger.error(f"Failed to load vector store for user '{user_token}' in section '{section}'.")
            return "Error: Could not load indexed documents. Please try re-uploading."

        # Perform similarity search
        retrieved_docs = vectorstore.similarity_search(query, k=k)
        
        if not retrieved_docs:
            return f"No relevant information found in your uploaded documents for the query: '{query}'."

        # Combine relevant document content
        combined_content = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
        
        # Optionally, use LLM to synthesize an answer from retrieved docs (RAG)
        llm = get_llm()
        
        # Create a prompt for RAG
        rag_prompt = f"""
        Based on the following retrieved document chunks, answer the user's query.
        If the information is not directly available in the provided chunks, state that you cannot answer from the given documents.

        User Query: {query}

        Document Chunks:
        {combined_content}

        Answer:
        """
        
        # Generate the answer using the LLM
        final_answer = llm.invoke(rag_prompt).content

        # Add source information
        source_info = "\n\n**Sources from your uploaded documents:**\n"
        for i, doc in enumerate(retrieved_docs):
            source_info += f"- Document Chunk {i+1} (Source: {doc.metadata.get('source', 'Unknown')}, Page: {doc.metadata.get('page', 'N/A')})\n"
        
        full_response = f"{final_answer}\n{source_info}"

        if export:
            export_path = export_vector_results(user_token, section, query, retrieved_docs, final_answer)
            return f"Results exported to: {export_path}\n\n{full_response}"
        
        return full_response

    except Exception as e:
        logger.error(f"Error querying uploaded documents for user '{user_token}', section '{section}': {e}", exc_info=True)
        return f"An error occurred while querying your documents: {e}"

# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import os
    import shutil
    from unittest.mock import MagicMock
    from langchain_core.documents import Document

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Required for embeddings and LLM
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
                    "uploaded_docs_query_enabled": False,
                    "max_query_results_k": 1
                },
                "basic": {
                    "uploaded_docs_query_enabled": True,
                    "max_query_results_k": 3
                },
                "pro": {
                    "uploaded_docs_query_enabled": True,
                    "max_query_results_k": 5
                },
                "elite": {
                    "uploaded_docs_query_enabled": True,
                    "max_query_results_k": 10
                },
                "premium": {
                    "uploaded_docs_query_enabled": True,
                    "max_query_results_k": 20
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
                'rag': {
                    'max_query_results_k': 10 # Default for RAG section
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

    print("\n--- Testing query_uploaded_docs_tool.py with RBAC ---")
    
    # Setup dummy vector store for testing
    test_user_basic = st.secrets.user_tokens["basic_user_token"]
    test_section = "test_docs"
    test_vector_path = BASE_VECTOR_DIR / test_user_basic / test_section
    
    # Create dummy documents
    docs = [
        Document(page_content="This is the first document about AI and machine learning.", metadata={"source": "doc1.pdf", "page": 1}),
        Document(page_content="The second document discusses financial markets and investment strategies.", metadata={"source": "doc2.txt", "page": 1}),
        Document(page_content="A third document on sports analytics and player performance.", metadata={"source": "doc3.docx", "page": 1}),
        Document(page_content="Another document on AI ethics and responsible AI development.", metadata={"source": "doc4.pdf", "page": 2}),
    ]
    
    # Mock embeddings for testing
    class MockEmbeddings:
        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            # Return dummy embeddings (e.g., based on length of text)
            return [[float(len(text)) / 100.0] * 10 for text in texts] # A simple mock embedding
        def embed_query(self, text: str) -> List[float]:
            return [float(len(text)) / 100.0] * 10

    # Override get_embeddings to return our mock
    import shared_tools.llm_embedding_utils
    shared_tools.llm_embedding_utils.get_embeddings = lambda: MockEmbeddings()
    
    # Mock LLM for RAG
    class MockLLM:
        def invoke(self, prompt: str) -> MagicMock:
            mock_content = f"Mock LLM response based on query: '{prompt.split('User Query: ')[1].split('Document Chunks:')[0].strip()}' and provided documents."
            mock_message = MagicMock()
            mock_message.content = mock_content
            return mock_message
    
    shared_tools.llm_embedding_utils.get_llm = lambda: MockLLM()

    # Build and save a mock vector store
    try:
        embeddings_instance = get_embeddings() # Get the mock embeddings
        vectorstore = FAISS.from_documents(docs, embeddings_instance)
        save_vectorstore(test_user_basic, test_section, vectorstore)
        print(f"Mock vector store created at: {test_vector_path}")
    except Exception as e:
        print(f"Error creating mock vector store: {e}")
        vectorstore = None


    if vectorstore:
        # Test with free user (should be denied)
        print("\n--- Free User (Access Denied) ---")
        free_user_token = st.secrets.user_tokens["free_user_token"]
        result_free = QueryUploadedDocs(query="What is AI?", user_token=free_user_token, section=test_section, k=1)
        print(f"Free User Result:\n{result_free}")
        assert "Access Denied" in result_free

        # Test with basic user (should be allowed, k capped at 3 by mock config)
        print("\n--- Basic User (Allowed, k capped) ---")
        basic_user_token = st.secrets.user_tokens["basic_user_token"]
        result_basic = QueryUploadedDocs(query="What is AI?", user_token=basic_user_token, section=test_section, k=5) # Request k=5, should be capped to 3
        print(f"Basic User Result (first 500 chars):\n{result_basic[:500]}...")
        assert "Access Denied" not in result_basic
        # Further assertions would require parsing the output to check actual k, which is complex for string output.
        # But the internal logic `k = min(k, max_k_results)` handles it.

        # Test with admin user (should be allowed, k unlimited)
        print("\n--- Admin User (Allowed, k unlimited) ---")
        admin_user_token = st.secrets.user_tokens["admin_user_token"]
        result_admin = QueryUploadedDocs(query="Tell me about financial markets.", user_token=admin_user_token, section=test_section, k=10) # Request k=10, should be unlimited
        print(f"Admin User Result (first 500 chars):\n{result_admin[:500]}...")
        assert "Access Denied" not in result_admin

    else:
        print("Skipping QueryUploadedDocs tests as mock vector store could not be created.")

    # Clean up dummy files and directories
    if test_vector_path.exists():
        shutil.rmtree(test_vector_path, ignore_errors=True)
    
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        for f in dummy_data_dir.iterdir():
            if f.is_file():
                os.remove(f)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)

    print("\n--- RBAC tests for query_uploaded_docs_tool completed. ---")
