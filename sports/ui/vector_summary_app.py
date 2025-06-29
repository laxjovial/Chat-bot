# sports/ui/vector_summary_app.py

import streamlit as st
from pathlib import Path
from io import BytesIO

from sports.tools.doc_summarizer import summarize_document
from sports.tools.export_utils import export_response
from sports.tools.vector_query_tool import QueryUploadedDocs
from sports.tools.import_utils import process_upload
from utils.user_manager import get_user_token

st.set_page_config(page_title="LLM Document Summarizer + QA + Classification", layout="centered")
st.title("📚 Smart File Analyzer")

# === User Setup ===
username_or_email = st.text_input("User ID or Email", value="victor")
user_token = get_user_token(username_or_email)
section = st.selectbox("Section", ["sports", "legal", "finance", "media", "medical"], index=0)

# === Upload + Summarize ===
st.subheader("1. Upload File")
file = st.file_uploader("Upload a document to analyze (PDF, TXT, DOCX, CSV, MD)", type=["pdf", "txt", "md", "csv", "docx"])
export_flag = st.checkbox("Export summary as markdown")
export_label = st.checkbox("Export classification label")
save_to_vector = st.checkbox("Auto-index summary into memory")

# For classification preview
def classify_text(summary):
    summary_lower = summary.lower()
    if "contract" in summary_lower or "agreement" in summary_lower:
        return "🧾 Contract Document"
    elif "invoice" in summary_lower or "billing" in summary_lower:
        return "💰 Invoice or Billing Record"
    elif "medical" in summary_lower or "patient" in summary_lower:
        return "🩺 Medical Document"
    elif "terms" in summary_lower and "service" in summary_lower:
        return "📄 Terms of Service"
    else:
        return "📂 General Document"

if file and st.button("🧠 Summarize & Classify"):
    if not user_token:
        st.error("User not found.")
    else:
        temp_path = Path(f"sports/uploads/{user_token}/{section}/temp_{file.name}")
        temp_path.parent.mkdir(parents=True, exist_ok=True)

        with open(temp_path, "wb") as f:
            f.write(file.read())

        with st.spinner("Analyzing with LLM..."):
            try:
                summary = summarize_document(temp_path, user_id=user_token)
                doc_type = classify_text(summary)

                st.success("✅ Summary complete!")
                st.markdown(f"### 🏷️ Document Type: {doc_type}")
                st.text_area("📋 Summary", summary, height=400)

                # === Export options ===
                if export_flag:
                    summary_path = export_response(summary, section=section, user_id=user_token, format="md", filename="summary")
                    st.info(f"📄 Summary exported to: {summary_path}")

                if export_label:
                    label_path = export_response(doc_type, section=section, user_id=user_token, format="txt", filename="classification")
                    st.info(f"🏷️ Classification exported to: {label_path}")

                if save_to_vector:
                    summary_file = BytesIO(summary.encode("utf-8"))
                    summary_file.name = "summary.txt"
                    msg = process_upload(summary_file, user_token=user_token, section=section)
                    st.success(f"🧠 Summary embedded: {msg}")

            except Exception as e:
                st.error(f"❌ Failed to summarize: {e}")
            finally:
                temp_path.unlink(missing_ok=True)

# === Interactive QA on Uploaded Content ===
st.subheader("2. Ask a Question About This File")
query = st.text_area("Ask something about your uploaded document", placeholder="e.g. What is the termination clause?", key="qa_text")
if query and st.button("🔍 Ask Document"):
    if not user_token:
        st.error("User not found.")
    else:
        with st.spinner("Running vector-based QA..."):
            result = QueryUploadedDocs.invoke({
                "query": query,
                "user_token": user_token,
                "section": section,
                "export": False
            })
            st.text_area("💬 Answer", result, height=300)


