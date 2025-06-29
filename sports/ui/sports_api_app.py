# sports/ui/sports_api_app.py

import streamlit as st
from sports.tools.sports_tool import SportsTool

st.set_page_config(page_title="Sports API Query", layout="centered")
st.title("🏟️ Real-Time Sports Info")

# === User Setup ===
user_id = st.text_input("User ID", value="victor")
st.markdown("Use this tool to ask sports-related questions like:")
st.code("How many EPL trophies has Manchester City won?\nWho is the current top scorer in La Liga?")

# === Query Field ===
query = st.text_area("Enter your sports query", height=100)

if st.button("⚽ Ask SportsTool"):
    if not query.strip():
        st.warning("Please enter a valid question.")
    else:
        with st.spinner("Fetching answer from available APIs..."):
            result = SportsTool.run(query)
            st.success("✅ Answer Ready")
            st.text_area("📋 Result", result, height=300)
