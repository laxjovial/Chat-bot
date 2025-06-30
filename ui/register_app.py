# ui/register_app.py

import streamlit as st
from utils.user_manager import create_user, lookup_user_by_token, send_token_to_email

st.set_page_config(page_title="📝 Register", layout="centered")
st.title("📝 Create a New Account")

# === Form Inputs ===
with st.form("register_form"):
    username = st.text_input("Username")
    email = st.text_input("Email Address")
    password = st.text_input("Password", type="password")
    tier = st.selectbox("Select Your Access Tier", ["free", "pro", "admin"])
    security_q = st.text_input("Security Question (for recovery)", value="What is your favorite color?")
    security_a = st.text_input("Security Answer")

    submitted = st.form_submit_button("🚀 Register")

# === Registration Logic ===
if submitted:
    if not username or not email or not password or not security_q or not security_a:
        st.warning("Please complete all fields.")
    else:
        token = create_user(
            username=username,
            email=email,
            password=password,
            tier=tier,
            security_q=security_q,
            security_a=security_a
        )
        user = lookup_user_by_token(token)
        if user:
            st.success(f"🎉 Registration successful! Your user token is:\n\n`{token}`")
            
            # Send token to email (mock or SMTP)
            if send_token_to_email(email):
                st.info("📩 Your token has been sent to your email. Please save it securely.")
            else:
                st.warning("⚠️ Token could not be sent to your email (email service not connected).")
        else:
            st.error("❌ Something went wrong. Please try again.")
