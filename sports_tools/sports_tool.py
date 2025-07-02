# sports_chat_agent_app.py

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

# Import the sports-specific tools
from sports_tools.sports_tool import sports_search_web, sports_query_uploaded_docs, sports_summarize_document_by_path

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
        st.secrets = MockSecrets()
        logger.info("Mocked st.secrets for standalone testing.")
    
    # The config_manager is a singleton and should be initialized on import.
    # We just ensure it has loaded correctly.
    if not config_manager._is_loaded:
        try:
            # This line should ideally not be needed if config_manager is a true singleton
            # and initialized on module import, but is a safeguard.
            # config_manager = ConfigManager() 
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
tools = [
    sports_search_web,
    sports_query_uploaded_docs,
    sports_summarize_document_by_path,
]

# Define the agent prompt
# The prompt guides the agent on how to use its tools and respond.
template = """
You are a highly specialized AI assistant focused on sports. Your primary goal is to provide accurate, concise, and helpful information about sports.
You have access to the following tools:

{tools}

**Instructions for using tools:**
- **`sports_search_web`**: Use this tool for general sports knowledge, current events, recent news, or anything that requires real-time information from the internet.
- **`sports_query_uploaded_docs`**: Use this tool if the user's question seems to refer to specific documents or data that might have been uploaded by them (e.g., "my team's scouting report", "the contract details I uploaded"). Always specify the `user_token` when calling this tool.
- **`sports_summarize_document_by_path`**: Use this tool if the user explicitly asks you to summarize a document and provides a file path (e.g., "summarize the article at uploads/my_user/sports/game_analysis.txt").

**General Guidelines:**
- Prioritize using the tools to find answers.
- If a question can be answered by multiple tools, choose the most specific and efficient one.
- If you cannot find an answer using your tools, state that clearly and politely.
- When responding, be concise and directly answer the user's question.
- Cite your sources (e.g., "[From Web Search]", "[From Uploaded Docs]") when you use a tool to retrieve information.
- Maintain a helpful and informative tone.

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
st.set_page_config(page_title="Sports AI Assistant", page_icon="⚽", layout="centered")
st.title("Sports AI Assistant ⚽")
st.markdown("Your dedicated AI for all things sports! Ask me anything about sports, and I'll use my tools to find the answer.")

# Initialize chat history in Streamlit's session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        AIMessage(content="Hello! I am your Sports AI Assistant. How can I help you today?")
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
                # In a real app, this would come from a login system.
                current_user_token = get_user_token() 

                # Prepare chat history for the agent.
                # The agent's prompt expects a string representation of chat history.
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
st.caption("This agent uses web search, queries your uploaded documents, and can summarize files.")

