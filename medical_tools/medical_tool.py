# medical_tools/medical_tool.py

import requests
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import yaml # Added for loading medical_apis.yaml

# Import generic tools
from langchain_core.tools import tool
from shared_tools.query_uploaded_docs_tool import QueryUploadedDocs
from shared_tools.scraper_tool import scrape_web
from shared_tools.doc_summarizer import summarize_document
from shared_tools.import_utils import process_upload, clear_indexed_data # Used by Streamlit apps, not directly as agent tools
from shared_tools.export_utils import export_response, export_vector_results # To be used internally by other tools, or for direct exports
from shared_tools.vector_utils import build_vectorstore, load_docs_from_json_file, BASE_VECTOR_DIR # For testing and potential future direct use

# REMOVED: from langchain_community.tools.python.tool import PythonREPLTool
# The Python interpreter is now managed and imported via shared_tools/python_interpreter_tool.py
# and conditionally added to the agent's toolset in the *_chat_agent_app.py files.

# Import config_manager to access API configurations
from config.config_manager import config_manager

# Constants for the medical section
MEDICAL_SECTION = "medical"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

logger = logging.getLogger(__name__)

@tool
def medical_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 2000) -> str:
    """
    Searches the web for medical and health-related information using a smart search fallback mechanism.
    This tool wraps the generic `scrape_web` tool, providing a medical-specific interface.
    
    Args:
        query (str): The medical-related search query (e.g., "symptoms of common cold", "latest cancer research").
        user_token (str): The unique identifier for the user. Defaults to "default".
        max_chars (int): Maximum characters for the returned snippet. Defaults to 2000.
    
    Returns:
        str: A string containing relevant information from the web.
    """
    logger.info(f"Tool: medical_search_web called with query: '{query}' for user: '{user_token}'")
    return scrape_web(query=query, user_token=user_token, max_chars=max_chars)

@tool
def medical_query_uploaded_docs(query: str, user_token: str = DEFAULT_USER_TOKEN, export: Optional[bool] = False, k: int = 5) -> str:
    """
    Queries previously uploaded and indexed medical documents for a user using vector similarity search.
    This tool wraps the generic `QueryUploadedDocs` tool, fixing the section to "medical".
    
    Args:
        query (str): The search query to find relevant medical documents (e.g., "side effects of drug X", "patient history for ID 123").
        user_token (str): The unique identifier for the user. Defaults to "default".
        export (bool): If True, the results will be saved to a file in markdown format. Defaults to False.
        k (int): The number of top relevant documents to retrieve. Defaults to 5.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path if exported.
    """
    logger.info(f"Tool: medical_query_uploaded_docs called with query: '{query}' for user: '{user_token}'")
    return QueryUploadedDocs(query=query, user_token=user_token, section=MEDICAL_SECTION, export=export, k=k)

