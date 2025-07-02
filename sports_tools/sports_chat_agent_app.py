# ui/sports_chat_agent_app.py

import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.callbacks import StreamingStdOutCallbackHandler
import logging

# Assume config_manager and get_user_token exist in these paths
from config.config_manager import config_manager
from utils.user_manager import get_current_user, get_user_tier_capability # For getting user token and capabilities
from shared_tools.llm_embedding_utils import get_llm # For getting the LLM instance

# Import the sports-specific tools
from sports_tools.sports_tool import (
    sports_search_web, 
    sports_query_uploaded_docs, 
    sports_summarize_document_by_path,
    sports_data_fetcher, # The tool for fetching sports data
    player_stats_checker,
    team_info_checker,
    match_schedule_checker
)

# Import the RBAC-enabled Python interpreter tool
from shared_tools.python_interpreter_tool import python_interpreter_with_rbac

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
                self.thesportsdb = {"api_key": "YOUR_THESPORTSDB_API_KEY_HERE"}
                self.sportradar = {"api_key": "YOUR_SPORTRADAR_API_KEY_HERE"}
        st.secrets = MockSecrets()
        logger.info("Mocked st.secrets for standalone testing.")
    
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
# Get current user for RBAC checks
current_user = get_current_user()
user_token = current_user.get('user_id') # Use user_id as user_token for consistency with RBAC checks
# If user_id is not available (e.g., mock user), fall back to a default or handle appropriately
if not user_token:
    user_token = "default" # Fallback for guest users or testing

# Define the base set of tools available to the Sports Agent
tools = [
    sports_search_web,
    sports_query_uploaded_docs,
    sports_summarize_document_by_path,
    sports_data_fetcher, # The tool for fetching sports data
    player_stats_checker,
    team_info_checker,
    match_schedule_checker
]

# Conditionally add the Python interpreter based on user's tier
if get_user_tier_capability(user_token, 'data_analysis_enabled', False):
    tools.append(python_interpreter_with_rbac)
    logger.info(f"Python interpreter enabled for user {user_token} (Tier: {current_user.get('tier')}).")
else:
    logger.info(f"Python interpreter NOT enabled for user {user_token} (Tier: {current_user.get('tier')}).")


# Define the agent prompt
# The prompt guides the agent on how to use its tools and respond.
template = """
You are a highly specialized AI assistant focused on sports information and analysis. Your primary goal is to provide accurate, concise, and helpful information, statistics, and insights related to various sports, teams, and players.
You have access to the following tools:

{tools}

**Instructions for using tools:**
- **`sports_search_web`**: Use this tool for general sports news, recent game results, or anything that requires up-to-date information from the broader internet on sports topics.
- **`sports_query_uploaded_docs`**: Use this tool if the user's question seems to refer to specific sports documents, scouting reports, or personal sports notes that might have been uploaded by them (e.g., "my team's training plan", "summary of the basketball analytics report I uploaded"). Always specify the `user_token` when calling this tool.
- **`sports_summarize_document_by_path`**: Use this tool if the user explicitly asks you to summarize a document and provides a file path (e.g., "summarize the match report at uploads/my_user/sports/match_report.pdf").
- **`sports_data_fetcher`**: This is your primary tool for structured sports data from configured APIs.
    - **For Player Stats**: Use `api_name="TheSportsDB"` or `api_name="SportRadar"` with `data_type="player_stats"`. Provide `player_name` and `sport` (optional).
    - **For Team Info**: Use `api_name="TheSportsDB"` or `api_name="SportRadar"` with `data_type="team_info"`. Provide `team_name` and `sport` (optional).
    - **For Match Schedules/Results**: Use `api_name="TheSportsDB"` or `api_name="SportRadar"` with `data_type="match_schedule"`. Provide `team_name` or `league` and `date` (optional).
    - Always specify the `api_name` and `data_type`, and then the relevant parameters for that specific API and data type.
    - The output will be a JSON string. You will likely need to use `python_interpreter_with_rbac` to parse and analyze this JSON.
- **`player_stats_checker`**: Use this tool if the user asks for statistics of a specific player.
- **`team_info_checker`**: Use this tool if the user asks for information about a specific team.
- **`match_schedule_checker`**: Use this tool if the user asks for match schedules or results.
- **`python_interpreter_with_rbac`**: This is a powerful tool for users with appropriate tiers. Use it for:
    - **Parsing and Analyzing Fetched Data**: After using `sports_data_fetcher`, use this tool to parse the JSON output (e.g., `import json; data = json.loads(tool_output)`) and perform calculations, statistical analysis, or extract specific insights from sports datasets (e.g., calculating batting averages, win rates, comparing player performance).
    - **Complex Queries**: Any query that requires programmatic logic, conditional statements, or data manipulation that cannot be directly answered by other tools.
    - Print your final results or findings clearly to stdout so I can see them.

**General Guidelines:**
- Prioritize using the tools to find answers.
- If a question can be answered by multiple tools, choose the most specific and efficient one.
- If you cannot find an answer using your tools, state that clearly and politely.
- When responding, be concise and directly answer the user's question.
- Cite your sources (e.g., "[From Web Search]", "[From Uploaded Docs]", "[Python Analysis]", "[From TheSportsDB]") when you use a tool to retrieve information or perform analysis.
- Maintain a professional, objective, and informative tone.

Begin!

{chat_history}
Question: {input}
{agent_scratchpad}
"""

prompt = PromptTemplate.from_template(template)

# Create the agent
agent = create_react_agent(llm, tools, prompt)
# Pass the user_token to the agent executor so it's available for tools
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# --- Streamlit UI ---
st.set_page_config(page_title="Sports AI Assistant", page_icon="🏆", layout="centered")
st.title("Sports AI Assistant 🏆")
st.markdown("Your dedicated AI for sports information and analysis. Ask me anything about your favorite teams, players, or games!")

# Initialize chat history in Streamlit's session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        AIMessage(content="Hello! I am your Sports AI Assistant. What sports information are you looking for today?")
    ]

# Display chat history
for message in st.session_state.messages:
    with st.chat_message("user" if isinstance(message, HumanMessage) else "assistant"):
        st.write(message.content)

# Get user input
user_query = st.chat_input("Ask me about sports...")

if user_query:
    # Add user's query to chat history
    st.session_state.messages.append(HumanMessage(content=user_query))
    with st.chat_message("user"):
        st.write(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Get the current user token. This is important for tools like sports_query_uploaded_docs.
                current_user_obj = get_current_user()
                current_user_token = current_user_obj.get('user_id') # Use user_id as token for RBAC checks
                if not current_user_token:
                    st.warning("Could not retrieve user token. Functionality might be limited.")
                    current_user_token = "default" # Fallback for guest users or testing

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
st.caption(f"Current User Token: `{current_user.get('user_id', 'N/A')}` (for demo purposes)")
st.caption("This agent uses web search, queries your uploaded documents, can summarize files, fetches data from sports APIs, and can perform data analysis based on your tier.")

