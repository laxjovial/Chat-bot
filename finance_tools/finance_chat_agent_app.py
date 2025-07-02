# finance_chat_agent_app.py

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

# Import the finance-specific tools
from finance_tools.finance_tool import (
    finance_search_web, 
    finance_query_uploaded_docs, 
    finance_summarize_document_by_path,
    python_repl, # The Python REPL tool for data analysis
    finance_data_fetcher # The tool for fetching financial data
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
                self.alphavantage_api_key = "YOUR_ALPHAVANTAGE_API_KEY_HERE" # For finance_data_fetcher
                self.coingecko_api_key = "YOUR_COINGECKO_API_KEY_HERE" # For finance_data_fetcher
                self.exchangerate_api_key = "YOUR_EXCHANGERATE_API_KEY_HERE" # For finance_data_fetcher
                self.financial_news = {"api_key": "YOUR_FINANCIAL_NEWS_API_KEY_HERE"} # For finance_apis.yaml example
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
# Include the new Python REPL tool and the finance data fetcher
tools = [
    finance_search_web,
    finance_query_uploaded_docs,
    finance_summarize_document_by_path,
    python_repl, # For data analysis and complex logic
    finance_data_fetcher # For fetching financial data
]

# Define the agent prompt
# The prompt guides the agent on how to use its tools and respond.
template = """
You are a highly specialized AI assistant focused on finance. Your primary goal is to provide accurate, concise, and helpful information, analysis, and insights related to financial markets, companies, economic data, cryptocurrencies, and currency exchange rates.
You have access to the following tools:

{tools}

**Instructions for using tools:**
- **`finance_search_web`**: Use this tool for general financial news, current market trends, or anything that requires up-to-date information from the broader internet.
- **`finance_query_uploaded_docs`**: Use this tool if the user's question seems to refer to specific financial documents or reports that might have been uploaded by them (e.g., "my company's Q4 report", "the investment strategy I uploaded"). Always specify the `user_token` when calling this tool.
- **`finance_summarize_document_by_path`**: Use this tool if the user explicitly asks you to summarize a document and provides a file path (e.g., "summarize the earnings call transcript at uploads/my_user/finance/transcript.txt").
- **`finance_data_fetcher`**: This is your primary tool for structured financial data.
    - **For Stock Data**: Use `api_name="AlphaVantage"` with `data_type` like "stock_prices", "company_overview", "global_quote". Provide `symbol`.
    - **For Cryptocurrency Data**: Use `api_name="CoinGecko"` with `data_type` like "crypto_price" (requires `ids` and `vs_currencies`), "crypto_list", or "crypto_market_chart" (requires `ids`, `vs_currencies`, `days`).
    - **For Currency Exchange Rates**: Use `api_name="ExchangeRate-API"` with `data_type` like "exchange_rate_latest" (requires `base_currency`) or "exchange_rate_convert" (requires `base_currency`, `target_currency`, `amount`).
    - Always specify the `api_name` and `data_type`, and then the relevant parameters for that specific API and data type.
    - The output will be a JSON string. You will likely need to use `python_interpreter` to parse and analyze this JSON.
- **`python_interpreter`**: This is a powerful tool. Use it for:
    - **Parsing and Analyzing Fetched Data**: After using `finance_data_fetcher`, use this tool to parse the JSON output (e.g., `import json; data = json.loads(tool_output)`) and perform calculations, statistical analysis, time-series analysis (e.g., `import pandas as pd`), or extract specific insights.
    - **Complex Calculations**: Any query that requires programmatic logic, conditional statements, or data manipulation that cannot be directly answered by other tools.
    - Print your final results or findings clearly to stdout so I can see them.

**General Guidelines:**
- Prioritize using the tools to find answers.
- If a question can be answered by multiple tools, choose the most specific and efficient one.
- If you cannot find an answer using your tools, state that clearly and politely.
- When responding, be concise and directly answer the user's question.
- Cite your sources (e.g., "[From Web Search]", "[From Uploaded Docs]", "[Python Analysis]", "[From AlphaVantage]") when you use a tool to retrieve information or perform analysis.
- Maintain a professional, helpful, and informative tone, suitable for financial contexts.

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
st.set_page_config(page_title="Finance AI Assistant", page_icon="📈", layout="centered")
st.title("Finance AI Assistant 📈")
st.markdown("Your dedicated AI for financial insights and analysis! Ask me anything about markets, companies, economic data, crypto, or exchange rates, and I'll use my tools to help.")

# Initialize chat history in Streamlit's session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        AIMessage(content="Hello! I am your Finance AI Assistant. How can I help you today?")
    ]

# Display chat history
for message in st.session_state.messages:
    with st.chat_message("user" if isinstance(message, HumanMessage) else "assistant"):
        st.write(message.content)

# Get user input
user_query = st.chat_input("Ask me about finance...")

if user_query:
    # Add user's query to chat history
    st.session_state.messages.append(HumanMessage(content=user_query))
    with st.chat_message("user"):
        st.write(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Get the current user token. This is important for tools like finance_query_uploaded_docs.
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
st.caption("This agent uses web search, queries your uploaded documents, can summarize files, and performs data analysis via a Python interpreter.")