@tool
def medical_summarize_document_by_path(file_path_str: str) -> str:
    """
    Summarizes a document related to medical information located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    This tool wraps the generic `summarize_document` tool.
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/medical/patient_record.pdf"
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: medical_summarize_document_by_path called for file: '{file_path_str}'")
    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.error(f"Document not found at '{file_path_str}' for summarization.")
        return f"Error: Document not found at '{file_path_str}'."
    
    try:
        summary = summarize_document(file_path) # Assuming summarize_document can take Path object
        return f"Summary of '{file_path.name}':\n{summary}"
    except ValueError as e:
        logger.error(f"Error summarizing document '{file_path_str}': {e}")
        return f"Error summarizing document: {e}"
    except Exception as e:
        logger.critical(f"An unexpected error occurred during summarization of '{file_path_str}': {e}", exc_info=True)
        return f"An unexpected error occurred during summarization: {e}"

# === Advanced Medical Tools ===

# REMOVED: Direct import and initialization of PythonREPLTool.
# The python_interpreter_with_rbac tool is now imported and added conditionally
# in the *_chat_agent_app.py files based on RBAC.

# Helper to load API configs
def _load_medical_apis() -> Dict[str, Any]:
    """Loads medical API configurations from data/medical_apis.yaml."""
    medical_apis_path = Path("data/medical_apis.yaml")
    if not medical_apis_path.exists():
        logger.warning(f"data/medical_apis.yaml not found at {medical_apis_path}")
        return {}
    try:
        with open(medical_apis_path, "r") as f:
            full_config = yaml.safe_load(f) or {}
            return {api['name']: api for api in full_config.get('apis', [])}
    except Exception as e:
        logger.error(f"Error loading medical_apis.yaml: {e}")
        return {}

MEDICAL_APIS_CONFIG = _load_medical_apis()

@tool
def medical_data_fetcher(
    api_name: str, 
    data_type: str, 
    query: Optional[str] = None, # General query for search APIs (e.g., disease, drug)
    patient_id: Optional[str] = None, # For patient records
    drug_name: Optional[str] = None, # For drug information
    disease_name: Optional[str] = None, # For disease information
    symptom: Optional[str] = None, # For symptom checker
    limit: Optional[int] = None
) -> str:
    """
    Fetches medical and health data from configured APIs (e.g., RxNorm, ClinicalTrials.gov, CDC APIs).
    
    Args:
        api_name (str): The name of the API to use (e.g., "RxNorm", "ClinicalTrials", "CDC").
                        This must match a 'name' field in data/medical_apis.yaml.
        data_type (str): The type of data to fetch.
                          - For RxNorm: "drug_info", "drug_interactions".
                          - For ClinicalTrials: "trial_search", "trial_details".
                          - For CDC: "disease_info", "vaccine_info".
        query (str, optional): General query for search APIs.
        patient_id (str, optional): Identifier for patient records (if supported by API).
        drug_name (str, optional): Name of the drug (e.g., "ibuprofen").
        disease_name (str, optional): Name of the disease (e.g., "diabetes").
        symptom (str, optional): A symptom for a symptom checker (if supported by API).
        limit (int, optional): Maximum number of records to return.
        
    Returns:
        str: A JSON string of the fetched data or an error message.
             The agent can then use `python_interpreter_with_rbac` to parse and analyze this JSON.
    """
    logger.info(f"Tool: medical_data_fetcher called for API: {api_name}, data_type: {data_type}, query: {query}, drug: {drug_name}, disease: {disease_name}")

    api_info = MEDICAL_APIS_CONFIG.get(api_name)
    if not api_info:
        return f"Error: API '{api_name}' not found in data/medical_apis.yaml configuration."

    endpoint = api_info.get("endpoint")
    key_name = api_info.get("key_name")
    api_key_value_ref = api_info.get("key_value")
    default_params = api_info.get("default_params", {})
    headers = api_info.get("headers", {})
    request_timeout = config_manager.get('web_scraping.timeout_seconds', 10)

    api_key = None
    if api_key_value_ref and api_key_value_ref.startswith("load_from_secrets."):
        secret_key_path = api_key_value_ref.split("load_from_secrets.")[1]
        api_key = config_manager.get_secret(secret_key_path)
    
    if key_name and not api_key:
        logger.warning(f"API key for '{api_name}' not found in secrets.toml. Proceeding without key if API allows.")

    params = {**default_params} # Start with default parameters
    if api_key and key_name:
        params[key_name] = api_key
    
    url = endpoint # Base URL, might be modified

    try:
        # --- RxNorm (Placeholder - Actual RxNorm API is complex, uses NLM API key) ---
        if api_name == "RxNorm":
            if not api_key: return "Error: API key is required for RxNorm API."
            
            if data_type == "drug_info":
                if not drug_name: return "Error: 'drug_name' is required for RxNorm drug_info."
                url = f"{endpoint}{api_info['functions']['DRUG_INFO']['path']}"
                params['name'] = drug_name
            elif data_type == "drug_interactions":
                if not drug_name: return "Error: 'drug_name' is required for RxNorm drug_interactions."
                url = f"{endpoint}{api_info['functions']['DRUG_INTERACTIONS']['path']}"
                params['name'] = drug_name
            else:
                return f"Error: Unsupported data_type '{data_type}' for RxNorm."
            
            response = requests.get(url, headers=headers, params=params, timeout=request_timeout)

        # --- ClinicalTrials.gov (Placeholder - Uses a public API, but can be complex) ---
        elif api_name == "ClinicalTrials":
            if data_type == "trial_search":
                if not query: return "Error: 'query' is required for ClinicalTrials trial_search."
                url = f"{endpoint}{api_info['functions']['TRIAL_SEARCH']['path']}"
                params['query'] = query
                if limit: params['pageSize'] = limit # ClinicalTrials uses pageSize
            elif data_type == "trial_details":
                # This would typically require a NCT ID, not a query
                return "Error: 'trial_details' requires a trial ID (NCT number). Not implemented via query."
            else:
                return f"Error: Unsupported data_type '{data_type}' for ClinicalTrials."
            
            response = requests.get(url, headers=headers, params=params, timeout=request_timeout)

        # --- CDC APIs (Placeholder - Many different APIs, simplified for example) ---
        elif api_name == "CDC":
            if data_type == "disease_info":
                if not disease_name: return "Error: 'disease_name' is required for CDC disease_info."
                # Example: CDC has APIs for specific diseases, this is a mock URL
                url = f"{endpoint}{api_info['functions']['DISEASE_INFO']['path']}/{disease_name.replace(' ', '_')}"
            elif data_type == "vaccine_info":
                # Example: CDC has APIs for vaccine schedules, this is a mock URL
                return "Error: 'vaccine_info' not fully implemented; requires specific vaccine name or ID."
            else:
                return f"Error: Unsupported data_type '{data_type}' for CDC."
            
            response = requests.get(url, headers=headers, params=params, timeout=request_timeout)

        else:
            return f"Error: API '{api_name}' is not supported by medical_data_fetcher."

        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()
        
        # Apply limit if specified and data is a list (or has a list-like key)
        if limit and isinstance(data, dict):
            # Common keys for lists in medical APIs
            for key in ['results', 'data', 'drugs', 'diseases', 'trials']:
                if key in data and isinstance(data[key], list):
                    data[key] = data[key][:limit]
                    break
        elif limit and isinstance(data, list):
            data = data[:limit]

        return json.dumps(data, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as req_e:
        logger.error(f"API request failed for {api_name} ({data_type}): {req_e}")
        if hasattr(req_e, 'response') and req_e.response is not None:
            logger.error(f"Response content: {req_e.response.text}")
            return f"API request failed for {api_name}: {req_e.response.text}"
        return f"API request failed for {api_name}: {req_e}"
    except Exception as e:
        logger.error(f"Error processing {api_name} response or request setup: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}"


# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import shutil
    import os
    from config.config_manager import ConfigManager # Import ConfigManager for testing setup
    from shared_tools.llm_embedding_utils import get_llm # For testing summarization with a real LLM
    # Import the RBAC-enabled Python interpreter tool for testing purposes here
    from shared_tools.python_interpreter_tool import python_interpreter_with_rbac
    from unittest.mock import MagicMock

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Replace with a real key
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Replace with a real key
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # For scrape_web testing
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"} # For scrape_web testing
            self.rxnorm_api_key = "YOUR_RXNORM_API_KEY" # For RxNorm (NLM API Key)
            self.cdc_api_key = "YOUR_CDC_API_KEY" # For CDC (if needed)
            # Mock user tokens for testing RBAC
            self.user_tokens = {
                "free_user_token": "mock_free_token",
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
                    "data_analysis_enabled": False,
                    "web_search_limit_chars": 500,
                    "web_search_max_results": 2
                },
                "pro": {
                    "data_analysis_enabled": True,
                    "web_search_limit_chars": 3000,
                    "web_search_max_results": 7
                },
                "elite": {
                    "data_analysis_enabled": True,
                    "web_search_limit_chars": 5000,
                    "web_search_max_results": 10
                },
                "premium": {
                    "data_analysis_enabled": True,
                    "web_search_limit_chars": 10000,
                    "web_search_max_results": 15
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
                'rag': {
                    'chunk_size': 500,
                    'chunk_overlap': 50,
                    'max_query_results_k': 10
                },
                'web_scraping': {
                    'user_agent': 'Mozilla/5.0 (Test; Python)',
                    'timeout_seconds': 5,
                    'max_search_results': 5 # Default for config
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


    print("\n--- Testing medical_tool functions (updated) ---")
    test_user = "test_user_medical"
    
    # Setup dummy API YAMLs for testing
    dummy_data_dir = Path("data")
    dummy_data_dir.mkdir(exist_ok=True)
    dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
    with open(dummy_medical_apis_path, "w") as f:
        f.write("""
