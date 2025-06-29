# sports/ui/sports_chat_agent.py

import streamlit as st
from langchain_community.chat_message_histories import StreamlitChatMessageHistory

from sports.tools.vector_query_tool import QueryUploadedDocs
from sports.tools.doc_summarizer import summarize_document
from sports.tools.sports_tool import SportsTool
from sports.config.config_manager import get_user_tier, get_model_settings
from sports.tools.import_utils import process_upload
from sports.tools.export_utils import export_response

from pathlib import Path
from io import BytesIO

st.set_page_config(page_title="Smart Sports Agent", layout="centered")
st.title("🤖 Your Sports Assistant Agent")

# === Memory Setup ===
history = StreamlitChatMessageHistory()
user_id = st.text_input("User ID", value="victor")
section = "sports"

# === Upload Block ===
with st.expander("📁 Upload a Document"):
    file = st.file_uploader("Upload a PDF, TXT, DOCX, CSV, or MD", type=["pdf", "txt", "md", "csv", "docx"])
    if file and st.button("Embed Document to Memory"):
        try:
            msg = process_upload(file, user_id=user_id, section=section)
            st.success(msg)
        except Exception as e:
            st.error(f"Upload failed: {e}")

# === Conversation Block ===
st.subheader("💬 Ask Anything")
for msg in history.messages:
    st.chat_message(msg.role).markdown(msg.content)

query = st.chat_input("Ask something like: How many EPL trophies has Man City won?")

if query:
    history.add_user_message(query)
    st.chat_message("user").markdown(query)

    # === Routing Logic ===
    answer = ""
    tier = get_user_tier(user_id)

    with st.spinner("Thinking..."):
        # Rule 1: API questions
        if any(kw in query.lower() for kw in ["who won", "how many", "player", "team", "trophies"]):
            answer = SportsTool.run(query)

        # Rule 2: Summarization request
        elif "summarize" in query.lower():
            summary_dir = Path(f"sports/uploads/{user_id}/{section}")
            files = list(summary_dir.glob("*.pdf")) + list(summary_dir.glob("*.txt"))
            if not files:
                answer = "No files to summarize. Please upload a document."
            else:
                try:
                    answer = summarize_document(files[0], user_id=user_id)
                except Exception as e:
                    answer = f"Summarization failed: {e}"

        # Rule 3: Vector-based fallback (for uploaded memory)
        else:
            answer = QueryUploadedDocs(query=query, user_id=user_id, section=section, export=False)

        # Tier-based length control (example)
        if tier == "free" and len(answer) > 1000:
            answer = answer[:1000] + "... (truncated for free tier)"

    history.add_ai_message(answer)
    st.chat_message("assistant").markdown(answer)
