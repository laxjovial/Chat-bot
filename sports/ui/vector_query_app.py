# sports/ui/vector_query_app.py

import streamlit as st
from sports.tools.import_utils import process_upload
from sports.tools.vector_query_tool import QueryUploadedDocs

st.set_page_config(page_title="Vector Document Query - Sports Assistant", layout="centered")
st.title("📄 Upload & Query Your Docs")

# === User & Section Setup ===
user_id = st.text_input("User ID", value="victor")
section = st.selectbox("Section", ["sports", "legal", "finance", "media", "medical"], index=0)

# === Upload Document ===
st.subheader("1. Upload File to Embed")
uploaded_file = st.file_uploader("Upload a document (PDF, TXT, MD, CSV, DOCX)", type=["pdf", "txt", "md", "csv", "docx"])
if uploaded_file and st.button("📥 Process Upload"):
    with st.spinner("Indexing document..."):
        msg = process_upload(uploaded_file, user_id=user_id, section=section)
        st.success(msg)

# === Query Uploaded Content ===
st.subheader("2. Ask a Question Based on Your File")
query_text = st.text_area("Your Question", placeholder="e.g. What does this contract say about termination clauses?")
export_flag = st.checkbox("Export results as markdown")

if st.button("🔍 Run Query"):
    if not query_text.strip():
        st.warning("Please enter a query.")
    else:
        with st.spinner("Searching embedded content..."):
            results = QueryUploadedDocs(query=query_text, user_id=user_id, section=section, export=export_flag)
            st.text_area("🔎 Results", results, height=400)