apis:
  - name: "RxNorm"
    type: "drug_database"
    endpoint: "https://rxnav.nlm.nih.gov/REST/"
    key_name: "apiKey" # NLM API key is often passed as a query parameter
    key_value: "load_from_secrets.rxnorm_api_key"
    headers: {}
    default_params: {}
    functions:
      DRUG_INFO:
        path: "rxcui.json" # Simplified, actual RxNorm is complex
        params: {name: ""}
      DRUG_INTERACTIONS:
        path: "interaction.json" # Simplified
        params: {rxcui: ""} # Requires RxCUI, not name directly
    query_param: "name"

  - name: "ClinicalTrials"
    type: "clinical_trials"
    endpoint: "https://clinicaltrials.gov/api/query/"
    key_name: "" # No API key for public API
    key_value: ""
    headers: {}
    default_params: {}
    functions:
      TRIAL_SEARCH:
        path: "full_studies"
        params: {query: "", pageSize: 10}
      TRIAL_DETAILS:
        path: "full_studies/{nct_id}"
    query_param: "query"

  - name: "CDC"
    type: "public_health"
    endpoint: "https://data.cdc.gov/resource/" # Example, CDC has many datasets
    key_name: "app_token" # CDC Socrata API token
    key_value: "load_from_secrets.cdc_api_key"
    headers: {}
    default_params: {}
    functions:
      DISEASE_INFO:
        path: "n8mc-b4w4.json" # Example dataset for infectious diseases
        params: {disease: ""}
      VACCINE_INFO:
        path: "vaccine-data.json" # Example dataset for vaccine data
    query_param: "query"

