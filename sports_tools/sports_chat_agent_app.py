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
from utils.user_manager import get_user_token

# Import the sports-specific tools
from sports_tools.sports_tool import sports_search_web, sports_query_uploaded_docs, sports_summarize_document_by_path

# Set up logging
logging.basicConfig(level=logging.INFO)

# --- Configuration ---
def initialize_config():
    """Initializes the config_manager and st.secrets."""
    if not hasattr(st, 'secrets'):
        # This block is mainly for local testing outside of Streamlit's native 'secrets.toml'
        class MockSecrets:
            def __init__(self):
                self.openai = {"api_key": "sk-your-openai-key-here"} # Replace with a real key for live app
                # Add other secrets as needed by the tools (e.g., serpapi, google custom search)
                self.serpapi = {"api_key": "YOUR_SERPAPI_KEY"} 
                self.google = {"api_key": "YOUR_GOOGLE_API_KEY"}
                self.google_custom_search = {"api_key": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY"}
        st.secrets = MockSecrets()
        logging.info("Mocked st.secrets for standalone testing.")
    
    if not hasattr(config_manager, '_instance') or config_manager._instance is None:
        try:
            # You might need to create a dummy config.yml in the 'data' directory for initialization
            # if running this standalone without a full project setup.
            # Example: data/config.yml should contain LLM and RAG settings.
            # config_manager = ConfigManager() # Uncomment if ConfigManager needs explicit instantiation
            logging.info("ConfigManager assumed to be initialized by importing. Ensure data/config.yml exists.")
        except Exception as e:
            st.error(f"Failed to initialize configuration: {e}. Please ensure data/config.yml and .streamlit/secrets.toml are set up correctly.")
            st.stop()

initialize_config()

# Get LLM based on configuration
def get_chat_model():
    """Gets the appropriate LLM instance based on global config."""
    llm_provider = config_manager.get('llm.provider', 'openai').lower()
    llm_model = config_manager.get('llm.model', 'gpt-4o')
    temperature = config_manager.get('llm.temperature', 0.7)

    if llm_provider == "openai":
        openai_api_key = config_manager.get('openai.api_key')
        if not openai_api_key:
            raise ValueError("OpenAI API key not found in secrets.toml under [openai] api_key.")
        return ChatOpenAI(model=llm_model, temperature=temperature, openai_api_key=openai_api_key, streaming=True, callbacks=[StreamingStdOutCallbackHandler()])
    # Add other providers if supported by LangChain agents
    else:
        raise ValueError(f"Unsupported LLM provider for agent: {llm_provider}. Only OpenAI is supported for agents in this setup.")

try:
    llm = get_chat_model()
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
template = """
You are a specialized sports assistant. Your primary goal is to provide accurate and helpful information about sports.
You have access to the following tools:

{tools}

Use the tools as much as possible to answer questions about sports.
If a question is about current events or general knowledge, use `sports_search_web`.
If a question refers to specific documents or data that might have been uploaded, use `sports_query_uploaded_docs`.
If asked to summarize a document available at a specific file path, use `sports_summarize_document_by_path`.

If you cannot find an answer using your tools, state that clearly and politely.
When responding, be concise and directly answer the user's question, citing sources when possible.
Your responses should be formatted clearly.

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
st.set_page_config(page_title="Sports AI Assistant", page_icon="⚽")
st.title("Sports AI Assistant ⚽")

# Initialize chat history
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
    st.session_state.messages.append(HumanMessage(content=user_query))
    with st.chat_message("user"):
        st.write(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Prepare chat history for the agent
                # The agent expects a list of tuples (HumanMessage.content, AIMessage.content)
                # Or a list of BaseMessage objects, but the template expects a string.
                # Let's convert to a simple string history for the prompt template.
                chat_history_str = "\n".join([
                    f"Human: {msg.content}" if isinstance(msg, HumanMessage) else f"AI: {msg.content}"
                    for msg in st.session_state.messages[:-1] # Exclude current human message
                ])

                response = agent_executor.invoke({
                    "input": user_query,
                    "chat_history": chat_history_str # Pass history as a string
                })
                ai_response = response.get("output", "I could not process that request.")
                st.write(ai_response)
                st.session_state.messages.append(AIMessage(content=ai_response))
            except Exception as e:
                st.error(f"An error occurred: {e}. Please try again or rephrase your question.")
                logging.error(f"Agent execution failed: {e}", exc_info=True)
