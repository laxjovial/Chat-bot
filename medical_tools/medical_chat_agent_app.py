# medical_chat_agent_app.py

import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.callbacks import StreamingStdOutCallbackHandler
import logging

# Assume config_manager and get_user_token exist in these paths
from config.config_manager import config_manager
from utils.user_manager import get_user_token # For getting a user token for session
from shared_tools.llm_embedding_utils import get_llm # For getting the LLM instance

# Import the medical-specific tools
from medical_tools.medical_tool import (
    medical_search_web, 
    medical_query_uploaded_docs, 
    medical_summarize_document_by_path,
    python_repl, # The Python REPL tool for data analysis
    medical_data_fetcher, # The tool for fetching medical data
    symptom_checker,
    basic_diagnosis,
    first_aid_instructions,
    health_tip_generator,
    emergency_locator,
    world_health_updates
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration Initialization ---
def initialize_app_config():
    """
    Initializes the config_manager and ensures Streamlit secrets are accessible.
    This function is called once at the start of the app.
    """
    if not hasattr(st, 'secrets'):
        # This block is mainly for local testing outside of Streamlit's native 'secrets.toml'
        # In a deployed Streamlit app, st.secrets will be automatically populated.
        class MockSecrets:
            def __init__(self):
                self.openai = {"api_key": "sk-your-openai-key-here"} # Replace with a real key for live app
                self.google = {"api_key": "AIzaSy_YOUR_GOOGLE_API_KEY_HERE"} # Replace with a real key
                self.serpapi = {"api_key": "YOUR_SERPAPI_KEY_HERE"} 
                self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY_HERE"}
                self.health_api_key = "YOUR_HEALTH_API_KEY_HERE" # For medical_data_fetcher
                self.who_api_key = "YOUR_WHO_API_KEY_HERE" # For medical_data_fetcher
                self.google_maps_api_key = "YOUR_GOOGLE_MAPS_API_KEY_HERE" # For medical_data_fetcher
        st.secrets = MockSecrets()
        logger.info("Mocked st.secrets for standalone testing.")
    
    # The config_manager is a singleton and should be initialized on import.
    # We just ensure it has loaded correctly.
    if not config_manager._is_loaded:
        try:
            logger.info("ConfigManager assumed to be initialized by importing. Ensure data/config.yml and other config files exist.")
        except Exception as e:
            st.error(f"Failed to initialize configuration: {e}. Please ensure data/config.yml and .streamlit/secrets.toml are set up correctly.")
            st.stop()

initialize_app_config()

# --- Streamlit UI for LLM Configuration ---
st.sidebar.header("LLM Settings")
# Get default temperature from config_manager
default_temperature = config_manager.get('llm.temperature', 0.7)
llm_temperature = st.sidebar.slider(
    "LLM Temperature (Creativity vs. Focus)",
    min_value=0.0,
    max_value=1.0,
    value=default_temperature,
    step=0.05,
    help="Controls the randomness of the LLM's output. Lower values mean more deterministic, higher values mean more creative."
)

# Get LLM based on configuration and user's temperature choice
@st.cache_resource # Cache the LLM resource to avoid re-initializing on every rerun
def get_llm_cached(temperature: float):
    """Gets the appropriate LLM instance based on global config and provided temperature."""
    # Call the centralized get_llm with the user-selected temperature
    llm_instance = get_llm(override_temperature=temperature)
    
    # Ensure it's a ChatOpenAI for agent compatibility if that's the expectation
    # This check is a safeguard; ideally, the agent's prompt should be LLM-agnostic
    # or the LLM provider should be explicitly set for agent usage.
    if not isinstance(llm_instance, ChatOpenAI):
        st.warning("The LangChain ReAct agent often performs best with OpenAI models. Ensure your chosen LLM is compatible.")
    
    # Add streaming callbacks if the LLM supports it
    # Note: Not all LLMs or LangChain integrations support streaming callbacks in the same way.
    if hasattr(llm_instance, 'streaming'):
        llm_instance.streaming = True
    if hasattr(llm_instance, 'callbacks'):
        llm_instance.callbacks = [StreamingStdOutCallbackHandler()]
    
    return llm_instance

try:
    llm = get_llm_cached(llm_temperature)
except ValueError as e:
    st.error(e)
    st.stop()
except Exception as e:
    st.error(f"Error initializing LLM: {e}")
    st.stop()

# --- Agent Setup ---
# Include all medical tools
tools = [
    medical_search_web,
    medical_query_uploaded_docs,
    medical_summarize_document_by_path,
    python_repl, # For data analysis and complex logic
    medical_data_fetcher, # For fetching medical data
    symptom_checker,
    basic_diagnosis,
    first_aid_instructions,
    health_tip_generator,
    emergency_locator,
    world_health_updates
]

# Define the agent prompt
# The prompt guides the agent on how to use its tools and respond.
template = """
You are a highly specialized AI assistant focused on medical, health, and life-based queries. Your primary goal is to provide accurate, concise, and helpful information, preliminary assessments, and guidance.
You have access to the following tools:

{tools}

**Instructions for using tools:**
- **`medical_search_web`**: Use this tool for general medical knowledge, health news, research updates, or anything that requires up-to-date information from the broader internet.
- **`medical_query_uploaded_docs`**: Use this tool if the user's question seems to refer to specific medical documents or personal health records that might have been uploaded by them (e.g., "my blood test results", "summary of the research paper I uploaded"). Always specify the `user_token` when calling this tool.
- **`medical_summarize_document_by_path`**: Use this tool if the user explicitly asks you to summarize a document and provides a file path (e.g., "summarize the patient report at uploads/my_user/medical/report.pdf").
- **`medical_data_fetcher`**: Use this tool to retrieve structured medical data from configured APIs. Understand its parameters (`api_name`, `data_type`, `query`, `location`, `symptoms`, `limit`).
    - **For Symptoms/Conditions Lists**: Use `api_name="HealthAPI"` with `data_type` like "symptoms_list" or "conditions_list".
    - **For World Health Updates**: Use `api_name="WHO_API"` with `data_type="world_health_updates"`.
    - **For Emergency Services**: Use `api_name="GoogleMapsAPI"` with `data_type="emergency_services"` and provide `location`.
- **`symptom_checker`**: Use this tool if the user provides a list of symptoms and asks for possible conditions. Provide a comma-separated list of symptoms.
- **`basic_diagnosis`**: Use this tool for a very preliminary diagnosis based on a list of symptoms.
- **`first_aid_instructions`**: Use this tool if the user asks for first aid steps for a specific condition or injury (e.g., "how to treat a burn", "first aid for choking").
- **`health_tip_generator`**: Use this tool if the user asks for a health tip on a general or specific topic (e.g., "give me a health tip", "health tip about sleep").
- **`emergency_locator`**: Use this tool if the user asks to find nearby emergency services or hospitals. Provide a `location`.
- **`world_health_updates`**: Use this tool to get recent global health news.
- **`python_interpreter`**: This is a powerful tool. Use it for:
    - **Data Analysis**: When the user asks for calculations, statistical analysis, or insights from structured health data (e.g., analyzing patient demographics from fetched data).
    - **Complex Queries**: When a query requires logical processing, conditional statements, or data manipulation that cannot be directly answered by other tools.
    - **Parsing JSON**: If `medical_data_fetcher` returns JSON, use `python_interpreter` to parse it (e.g., `import json; data = json.loads(tool_output); print(data[0]['title'])`).
    - Remember to `import pandas as pd` and other necessary libraries if working with dataframes.
    - Print your results clearly to stdout so I can see them.

**IMPORTANT DISCLAIMER:** Always include a strong disclaimer that you are an AI and your information is not a substitute for professional medical advice, diagnosis, or treatment. Advise the user to consult a qualified healthcare provider for any health concerns and to call emergency services in case of a medical emergency.

**General Guidelines:**
- Prioritize using the tools to find answers.
- If a question can be answered by multiple tools, choose the most specific and efficient one.
- If you cannot find an answer using your tools, state that clearly and politely.
- When responding, be concise and directly answer the user's question.
- Cite your sources (e.g., "[From Web Search]", "[From Uploaded Docs]", "[Python Analysis]", "[From WHO]") when you use a tool to retrieve information or perform analysis.
- Maintain a professional, empathetic, and informative tone, always prioritizing safety and advising professional consultation for medical concerns.

Begin!

{chat_history}
Question: {input}
{agent_scratchpad}
"""

prompt = PromptTemplate.from_template(template)

# Create the agent
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# --- Streamlit UI ---
st.set_page_config(page_title="Medical AI Assistant", page_icon="⚕️", layout="centered")
st.title("Medical AI Assistant ⚕️")
st.markdown("Your dedicated AI for medical and health-related queries. **Disclaimer: I am an AI and cannot provide medical advice. Always consult a healthcare professional for diagnosis and treatment.**")

# Initialize chat history in Streamlit's session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        AIMessage(content="Hello! I am your Medical AI Assistant. How can I help you today? Remember, I am not a substitute for professional medical advice.")
    ]