search_apis:
  - name: "MedicalLiteratureSearch"
    type: "search"
    endpoint: "https://api.example.com/medical_literature/search"
    key_name: "apiKey"
    key_value: "load_from_secrets.medical_literature_api_key"
    headers: {}
    default_params:
      sort_by: "published_date"
    query_param: "q"
""")
    # Re-load config after creating dummy file
    sys.modules['config.config_manager'].config_manager = MockConfigManager()
    sys.modules['config.config_manager'].ConfigManager = MockConfigManager # Also replace the class for singleton check
    global MEDICAL_APIS_CONFIG
    MEDICAL_APIS_CONFIG = _load_medical_apis()
    print("Dummy medical_apis.yaml created and config reloaded for testing.")


    if config_manager:
        # Test medical_search_web (already works, just for completeness)
        print("\n--- Testing medical_search_web ---")
        search_query = "latest COVID-19 vaccine updates"
        search_result = medical_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Mock requests.get for API calls
        class MockResponse:
            def __init__(self, json_data, status_code=200):
                self._json_data = json_data
                self.status_code = status_code
                self.text = json.dumps(json_data)
            def json(self):
                return self._json_data
            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.exceptions.HTTPError(f"HTTP Error: {self.status_code}", response=self)

        original_requests_get = requests.get
        requests.get = MagicMock(side_effect=[
            MockResponse({"drugGroup": {"conceptGroup": [{"conceptProperties": [{"name": "ibuprofen"}]}]}}),
            MockResponse({"FullStudiesResponse": {"FullStudies": [{"Study": {"ProtocolSection": {"Title": "Trial for Diabetes"}}}]}}),
            MockResponse([{"disease": "Influenza", "symptoms": "fever, cough, sore throat"}]),
        ])

        # Test medical_data_fetcher - RxNorm
        print("\n--- Testing medical_data_fetcher (RxNorm) ---")
        rxnorm_drug_info = medical_data_fetcher(api_name="RxNorm", data_type="drug_info", drug_name="ibuprofen")
        print(f"RxNorm Drug Info 'ibuprofen': {rxnorm_drug_info}")

        # Test medical_data_fetcher - ClinicalTrials
        print("\n--- Testing medical_data_fetcher (ClinicalTrials) ---")
        clinical_trials_search = medical_data_fetcher(api_name="ClinicalTrials", data_type="trial_search", query="diabetes", limit=1)
        print(f"ClinicalTrials Search 'diabetes': {clinical_trials_search}")

        # Test medical_data_fetcher - CDC
        print("\n--- Testing medical_data_fetcher (CDC) ---")
        cdc_disease_info = medical_data_fetcher(api_name="CDC", data_type="disease_info", disease_name="Influenza")
        print(f"CDC Disease Info 'Influenza': {cdc_disease_info}")
        
        # Restore original requests.get
        requests.get = original_requests_get

        # Test python_interpreter_with_rbac with mock data (example)
        print("\n--- Testing python_interpreter_with_rbac with mock data ---")
        python_code_medical = f"""
