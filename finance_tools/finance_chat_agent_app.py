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
    finance_data_fetcher # The placeholder tool for fetching financial data
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
                self.alphavantage = {"api_key": "YOUR_ALPHAVANTAGE_API_KEY_HERE"} # For finance_data_fetcher
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

# Get LLM based on configuration
try:
    # Get the LLM instance using the centralized utility function
    # Note: LangChain's create_react_agent often works best with ChatOpenAI for now.
    # If using other LLMs, ensure they are compatible with LangChain agents.
    llm = get_llm()
    if not isinstance(llm, ChatOpenAI):
        st.warning("The LangChain ReAct agent often performs best with OpenAI models. Ensure your chosen LLM is compatible.")
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
You are a highly specialized AI assistant focused on finance. Your primary goal is to provide accurate, concise, and helpful information, analysis, and insights related to financial markets, companies, and economic data.
You have access to the following tools:

{tools}

**Instructions for using tools:**
- **`finance_search_web`**: Use this tool for general financial knowledge, current market news, real-time economic indicators (if not available via `finance_data_fetcher`), or anything that requires up-to-date information from the internet.
- **`finance_query_uploaded_docs`**: Use this tool if the user's question seems to refer to specific financial documents or reports that might have been uploaded by them (e.g., "my company's Q4 report", "the investment strategy I uploaded"). Always specify the `user_token` when calling this tool.
- **`finance_summarize_document_by_path`**: Use this tool if the user explicitly asks you to summarize a document and provides a file path (e.g., "summarize the earnings call transcript at uploads/my_user/finance/transcript.txt").
- **`python_interpreter`**: This is a powerful tool. Use it for:
    - **Data Analysis**: When the user asks for calculations, statistical analysis, or insights from structured data.
    - **Time-Series Analysis**: For analyzing trends, volatility, or patterns in historical financial data (e.g., stock prices, economic indicators).
    - **Complex Queries**: When a query requires logical processing, conditional statements, or data manipulation that cannot be directly answered by other tools.
    - **Parsing JSON**: If `finance_data_fetcher` returns JSON, use `python_interpreter` to parse it (e.g., `import json; data = json.loads(tool_output); print(data[0]['close'])`).
    - Remember to `import pandas as pd` and other necessary libraries if working with dataframes.
    - Print your results clearly to stdout so I can see them.
- **`finance_data_fetcher`**: Use this tool to retrieve specific financial data points or time-series data from financial APIs. Understand its parameters (`data_type`, `symbol`, `start_date`, `end_date`, `limit`).

**General Guidelines:**
- Prioritize using the tools to find answers.
- If a question can be answered by multiple tools, choose the most specific and efficient one.
- If you cannot find an answer using your tools, state that clearly and politely.
- When responding, be concise and directly answer the user's question.
- Cite your sources (e.g., "[From Web Search]", "[From Uploaded Docs]", "[Python Analysis]") when you use a tool to retrieve information or perform analysis.
- Maintain a professional, helpful, and informative tone, suitable for financial contexts.

Begin!

{chat_history}
Question: {input}
{agent_scratchpad}
"""

prompt = PromptTemplate.from_template(template)

# Create the agent
# The `create_react_agent` function creates an agent that uses the ReAct framework.
# `verbose=True` is useful for debugging to see the agent's thought process.
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

# --- Streamlit UI ---
st.set_page_config(page_title="Finance AI Assistant", page_icon="📈", layout="centered")
st.title("Finance AI Assistant 📈")
st.markdown("Your dedicated AI for financial insights and analysis! Ask me anything about markets, companies, or economic data, and I'll use my tools to help.")

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