# Display chat history
for message in st.session_state.messages:
    with st.chat_message("user" if isinstance(message, HumanMessage) else "assistant"):
        st.write(message.content)

# Get user input
user_query = st.chat_input("Ask me about health or medical topics...")

if user_query:
    # Add user's query to chat history
    st.session_state.messages.append(HumanMessage(content=user_query))
    with st.chat_message("user"):
        st.write(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Get the current user token. This is important for tools like medical_query_uploaded_docs.
                current_user_token = get_user_token() 

                # Prepare chat history for the agent.
                chat_history_str = "\n".join([
                    f"Human: {msg.content}" if isinstance(msg, HumanMessage) else f"AI: {msg.content}"
                    for msg in st.session_state.messages[:-1] # Exclude the current human message
                ])

                # Invoke the agent executor with the current input and chat history
                response = agent_executor.invoke({
                    "input": user_query,
                    "chat_history": chat_history_str,
                    "user_token": current_user_token # Pass user_token to the agent so tools can access it
                })
                
                ai_response = response.get("output", "I could not process that request. Please try again.")
                st.write(ai_response)
                st.session_state.messages.append(AIMessage(content=ai_response))
            except Exception as e:
                st.error(f"An error occurred: {e}. Please try again or rephrase your question.")
                logger.error(f"Agent execution failed: {e}", exc_info=True)

st.markdown("---")
st.caption(f"Current User Token: `{get_user_token()}` (for demo purposes)")
st.caption("This agent uses web search, queries your uploaded documents, can summarize files, and provides preliminary health information. Always consult a healthcare professional for medical advice.")
