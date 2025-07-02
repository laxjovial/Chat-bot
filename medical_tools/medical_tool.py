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

# Import Python REPL for data analysis capabilities
from langchain_community.tools.python.tool import PythonREPLTool

# Import config_manager to access API configurations
from config.config_manager import config_manager

# Constants for the medical/health section
MEDICAL_SECTION = "medical"
DEFAULT_USER_TOKEN = "default" # Or use a proper user management if available

logger = logging.getLogger(__name__)

@tool
def medical_search_web(query: str, user_token: str = DEFAULT_USER_TOKEN, max_chars: int = 2000) -> str:
    """
    Searches the web for medical, health, or life-based information using a smart search fallback mechanism.
    This tool wraps the generic `scrape_web` tool, providing a medical-specific interface.
    
    Args:
        query (str): The medical/health-related search query (e.g., "latest cancer research", "benefits of meditation", "how to improve sleep").
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
    Queries previously uploaded and indexed medical/health documents for a user using vector similarity search.
    This tool wraps the generic `QueryUploadedDocs` tool, fixing the section to "medical".
    
    Args:
        query (str): The search query to find relevant medical documents (e.g., "my blood test results explanation", "summary of the medical journal article I uploaded").
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
    Summarizes a document related to medical/health located at the given file path.
    The file path should be accessible by the system (e.g., in the 'uploads' directory).
    This tool wraps the generic `summarize_document` tool.
    
    Args:
        file_path_str (str): The full path to the document file to be summarized.
                              Example: "uploads/default/medical/patient_report.pdf"
    
    Returns:
        str: A concise summary of the document content.
    """
    logger.info(f"Tool: medical_summarize_document_by_path called for file: '{file_path_str}'")
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

# === Advanced Medical/Health Tools ===

