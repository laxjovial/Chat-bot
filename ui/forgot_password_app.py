# ui/forgot_password_app.py

import streamlit as st
from utils.user_manager import (
    find_user_by_email,
    verify_recovery,
    reset_password,
)

st.set_page_config(page_title="🔐 Forgot Password", layout="centered")
st.title("🔑 Forgot Your Password?")

email = st.text_input("Enter your registered email")

if email:
    user = find_user_by_email(email)

    if user:
        st.info(f"Security Question: {user['security_q']}")
        answer = st.text_input("Answer to Security Question")
        new_password = st.text_input("New Password", type="password")
        confirm = st.text_input("Confirm New Password", type="password")

        if st.button("Reset Password"):
            if not answer or not new_password or not confirm:
                st.error("Please fill in all fields.")
            elif new_password != confirm:
                st.error("Passwords do not match.")
            elif verify_recovery(email, user["security_q"], answer):
                reset_password(email, new_password)
                st.success("✅ Password has been reset. You can now log in.")
            else:
                st.error("❌ Incorrect answer to security question.")
    else:
        st.warning("No user found with this email.")