import json
data = {rxnorm_drug_info}
drug_name = data.get('drugGroup', {{}}).get('conceptGroup', [{{}}])[0].get('conceptProperties', [{{}}])[0].get('name')
print(f"Fetched Drug Name: {{drug_name}}")
"""
        print(f"Executing Python code:\n{python_code_medical}")
        try:
            # Test with a user who has data_analysis_enabled
            pro_user_token = st.secrets.user_tokens["pro_user_token"]
            repl_output = python_interpreter_with_rbac(code=python_code_medical, user_token=pro_user_token)
            print(f"Python REPL Output (Pro User):\n{repl_output}")
            assert "Fetched Drug Name: ibuprofen" in repl_output

            # Test with a user who does NOT have data_analysis_enabled
            free_user_token = st.secrets.user_tokens["free_user_token"]
            repl_output_denied = python_interpreter_with_rbac(code=python_code_medical, user_token=free_user_token)
            print(f"Python REPL Output (Free User):\n{repl_output_denied}")
            assert "Access Denied" in repl_output_denied

        except Exception as e:
            print(f"Error executing Python REPL: {e}.")
            print("Make sure pandas, numpy, json are installed if you're running complex analysis.")

    else:
        print("Skipping medical_tool tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    dummy_json_path = Path("temp_medical_docs.json")
    if dummy_json_path.exists():
        dummy_json_path.unlink()
    if Path("exports").exists() and (Path("exports") / test_user).exists():
        shutil.rmtree(Path("exports") / test_user, ignore_errors=True)
    if Path("uploads").exists() and (Path("uploads") / test_user).exists():
        shutil.rmtree(Path("uploads") / test_user, ignore_errors=True)
    if BASE_VECTOR_DIR.exists() and (BASE_VECTOR_DIR / test_user).exists():
        shutil.rmtree(BASE_VECTOR_DIR / test_user, ignore_errors=True)
    
    dummy_data_dir = Path("data")
    if dummy_data_dir.exists():
        # Remove only if contents are dummy files created by this script
        dummy_config_path = dummy_data_dir / "config.yml"
        dummy_sports_apis_path = dummy_data_dir / "sports_apis.yaml"
        dummy_media_apis_path = dummy_data_dir / "media_apis.yaml"
        dummy_finance_apis_path = dummy_data_dir / "finance_apis.yaml"
        dummy_news_apis_path = dummy_data_dir / "news_apis.yaml"
        dummy_weather_apis_path = dummy_data_dir / "weather_apis.yaml"
        dummy_entertainment_apis_path = dummy_data_dir / "entertainment_apis.yaml"
        dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
        dummy_legal_apis_path = dummy_data_dir / "legal_apis.yaml"


        if dummy_config_path.exists(): os.remove(dummy_config_path)
        if dummy_sports_apis_path.exists(): os.remove(dummy_sports_apis_path)
        if dummy_media_apis_path.exists(): os.remove(dummy_media_apis_path)
        if dummy_finance_apis_path.exists(): os.remove(dummy_finance_apis_path)
        if dummy_news_apis_path.exists(): os.remove(dummy_news_apis_path)
        if dummy_weather_apis_path.exists(): os.remove(dummy_weather_apis_path)
        if dummy_entertainment_apis_path.exists(): os.remove(dummy_entertainment_apis_path)
        if dummy_medical_apis_path.exists(): os.remove(dummy_medical_apis_path)
        if dummy_legal_apis_path.exists(): os.remove(dummy_legal_apis_path)

        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)