# Initialize the Python REPL tool.
python_repl = PythonREPLTool()
python_repl.name = "python_interpreter"
python_repl.description = """
Executes Python code. Use this for complex data analysis, calculations, or any task that requires programmatic logic
on structured health data (e.g., analyzing patient demographics, epidemiological statistics).
Input should be a valid Python code string.
The output will be the result of the code execution (stdout/stderr).
You have access to common libraries like pandas, numpy, matplotlib, datetime, json, etc.
Example:
Action: python_interpreter
Action Input:
import json
data = json.loads(tool_output) # Assuming tool_output from a health data fetcher
avg_age = sum(item['age'] for item in data if 'age' in item) / len(data)
print(f"Average patient age: {avg_age}")
"""

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
    data_type: str, # e.g., "symptoms_list", "conditions_list", "news_articles", "emergency_services"
    query: Optional[str] = None, # For search queries
    location: Optional[str] = None, # For location-based services (e.g., "London", "near me")
    symptoms: Optional[str] = None, # Comma-separated symptoms for symptom checker
    limit: Optional[int] = None # For number of results
) -> str:
    """
    Fetches medical and health-related data from configured APIs.
    This is a placeholder and needs actual implementation to connect to APIs
    like medical knowledge bases, news APIs, or mapping APIs.
    
    Args:
        api_name (str): The name of the API to use (e.g., "HealthAPI", "WHO_API", "GoogleMapsAPI").
                        This must match a 'name' field in data/medical_apis.yaml.
        data_type (str): The type of data to fetch (e.g., "symptoms_list", "conditions_list", "news_articles", "emergency_services").
        query (str, optional): A search query for news, articles, or general information.
        location (str, optional): A location string (e.g., "London", "my current location") for services like emergency locator.
        symptoms (str, optional): Comma-separated list of symptoms (e.g., "fever,cough") for symptom checking.
        limit (int, optional): Maximum number of records to return.
        
    Returns:
        str: A JSON string of the fetched data or an error message.
             The agent can then use `python_interpreter` to parse and analyze this JSON.
    """
    logger.info(f"Tool: medical_data_fetcher called for API: {api_name}, data_type: {data_type}, query: '{query}', location: '{location}', symptoms: '{symptoms}'")

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
        if api_name == "HealthAPI":
            if data_type == "symptoms_list":
                return json.dumps({"symptoms": ["fever", "cough", "headache", "fatigue", "sore throat"]})
            elif data_type == "conditions_list":
                return json.dumps({"conditions": ["common cold", "influenza", "strep throat", "allergies"]})
            elif data_type == "symptom_checker":
                if symptoms:
                    symptoms_list = [s.strip().lower() for s in symptoms.split(',')]
                    if "fever" in symptoms_list and "cough" in symptoms_list:
                        return json.dumps({"possible_conditions": ["Common Cold", "Influenza"], "disclaimer": "Consult a doctor for accurate diagnosis."})
                    elif "headache" in symptoms_list and "fatigue" in symptoms_list:
                        return json.dumps({"possible_conditions": ["Stress", "Dehydration"], "disclaimer": "Consult a doctor for accurate diagnosis."})
                    else:
                        return json.dumps({"possible_conditions": ["Further investigation needed"], "disclaimer": "Consult a doctor for accurate diagnosis."})
                return "Error: 'symptoms' required for symptom_checker."
            else:
                return f"Error: Unsupported data_type '{data_type}' for HealthAPI."
        
        elif api_name == "WHO_API":
            if data_type == "world_health_updates":
                # Mock data for world health updates
                return json.dumps([
                    {"date": "2024-07-01", "title": "WHO issues new guidelines on pandemic preparedness.", "source": "WHO"},
                    {"date": "2024-06-25", "title": "Global measles cases show slight increase in Q2.", "source": "WHO Report"}
                ])
            else:
                return f"Error: Unsupported data_type '{data_type}' for WHO_API."

        elif api_name == "GoogleMapsAPI":
            if data_type == "emergency_services":
                if not location: return "Error: 'location' is required for GoogleMapsAPI emergency_services."
                # This would typically call a Google Maps Places API or similar
                return json.dumps([
                    {"name": "Nearest Hospital", "address": f"123 Health St, {location}", "type": "Hospital", "distance": "2.5 km"},
                    {"name": "Emergency Clinic", "address": f"456 Care Ave, {location}", "type": "Clinic", "distance": "5.0 km"}
                ])
            else:
                return f"Error: Unsupported data_type '{data_type}' for GoogleMapsAPI."

        else:
            return f"Error: API '{api_name}' is not supported by medical_data_fetcher."

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
def first_aid_instructions(condition: str) -> str:
    """
    Provides basic first aid instructions for common medical conditions or injuries.
    
    Args:
        condition (str): The medical condition or injury for which to provide first aid (e.g., "cuts", "burns", "choking", "sprain").
        
    Returns:
        str: Step-by-step first aid instructions.
    """
    logger.info(f"Tool: first_aid_instructions called for condition: '{condition}'")
    condition_lower = condition.lower()
    if "cut" in condition_lower:
        return """
        **First Aid for Minor Cuts:**
        1. **Wash hands:** Before treating the cut.
        2. **Stop the bleeding:** Apply gentle pressure with a clean cloth or bandage for a few minutes.
        3. **Clean the wound:** Rinse with clean water. Use mild soap if available. Remove any dirt or debris.
        4. **Apply antibiotic ointment:** A thin layer can help keep the wound moist and prevent infection.
        5. **Cover the wound:** Use a sterile bandage. Change daily or if it gets wet/dirty.
        6. **Seek medical attention** if bleeding is severe, the cut is deep, or signs of infection appear.
        """
    elif "burn" in condition_lower:
        return """
        **First Aid for Minor Burns (First-degree or small Second-degree):**
        1. **Cool the burn:** Hold the burned area under cool (not cold) running water for 10-20 minutes. Do NOT use ice.
        2. **Remove jewelry/tight clothing:** Do this quickly before swelling begins.
        3. **Cover the burn:** Loosely cover with a sterile, non-adhesive bandage or clean cloth.
        4. **Do NOT break blisters:** If blisters form, leave them intact to prevent infection.
        5. **Seek medical attention** for larger burns, deep burns, or burns on face, hands, feet, or genitals.
        """
    elif "choking" in condition_lower:
        return """
        **First Aid for Choking (Adult/Child - Conscious):**
        1. **Encourage coughing:** If the person can cough, encourage them to keep coughing.
        2. **5 Back Blows:** If coughing doesn't work, stand behind the person, lean them forward, and deliver 5 sharp blows between their shoulder blades with the heel of your hand.
        3. **5 Abdominal Thrusts (Heimlich Maneuver):** If back blows don't work, stand behind the person, wrap your arms around their waist, make a fist with one hand just above their navel, grasp your fist with your other hand, and deliver 5 quick, upward thrusts.
        4. **Repeat:** Continue alternating 5 back blows and 5 abdominal thrusts until the object is dislodged or the person becomes unconscious.
        5. **Call emergency services immediately** if the person cannot breathe, speak, or becomes unconscious.
        """
    elif "sprain" in condition_lower:
        return """
        **First Aid for Sprains (R.I.C.E. method):**
        1. **Rest:** Rest the injured area. Avoid activities that cause pain.
        2. **Ice:** Apply an ice pack (wrapped in a cloth) to the injured area for 15-20 minutes every 2-3 hours.
        3. **Compression:** Wrap the injured area with an elastic bandage to help reduce swelling. Do not wrap too tightly.
        4. **Elevation:** Elevate the injured limb above the level of the heart to help reduce swelling.
        5. **Seek medical attention** if pain is severe, you can't bear weight, or swelling/bruising is significant.
        """
    else:
        return f"I can provide basic first aid for common conditions like 'cuts', 'burns', 'choking', or 'sprains'. Please specify one of these or a similar common injury."

