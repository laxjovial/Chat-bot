# legal_tools/legal_tool.py

import requests
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import yaml # Added for loading legal_apis.yaml

# Import generic tools
from langchain_core.tools import tool
from shared_tools.query_uploaded_docs_tool import QueryUploadedDocs
from shared_tools.scraper_tool import scrape_web
from shared_tools.doc_summarizer import summarize_document
from shared_tools.import_utils import process_upload, clear_indexed_data # Used by Streamlit apps, not directly as agent tools
from shared_tools.export_utils import export_response, export_vector_results # To be used internally by other tools, or for direct exports
from shared_tools.vector_utils import build_vectorstore, load_docs_from_json_file, BASE_VECTOR_DIR # For testing and potential future direct use

# Import Python REPL for data analysis capabilities
from langchain_community.tools.python.tool import PythonREPLTool

# Import config_manager to access API configurations
from config.config_manager import config_manager

# Constants for the legal section
LEGAL_SECTION = "legal"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

logger = logging.getLogger(__name__)

@tool
def legal_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 2000) -> str:
    """
    Searches the web for legal information, news, or general legal topics using a smart search fallback mechanism.
    This tool wraps the generic `scrape_web` tool, providing a legal-specific interface.
    
    Args:
        query (str): The legal-related search query (e.g., "recent supreme court rulings", "intellectual property law changes").
        user_token (str): The unique identifier for the user. Defaults to "default".
        max_chars (int): Maximum characters for the returned snippet. Defaults to 2000.
    
    Returns:
        str: A string containing relevant information from the web.
    """
    logger.info(f"Tool: legal_search_web called with query: '{query}' for user: '{user_token}'")
    return scrape_web(query=query, user_token=user_token, max_chars=max_chars)

@tool
def legal_query_uploaded_docs(query: str, user_token: str = DEFAULT_USER_TOKEN, export: Optional[bool] = False, k: int = 5) -> str:
    """
    Queries previously uploaded and indexed legal documents for a user using vector similarity search.
    This tool wraps the generic `QueryUploadedDocs` tool, fixing the section to "legal".
    
    Args:
        query (str): The search query to find relevant legal documents (e.g., "what does clause 7.2 mean in my contract", "summary of the case brief I uploaded").
        user_token (str): The unique identifier for the user. Defaults to "default".
        export (bool): If True, the results will be saved to a file in markdown format. Defaults to False.
        k (int): The number of top relevant documents to retrieve. Defaults to 5.
    
    Returns:
        str: A string containing the combined content of the relevant document chunks,
             or a message indicating no data/results found, or the export path if exported.
    """
    logger.info(f"Tool: legal_query_uploaded_docs called with query: '{query}' for user: '{user_token}'")
    return QueryUploadedDocs(query=query, user_token=user_token, section=LEGAL_SECTION, export=export, k=k)

