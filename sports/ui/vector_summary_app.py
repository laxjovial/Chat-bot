# sports/ui/vector_summary_app.py

import streamlit as st
from pathlib import Path

from sports.tools.doc_summarizer import summarize_document
from sports.tools.export_utils import export_response

st.set_page_config(page_title="LLM Document Summarizer", layout="centered")
st.title("📚 LLM-Powered File Summarizer")

# === User Setup ===
user_id = st.text_input("User ID", value="victor")
section = st.selectbox("Section", ["sports", "legal", "finance", "media", "medical"], index=0)

# === Upload + Summarize ===
st.subheader("1. Upload File")
file = st.file_uploader("Upload a document to summarize (PDF, TXT, DOCX, CSV, MD)", type=["pdf", "txt", "md", "csv", "docx"])
export_flag = st.checkbox("Export summary as markdown")

if file and st.button("🧠 Summarize File"):
    temp_path = Path(f"sports/uploads/{user_id}/{section}/temp_{file.name}")
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    with open(temp_path, "wb") as f:
        f.write(file.read())

    with st.spinner("Generating summary using LLM..."):
        try:
            summary = summarize_document(temp_path, user_id=user_id)
            st.success("✅ Summary complete!")
            st.text_area("📋 Summary", summary, height=400)

            if export_flag:
                filepath = export_response(summary, section=section, user_id=user_id, format="md", filename="summary")
                st.info(f"📄 Summary exported to: {filepath}")

        except Exception as e:
            st.error(f"❌ Failed to summarize: {e}")
        finally:
            temp_path.unlink(missing_ok=True)
