# ui/login_app.py

import streamlit as st
import random
import time
from utils.user_manager import (
    get_user_token, lookup_user_by_token,
    find_user_by_email, verify_password, send_otp_to_email,
)

st.set_page_config(page_title="🔐 Login", layout="centered")
st.title("🔐 Secure Login")

# === Simulated in-memory OTP storage (clears on app restart) ===
if "otp_codes" not in st.session_state:
    st.session_state["otp_codes"] = {}

if "user_token" in st.session_state:
    st.success("✅ You are already logged in.")
    st.stop()

# === Login Options ===
login_method = st.radio("Login using:", ["Username or Email", "Token", "Email + OTP"])

# === Option 1: Username or Email + Password ===
if login_method == "Username or Email":
    username_or_email = st.text_input("Username or Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        token = get_user_token(username_or_email)
        user = lookup_user_by_token(token) if token else None

        if user and verify_password(user.get("email"), password):
            st.session_state["user_token"] = token
            st.success(f"🎉 Welcome back, {user.get('username')}!")
        else:
            st.error("❌ Invalid credentials.")

# === Option 2: Token ===
elif login_method == "Token":
    token = st.text_input("Paste your unique token")
    if st.button("Use Token"):
        user = lookup_user_by_token(token)
        if user:
            st.session_state["user_token"] = token
            st.success(f"🔓 Access granted for {user.get('username')}!")
        else:
            st.error("❌ Invalid token.")

# === Option 3: Email + OTP ===
elif login_method == "Email + OTP":
    email = st.text_input("Enter your registered email")
    otp_sent = st.session_state.get("otp_sent", False)

    if st.button("Send OTP"):
        user = find_user_by_email(email)
        if user:
            otp = str(random.randint(100000, 999999))
            st.session_state["otp_codes"][email] = otp
            st.session_state["otp_sent"] = True
            send_otp_to_email(email, otp)
            st.success("📧 OTP sent to your email!")
        else:
            st.error("❌ No user found with this email.")

    if otp_sent:
        user_otp = st.text_input("Enter the OTP")
        if st.button("Verify OTP"):
            correct_otp = st.session_state["otp_codes"].get(email)
            if correct_otp == user_otp:
                token = get_user_token(email)
                st.session_state["user_token"] = token
                st.success("✅ OTP verified. You are logged in.")
                st.session_state.pop("otp_sent")
            else:
                st.error("❌ Invalid OTP.")