@tool
def legal_summarize_document_by_path(file_path_str: str) -> str:
    """
    Summarizes a document related to legal topics located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    This tool wraps the generic `summarize_document` tool.
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/legal/court_ruling.pdf"
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: legal_summarize_document_by_path called for file: '{file_path_str}'")
    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.error(f"Document not found at '{file_path_str}' for summarization.")
        return f"Error: Document not found at '{file_path_str}'."
    
    try:
        summary = summarize_document(file_path)
        return f"Summary of '{file_path.name}':\n{summary}"
    except ValueError as e:
        logger.error(f"Error summarizing document '{file_path_str}': {e}")
        return f"Error summarizing document: {e}"
    except Exception as e:
        logger.critical(f"An unexpected error occurred during summarization of '{file_path_str}': {e}", exc_info=True)
        return f"An unexpected error occurred during summarization: {e}"

# === Advanced Legal Tools ===

# Initialize the Python REPL tool.
python_repl = PythonREPLTool()
python_repl.name = "python_interpreter"
python_repl.description = """
Executes Python code. Use this for complex data analysis, calculations, or any task that requires programmatic logic
on structured legal data (e.g., analyzing patterns in case outcomes, processing large legal datasets).
Input should be a valid Python code string.
The output will be the result of the code execution (stdout/stderr).
You have access to common libraries like pandas, numpy, matplotlib, datetime, json, etc.
Example:
Action: python_interpreter
Action Input:
import json
data = json.loads(tool_output) # Assuming tool_output from legal_data_fetcher
case_names = [item['case_name'] for item in data if 'case_name' in item]
print(f"Cases fetched: {', '.join(case_names)}")
"""

# Helper to load API configs
def _load_legal_apis() -> Dict[str, Any]:
    """Loads legal API configurations from data/legal_apis.yaml."""
    legal_apis_path = Path("data/legal_apis.yaml")
    if not legal_apis_path.exists():
        logger.warning(f"data/legal_apis.yaml not found at {legal_apis_path}")
        return {}
    try:
        with open(legal_apis_path, "r") as f:
            full_config = yaml.safe_load(f) or {}
            return {api['name']: api for api in full_config.get('apis', [])}
    except Exception as e:
        logger.error(f"Error loading legal_apis.yaml: {e}")
        return {}

LEGAL_APIS_CONFIG = _load_legal_apis()

@tool
def legal_data_fetcher(
    api_name: str,
    data_type: str, # e.g., "case_law_search", "statute_lookup", "regulation_search", "legal_news"
    query: Optional[str] = None, # For search queries (e.g., case name, keyword)
    jurisdiction: Optional[str] = None, # e.g., "US Federal", "California", "UK"
    year: Optional[int] = None, # For specific year of case/statute
    limit: Optional[int] = None # For number of results
) -> str:
    """
    Fetches legal data from configured APIs.
    This is a placeholder and needs actual implementation to connect to APIs
    like legal research databases (e.g., Fastcase, LexisNexis, Westlaw - often proprietary/expensive),
    or public legal data sources.
    
    Args:
        api_name (str): The name of the API to use (e.g., "LegalDB", "GovLawAPI").
                        This must match a 'name' field in data/legal_apis.yaml.
        data_type (str): The type of data to fetch (e.g., "case_law_search", "statute_lookup", "regulation_search", "legal_news").
        query (str, optional): A search query for case names, statute titles, or keywords.
        jurisdiction (str, optional): The legal jurisdiction (e.g., "US Federal", "California", "UK").
        year (int, optional): Specific year for filtering results.
        limit (int, optional): Maximum number of records to return.
        
    Returns:
        str: A JSON string of the fetched data or an error message.
             The agent can then use `python_interpreter` to parse and analyze this JSON.
    """
    logger.info(f"Tool: legal_data_fetcher called for API: {api_name}, data_type: {data_type}, query: '{query}', jurisdiction: '{jurisdiction}'")

    api_info = LEGAL_APIS_CONFIG.get(api_name)
    if not api_info:
        return f"Error: API '{api_name}' not found in data/legal_apis.yaml configuration."

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
    
    if key_name and api_key:
        if key_name.lower() == "authorization": # Handle Bearer tokens
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            default_params[key_name] = api_key
    elif key_name and not api_key:
        logger.warning(f"API key for '{api_name}' not found in secrets.toml. Proceeding without key if API allows.")

    params = {**default_params} # Start with default parameters
    url = endpoint

    try:
        # --- Placeholder/Mock Implementations ---
        if api_name == "LegalDB":
            if data_type == "case_law_search":
                return json.dumps([
                    {"case_name": f"Mock Case {query}", "citation": "123 F.3d 456", "year": year if year else "2023", "jurisdiction": jurisdiction if jurisdiction else "US Federal", "summary": "This is a mock summary of a legal case."},
                    {"case_name": "Another Mock Ruling", "citation": "789 S.Ct. 1011", "year": year if year else "2022", "jurisdiction": jurisdiction if jurisdiction else "US Federal", "summary": "Another mock summary of a legal ruling."}
                ][:limit if limit else 2])
            elif data_type == "statute_lookup":
                return json.dumps({"statute_title": f"Mock Statute: {query}", "citation": "18 U.S.C. § 123", "jurisdiction": jurisdiction if jurisdiction else "US Federal", "text_snippet": "This is a mock snippet of a legal statute text."})
            else:
                return f"Error: Unsupported data_type '{data_type}' for LegalDB."
        
        elif api_name == "GovLawAPI":
            if data_type == "regulation_search":
                return json.dumps([
                    {"regulation_title": f"Mock Regulation: {query}", "code": "40 CFR 123", "year": year if year else "2024", "jurisdiction": jurisdiction if jurisdiction else "US Federal", "summary": "This is a mock summary of a legal regulation."},
                ][:limit if limit else 1])
            else:
                return f"Error: Unsupported data_type '{data_type}' for GovLawAPI."

        else:
            return f"Error: API '{api_name}' is not supported by legal_data_fetcher."

    except requests.exceptions.RequestException as req_e:
        logger.error(f"API request failed for {api_name} ({data_type}): {req_e}")
        if hasattr(req_e, 'response') and req_e.response is not None:
            logger.error(f"Response content: {req_e.response.text}")
            return f"API request failed for {api_name}: {req_e.response.text}"
        return f"API request failed for {api_name}: {req_e}"
    except Exception as e:
        logger.error(f"Error processing {api_name} response or request setup: {e}", exc_info=True)
        return f"An unexpected error occurred: {e}"

@tool
def legal_term_explainer(term: str) -> str:
    """
    Explains a legal term in simple, understandable language.
    
    Args:
        term (str): The legal term to explain (e.g., "habeas corpus", "res judicata", "tort").
        
    Returns:
        str: A simplified explanation of the legal term.
    """
    logger.info(f"Tool: legal_term_explainer called for term: '{term}'")
    term_lower = term.lower()
    if "habeas corpus" in term_lower:
        return "**Habeas Corpus:** A legal writ (order) that requires a person under arrest to be brought before a judge or into court. The purpose is to ensure that a prisoner can be released from unlawful detention—that is, detention lacking sufficient cause or evidence."
    elif "res judicata" in term_lower:
        return "**Res Judicata:** Latin for 'a matter judged.' It's a legal principle that states once a final judgment has been made on a legal case, it cannot be litigated again between the same parties. It prevents relitigation of issues already decided."
    elif "tort" in term_lower:
        return "**Tort:** In common law jurisdictions, a tort is a civil wrong that causes a claimant to suffer loss or harm, resulting in legal liability for the person who commits the tortious act. Examples include negligence, trespass, and defamation."
    elif "stare decisis" in term_lower:
        return "**Stare Decisis:** Latin for 'to stand by things decided.' It's the legal principle by which judges are obliged to respect the precedents established by prior decisions. This means that once a court has made a decision on a particular legal issue, that decision should be followed in similar cases in the future."
    else:
        return f"I can explain common legal terms. Please provide a specific legal term for explanation."

@tool
def contract_analyzer(file_path_str: str, analysis_type: str = "summary") -> str:
    """
    Performs a basic analysis of a contract document (e.g., identifies parties, key clauses, obligations).
    **Disclaimer: This tool provides preliminary information and is NOT a substitute for professional legal advice. Always consult a qualified legal professional for contract review.**
    
    Args:
        file_path_str (str): The full path to the contract document file (e.g., "uploads/default/legal/employment_contract.pdf").
        analysis_type (str): The type of analysis to perform (e.g., "summary", "parties", "obligations", "termination_clauses"). Defaults to "summary".
        
    Returns:
        str: The result of the contract analysis.
    """
    logger.info(f"Tool: contract_analyzer called for file: '{file_path_str}', analysis_type: '{analysis_type}'")
    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.error(f"Document not found at '{file_path_str}' for contract analysis.")
        return f"Error: Document not found at '{file_path_str}'."
    
    # In a real scenario, this would involve:
    # 1. Loading the document content.
    # 2. Using an LLM or specialized NLP models fine-tuned for legal text to extract information.
    # 3. Potentially leveraging a structured parsing library.

    # For now, a mock response based on analysis_type
    mock_content_snippet = f"Mock analysis of '{file_path.name}' for {analysis_type}."
    
    if analysis_type == "summary":
        return f"""
        **Contract Summary for '{file_path.name}':**
        This is a mock summary. In a real scenario, this would provide a concise overview of the contract's purpose, key terms, and duration.
        
        **Disclaimer:** This tool provides preliminary information and is NOT a substitute for professional legal advice. Always consult a qualified legal professional for contract review.
        """
    elif analysis_type == "parties":
        return f"""
        **Parties Identified in '{file_path.name}':**
        - Party A: [Mock Name/Entity 1]
        - Party B: [Mock Name/Entity 2]
        
        **Disclaimer:** This tool provides preliminary information and is NOT a substitute for professional legal advice.
        """
    elif analysis_type == "obligations":
        return f"""
        **Key Obligations in '{file_path.name}':**
        - Party A: [Mock Obligation 1], [Mock Obligation 2]
        - Party B: [Mock Obligation 3], [Mock Obligation 4]
        
        **Disclaimer:** This tool provides preliminary information and is NOT a substitute for professional legal advice.
        """
    elif analysis_type == "termination_clauses":
        return f"""
        **Termination Clauses in '{file_path.name}':**
        - Clause 10.1: Termination for convenience with 30 days notice.
        - Clause 10.2: Termination for breach with cure period.
        
        **Disclaimer:** This tool provides preliminary information and is NOT a substitute for professional legal advice.
        """
    else:
        return f"Unsupported analysis type: '{analysis_type}'. Supported types are 'summary', 'parties', 'obligations', 'termination_clauses'."


# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import shutil
    import os
    from config.config_manager import ConfigManager # Import ConfigManager for testing setup
    from shared_tools.llm_embedding_utils import get_llm # For testing summarization with a real LLM

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Replace with a real key
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Replace with a real key
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # For scrape_web testing
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"} # For scrape_web testing
            self.legal_api_key = "YOUR_LEGAL_API_KEY" # Placeholder for a real legal API key

    try:
        # Create dummy config.yml
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
  chunk_size: 500
  chunk_overlap: 50
web_scraping:
  user_agent: Mozilla/5.0 (Test; Python)
  timeout_seconds: 5
""")
        # Create dummy API YAMLs for scraper_tool and legal_data_fetcher
        dummy_sports_apis_path = dummy_data_dir / "sports_apis.yaml"
        with open(dummy_sports_apis_path, "w") as f:
            f.write("""
search_apis:
  - name: "SerpAPI"
    type: "search"
    endpoint: "https://serpapi.com/search"
    key_name: "api_key"
    key_value: "load_from_secrets.serpapi_api_key"
    query_param: "q"
    default_params:
      engine: "google"
      num: 3
            """)
        dummy_media_apis_path = dummy_data_dir / "media_apis.yaml"
        with open(dummy_media_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
""")
        dummy_finance_apis_path = dummy_data_dir / "finance_apis.yaml"
        with open(dummy_finance_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
""")
        dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
        with open(dummy_medical_apis_path, "w") as f:
            f.write("""
apis: []
search_apis: []
""")
        dummy_legal_apis_path = dummy_data_dir / "legal_apis.yaml"
        with open(dummy_legal_apis_path, "w") as f:
            f.write("""
apis:
  - name: "LegalDB"
    type: "legal"
    endpoint: "https://api.example.com/legal/" # Placeholder
    key_name: "api_key"
    key_value: "load_from_secrets.legal_api_key"
    headers: {}
    default_params: {}
    functions:
      case_law_search: {path: "cases"}
      statute_lookup: {path: "statutes"}
    query_param: "q"

  - name: "GovLawAPI"
    type: "legal"
    endpoint: "https://api.example.com/govlaw/" # Placeholder
    key_name: "api_key"
    key_value: "load_from_secrets.govlaw_api_key"
    headers: {}
    default_params: {}
    functions:
      regulation_search: {path: "regulations"}
    query_param: "q"

search_apis: []
""")

        if not hasattr(st, 'secrets'):
            st.secrets = MockSecrets()
            print("Mocked st.secrets for standalone testing.")
        
        # Ensure config_manager is a fresh instance for this test run
        ConfigManager._instance = None # Reset the singleton
        ConfigManager._is_loaded = False
        config_manager = ConfigManager()
        print("ConfigManager initialized for testing.")

    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Skipping API/LLM-dependent tests.")
        config_manager = None

    print("\n--- Testing legal_tool functions ---")
    test_user = "test_user_legal"
    
    if config_manager:
        # Test legal_search_web
        print("\n--- Testing legal_search_web ---")
        search_query = "recent changes to privacy law"
        search_result = legal_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Prepare dummy data for legal_query_uploaded_docs
        print("\n--- Preparing dummy data for legal_query_uploaded_docs ---")
        dummy_json_path = Path("temp_legal_docs.json")
        dummy_data = [
            {"id": 1, "text": "This is a summary of the landmark case Roe v. Wade.", "category": "case_law"},
            {"id": 2, "text": "Notes on the General Data Protection Regulation (GDPR) and its implications.", "category": "regulation"},
            {"id": 3, "text": "My analysis of a specific employment contract clause.", "category": "contract"}
        ]
        with open(dummy_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f)
        
        # Load documents from the dummy JSON for build_vectorstore
        loaded_docs_for_vector = load_docs_from_json_file(dummy_json_path)
        for i, doc in enumerate(loaded_docs_for_vector):
            doc.page_content = dummy_data[i]["text"]

        build_vectorstore(test_user, LEGAL_SECTION, loaded_docs_for_vector, chunk_size=200, chunk_overlap=0)
        print(f"Vectorstore built for {LEGAL_SECTION}.")

        # Test legal_query_uploaded_docs
        print("\n--- Testing legal_query_uploaded_docs ---")
        doc_query = "What did I upload about GDPR?"
        doc_results = legal_query_uploaded_docs(doc_query, user_token=test_user)
        print(f"Query uploaded docs for '{doc_query}':\n{doc_results}")

        # Test legal_summarize_document_by_path
        print("\n--- Testing legal_summarize_document_by_path ---")
        # Create a dummy upload directory and file
        test_upload_dir = Path("uploads") / test_user / LEGAL_SECTION
        test_upload_dir.mkdir(parents=True, exist_ok=True)
        summarize_file_path = test_upload_dir / "legal_brief.txt"
        with open(summarize_file_path, "w") as f:
            f.write("This legal brief argues for the plaintiff's position based on precedent and statutory interpretation. " * 30 + 
                    "It cites several key cases and outlines the legal arguments in detail. " * 20 +
                    "The defense's counter-arguments are also addressed and refuted." * 25)
        print(f"Created dummy file for summarization: {summarize_file_path}")

        summary_result = legal_summarize_document_by_path(str(summarize_file_path))
        print(summary_result)

        # Test legal_data_fetcher (mocked)
        print("\n--- Testing legal_data_fetcher (mocked) ---")
        case_search = legal_data_fetcher(api_name="LegalDB", data_type="case_law_search", query="privacy", jurisdiction="California")
        print(f"Case Search (mocked): {case_search}")
        statute_lookup = legal_data_fetcher(api_name="LegalDB", data_type="statute_lookup", query="data security")
        print(f"Statute Lookup (mocked): {statute_lookup}")

        # Test legal_term_explainer
        print("\n--- Testing legal_term_explainer ---")
        term_explanation = legal_term_explainer("stare decisis")
        print(f"Explanation of 'stare decisis':\n{term_explanation}")
        term_explanation2 = legal_term_explainer("tort")
        print(f"Explanation of 'tort':\n{term_explanation2}")

        # Test contract_analyzer (mocked)
        print("\n--- Testing contract_analyzer (mocked) ---")
        contract_file_path = str(test_upload_dir / "employment_contract.pdf") # Mock path
        with open(contract_file_path, "w") as f: # Create a dummy file for the tool to 'find'
            f.write("This is a mock employment contract content.")
        
        contract_summary = contract_analyzer(contract_file_path, analysis_type="summary")
        print(f"Contract Summary:\n{contract_summary}")
        contract_parties = contract_analyzer(contract_file_path, analysis_type="parties")
        print(f"Contract Parties:\n{contract_parties}")

        # Test python_interpreter (example with mock data)
        print("\n--- Testing python_interpreter with mock data ---")
        python_code_legal_data = """
import json
import pandas as pd
mock_legal_data = '''[
    {"case_id": "C001", "year": 2020, "outcome": "Plaintiff"},
    {"case_id": "C002", "year": 2021, "outcome": "Defendant"},
    {"case_id": "C003", "year": 2020, "outcome": "Plaintiff"},
    {"case_id": "C004", "year": 2022, "outcome": "Settled"}
]'''
df = pd.DataFrame(json.loads(mock_legal_data))
outcome_counts = df['outcome'].value_counts()
print(f"Case outcomes:\n{outcome_counts}")
"""
        print(f"Executing Python code:\n{python_code_legal_data}")
        try:
            repl_output = python_repl.run(python_code_legal_data)
            print(f"Python REPL Output:\n{repl_output}")
        except Exception as e:
            print(f"Error executing Python REPL: {e}. Make sure pandas, numpy, json are installed.")


    else:
        print("Skipping legal_tool tests due to ConfigManager issues or missing API keys.")

    # Clean up dummy files and directories
    dummy_json_path = Path("temp_legal_docs.json")
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
        dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
        dummy_legal_apis_path = dummy_data_dir / "legal_apis.yaml"

        if dummy_config_path.exists(): os.remove(dummy_config_path)
        if dummy_sports_apis_path.exists(): os.remove(dummy_sports_apis_path)
        if dummy_media_apis_path.exists(): os.remove(dummy_media_apis_path)
        if dummy_finance_apis_path.exists(): os.remove(dummy_finance_apis_path)
        if dummy_medical_apis_path.exists(): os.remove(dummy_medical_apis_path)
        if dummy_legal_apis_path.exists(): os.remove(dummy_legal_apis_path)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