@tool
def health_tip_generator(topic: Optional[str] = "general") -> str:
    """
    Generates a helpful health tip on a specified topic or a general health tip.
    
    Args:
        topic (str, optional): The topic for the health tip (e.g., "sleep", "nutrition", "exercise", "mental health"). Defaults to "general".
        
    Returns:
        str: A concise and actionable health tip.
    """
    logger.info(f"Tool: health_tip_generator called for topic: '{topic}'")
    topic_lower = topic.lower()
    if "sleep" in topic_lower:
        return "Aim for 7-9 hours of quality sleep per night. Establish a consistent sleep schedule, even on weekends, and create a relaxing bedtime routine."
    elif "nutrition" in topic_lower or "diet" in topic_lower:
        return "Focus on a balanced diet rich in fruits, vegetables, whole grains, and lean proteins. Limit processed foods, sugary drinks, and unhealthy fats."
    elif "exercise" in topic_lower or "fitness" in topic_lower:
        return "Engage in at least 150 minutes of moderate-intensity aerobic activity or 75 minutes of vigorous-intensity activity per week, along with muscle-strengthening activities twice a week."
    elif "mental health" in topic_lower or "stress" in topic_lower:
        return "Practice mindfulness or meditation for a few minutes each day. Stay connected with loved ones, engage in hobbies, and don't hesitate to seek professional help if needed."
    elif "hydration" in topic_lower or "water" in topic_lower:
        return "Drink plenty of water throughout the day. Staying well-hydrated is crucial for energy levels, skin health, and overall bodily functions."
    else:
        return "For general well-being, remember to stay hydrated, get regular physical activity, eat a balanced diet, and prioritize mental health. Small changes can lead to big improvements!"

# Note: Symptom checker and basic diagnosis are complex and require robust medical knowledge bases.
# These are simplified placeholders. For a real application, consider integrating with
# specialized medical APIs (e.g., Infermedica, Mayo Clinic APIs if available).
@tool
def symptom_checker(symptoms: str) -> str:
    """
    Provides a preliminary check for possible conditions based on a list of symptoms.
    **Disclaimer: This tool provides general information and is NOT a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider for any health concerns.**
    
    Args:
        symptoms (str): A comma-separated list of symptoms (e.g., "fever,cough,sore throat").
        
    Returns:
        str: A list of possible conditions and a strong disclaimer.
    """
    logger.info(f"Tool: symptom_checker called with symptoms: '{symptoms}'")
    # This calls the medical_data_fetcher with a specific data_type for symptom checking
    return medical_data_fetcher(api_name="HealthAPI", data_type="symptom_checker", symptoms=symptoms)

