# ui/register_app.py

import streamlit as st
from utils.user_manager import create_user, find_user_by_email
from utils.email_utils import send_email

st.set_page_config(page_title="📝 Register", layout="centered")
st.title("📝 Create an Account")

# === Input Fields ===
username = st.text_input("Username")
email = st.text_input("Email")
password = st.text_input("Password", type="password")
tier = st.selectbox("Choose your plan", ["free", "pro", "admin"])

st.markdown("### 🔒 Security Question")
security_q = st.text_input("Your question (e.g., Best team?)")
security_a = st.text_input("Your answer (case sensitive)")

# === Register Button ===
if st.button("Create Account"):
    if not all([username, email, password, security_q, security_a]):
        st.error("❌ All fields are required.")
    elif find_user_by_email(email):
        st.error("❌ A user with this email already exists.")
    else:
        # Create the user and return the token
        token = create_user(
            username=username,
            email=email,
            tier=tier,
            password=password,
            security_q=security_q,
            security_a=security_a
        )

        # === Email the token ===
        subject = "✅ Your Smart Assistant Login Token"
        body = f"""
        Hello {username},

        Your account has been successfully created!

        🔑 Your unique token: {token}

        This token gives you secure access. Please keep it safe and do not share it with others.

        You can also log in using your username/password or OTP via email or phone (if enabled).

        — Smart AI Assistant Team
        """

        send_email(email=email, subject=subject, body=body)

        st.success("🎉 Account created!")
        st.info("📧 Token sent to your email. Check your inbox.")
