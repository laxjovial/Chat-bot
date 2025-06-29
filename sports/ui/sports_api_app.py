# sports/ui/sports_api_app.py

import streamlit as st
from sports.tools.sports_tool import SportsTool
from utils.user_manager import get_user_token

st.set_page_config(page_title="Sports API Query", layout="centered")
st.title("🏟️ Real-Time Sports Info")

# === User Setup ===
username_or_email = st.text_input("Enter your username or email", value="victor")
user_token = get_user_token(username_or_email)

st.markdown("Use this tool to ask sports-related questions like:")
st.code("How many EPL trophies has Manchester City won?\nWho is the current top scorer in La Liga?")

# === Query Field ===
query = st.text_area("Enter your sports query", height=100)

if st.button("⚽ Ask SportsTool"):
    if not query.strip():
        st.warning("Please enter a valid question.")
    elif not user_token:
        st.error("User not found. Please check your input.")
    else:
        with st.spinner("Fetching answer from available APIs..."):
            result = SportsTool.invoke({"query": query, "user_token": user_token})
            st.success("✅ Answer Ready")
            st.text_area("📋 Result", result, height=300)