@tool
def basic_diagnosis(symptoms: str) -> str:
    """
    Attempts a very basic, preliminary diagnosis based on provided symptoms.
    **Disclaimer: This tool provides general information and is NOT a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider for any health concerns.**
    
    Args:
        symptoms (str): A comma-separated list of symptoms (e.g., "headache,nausea,dizziness").
        
    Returns:
        str: A preliminary diagnosis and a strong disclaimer.
    """
    logger.info(f"Tool: basic_diagnosis called with symptoms: '{symptoms}'")
    # This is a simplified version; in a real scenario, it would be more complex
    # and potentially leverage an LLM with a medical context or a dedicated API.
    symptoms_list = [s.strip().lower() for s in symptoms.split(',')]
    
    diagnosis = "Uncertain. More information or professional medical consultation is needed."
    if "fever" in symptoms_list and "cough" in symptoms_list and "sore throat" in symptoms_list:
        diagnosis = "Possible common cold or influenza."
    elif "chest pain" in symptoms_list and "shortness of breath" in symptoms_list:
        diagnosis = "Potentially serious. Seek immediate medical attention."
    elif "headache" in symptoms_list and "stiff neck" in symptoms_list and "fever" in symptoms_list:
        diagnosis = "Possible meningitis. Seek immediate medical attention."
    
    return f"""
    **Preliminary Indication:** {diagnosis}
    
    **IMPORTANT DISCLAIMER:** This information is for general knowledge and informational purposes only, and does not constitute medical advice. It is NOT a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition. Never disregard professional medical advice or delay in seeking it because of something you have read here. In case of a medical emergency, call your local emergency services immediately.
    """

@tool
def emergency_locator(location: str) -> str:
    """
    Finds nearby emergency services (hospitals, clinics) based on a specified location.
    
    Args:
        location (str): The location to search around (e.g., "London", "my current location", "123 Main St, Anytown").
        
    Returns:
        str: A list of nearby emergency services with addresses and types, or an error message.
    """
    logger.info(f"Tool: emergency_locator called for location: '{location}'")
    # This calls the medical_data_fetcher with a specific data_type for emergency services
    return medical_data_fetcher(api_name="GoogleMapsAPI", data_type="emergency_services", location=location)

@tool
def world_health_updates() -> str:
    """
    Fetches recent global health news and updates from sources like WHO.
    
    Returns:
        str: A summary of recent world health updates.
    """
    logger.info(f"Tool: world_health_updates called.")
    # This calls the medical_data_fetcher with a specific data_type for world health updates
    return medical_data_fetcher(api_name="WHO_API", data_type="world_health_updates")


# CLI Test (optional)
if __name__ == "__main__":
    import streamlit as st
    import shutil
    import os
    from config.config_manager import ConfigManager # Import ConfigManager for testing setup
    from shared_tools.llm_embedding_utils import get_llm # For testing summarization with a real LLM

    logging.basicConfig(level=logging.INFO)

    # Mock Streamlit secrets and config for local testing if needed
    class MockSecrets:
        def __init__(self):
            self.openai = {"api_key": "sk-mock-openai-key-12345"} # Replace with a real key
            self.google = {"api_key": "AIzaSy-mock-google-key"} # Replace with a real key
            self.ollama = {"api_url": "http://localhost:11434", "model": "llama3"}
            self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} # For scrape_web testing
            self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"} # For scrape_web testing
            self.alphavantage_api_key = "YOUR_ALPHAVANTAGE_API_KEY"
            self.coingecko_api_key = "YOUR_COINGECKO_API_KEY"
            self.exchangerate_api_key = "YOUR_EXCHANGERATE_API_KEY"
            self.themoviedb_api_key = "YOUR_THEMOVIEDB_API_KEY"
            self.omdbapi_api_key = "YOUR_OMDBAPI_API_KEY"
            self.health_api_key = "YOUR_HEALTH_API_KEY" # Placeholder for a real health API key
            self.who_api_key = "YOUR_WHO_API_KEY" # Placeholder for a real WHO API key
            self.google_maps_api_key = "YOUR_GOOGLE_MAPS_API_KEY" # Placeholder for Google Maps API key

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
        # Create dummy API YAMLs for scraper_tool and medical_data_fetcher
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
apis:
  - name: "HealthAPI"
    type: "medical"
    endpoint: "https://api.example.com/health/" # Placeholder
    key_name: "api_key"
    key_value: "load_from_secrets.health_api_key"
    headers: {}
    default_params: {}
    functions:
      symptoms_list: {path: "symptoms"}
      conditions_list: {path: "conditions"}
      symptom_checker: {path: "symptom_check"}
    query_param: "q"

  - name: "WHO_API"
    type: "medical"
    endpoint: "https://api.who.int/data/v1/" # Placeholder
    key_name: "api_key"
    key_value: "load_from_secrets.who_api_key"
    headers: {}
    default_params: {}
    functions:
      world_health_updates: {path: "news"}
    query_param: "q"

  - name: "GoogleMapsAPI"
    type: "maps"
    endpoint: "https://maps.googleapis.com/maps/api/place/textsearch/json" # Example for Places API
    key_name: "key"
    key_value: "load_from_secrets.google_maps_api_key"
    headers: {}
    default_params: {}
    functions:
      emergency_services: {path: ""} # Path for textsearch
    query_param: "query"
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

    print("\n--- Testing medical_tool functions ---")
    test_user = "test_user_medical"
    
    if config_manager:
        # Test medical_search_web
        print("\n--- Testing medical_search_web ---")
        search_query = "latest research on Alzheimer's disease"
        search_result = medical_search_web(search_query, user_token=test_user)
        print(f"Search Result for '{search_query}':\n{search_result[:500]}...")

        # Prepare dummy data for medical_query_uploaded_docs
        print("\n--- Preparing dummy data for medical_query_uploaded_docs ---")
        dummy_json_path = Path("temp_medical_docs.json")
        dummy_data = [
            {"id": 1, "text": "Patient X's medical history includes hypertension and type 2 diabetes.", "category": "patient_record"},
            {"id": 2, "text": "A new study suggests regular exercise significantly reduces cardiovascular risk.", "category": "research"},
            {"id": 3, "text": "First aid for a sprained ankle involves R.I.C.E. (Rest, Ice, Compression, Elevation).", "category": "first_aid"}
        ]
        with open(dummy_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f)
        
        # Load documents from the dummy JSON for build_vectorstore
        loaded_docs_for_vector = load_docs_from_json_file(dummy_json_path)
        for i, doc in enumerate(loaded_docs_for_vector):
            doc.page_content = dummy_data[i]["text"]

        build_vectorstore(test_user, MEDICAL_SECTION, loaded_docs_for_vector, chunk_size=200, chunk_overlap=0)
        print(f"Vectorstore built for {MEDICAL_SECTION}.")

        # Test medical_query_uploaded_docs
        print("\n--- Testing medical_query_uploaded_docs ---")
        doc_query = "What is patient X's medical history?"
        doc_results = medical_query_uploaded_docs(doc_query, user_token=test_user)
        print(f"Query uploaded docs for '{doc_query}':\n{doc_results}")

        # Test medical_summarize_document_by_path
        print("\n--- Testing medical_summarize_document_by_path ---")
        # Create a dummy upload directory and file
        test_upload_dir = Path("uploads") / test_user / MEDICAL_SECTION
        test_upload_dir.mkdir(parents=True, exist_ok=True)
        summarize_file_path = test_upload_dir / "medical_report.txt"
        with open(summarize_file_path, "w") as f:
            f.write("This medical report details the findings from a recent clinical trial on a new drug. " * 30 + 
                    "The drug showed promising results in reducing symptoms in 70% of participants, with minimal side effects. " * 20 +
                    "Further research is recommended to confirm long-term efficacy and safety." * 25)
        print(f"Created dummy file for summarization: {summarize_file_path}")

        summary_result = medical_summarize_document_by_path(str(summarize_file_path))
        print(summary_result)

        # Test symptom_checker
        print("\n--- Testing symptom_checker ---")
        symptoms_check_result = symptom_checker("fever,cough")
        print(f"Symptom Checker (fever,cough): {symptoms_check_result}")
        symptoms_check_result2 = symptom_checker("headache,fatigue")
        print(f"Symptom Checker (headache,fatigue): {symptoms_check_result2}")

        # Test basic_diagnosis
        print("\n--- Testing basic_diagnosis ---")
        diagnosis_result = basic_diagnosis("fever,cough,sore throat")
        print(f"Basic Diagnosis (fever,cough,sore throat):\n{diagnosis_result}")
        diagnosis_result2 = basic_diagnosis("chest pain,shortness of breath")
        print(f"Basic Diagnosis (chest pain,shortness of breath):\n{diagnosis_result2}")

        # Test first_aid_instructions
        print("\n--- Testing first_aid_instructions ---")
        first_aid_cut = first_aid_instructions("minor cut")
        print(f"First Aid for Minor Cut:\n{first_aid_cut}")
        first_aid_burn = first_aid_instructions("burn")
        print(f"First Aid for Burn:\n{first_aid_burn}")

        # Test health_tip_generator
        print("\n--- Testing health_tip_generator ---")
        health_tip_sleep = health_tip_generator("sleep")
        print(f"Health Tip (sleep): {health_tip_sleep}")
        health_tip_general = health_tip_generator()
        print(f"Health Tip (general): {health_tip_general}")

        # Test emergency_locator
        print("\n--- Testing emergency_locator ---")
        emergency_london = emergency_locator("London")
        print(f"Emergency Services near London:\n{emergency_london}")

        # Test world_health_updates
        print("\n--- Testing world_health_updates ---")
        world_updates = world_health_updates()
        print(f"World Health Updates:\n{world_updates}")

        # Test python_interpreter (example with mock data)
        print("\n--- Testing python_interpreter with mock data ---")
        python_code_health_data = """
import json
import pandas as pd
mock_health_data = '''[
    {"patient_id": "P001", "age": 35, "condition": "Flu"},
    {"patient_id": "P002", "age": 42, "condition": "Cold"},
    {"patient_id": "P003", "age": 28, "condition": "Flu"},
    {"patient_id": "P004", "age": 50, "condition": "Allergies"}
]'''
df = pd.DataFrame(json.loads(mock_health_data))
flu_patients = df[df['condition'] == 'Flu']
print(f"Number of flu patients: {len(flu_patients)}")
print(f"Average age of flu patients: {flu_patients['age'].mean()}")
"""
        print(f"Executing Python code:\n{python_code_health_data}")
        try:
            repl_output = python_repl.run(python_code_health_data)
            print(f"Python REPL Output:\n{repl_output}")
        except Exception as e:
            print(f"Error executing Python REPL: {e}. Make sure pandas, numpy, json are installed.")


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
        dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"

        if dummy_config_path.exists(): os.remove(dummy_config_path)
        if dummy_sports_apis_path.exists(): os.remove(dummy_sports_apis_path)
        if dummy_media_apis_path.exists(): os.remove(dummy_media_apis_path)
        if dummy_finance_apis_path.exists(): os.remove(dummy_finance_apis_path)
        if dummy_medical_apis_path.exists(): os.remove(dummy_medical_apis_path)
        if not os.listdir(dummy_data_dir):
            os.rmdir(dummy_data_dir)
