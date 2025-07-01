# ui/forgot_password_app.py

import streamlit as st
from utils.user_manager import (
    find_user_by_email,
    verify_recovery,
    update_password,
    create_reset_token,
    reset_password_with_token
)
from utils.email_utils import EmailSender

st.set_page_config(page_title="🔐 Forgot Password", layout="centered")
st.title("🔑 Forgot Password")

# === Step 0: Setup ===
sender = EmailSender()
method = st.radio("Choose recovery method:", ["Email Code", "Security Question"])

# === Step 1: Enter Email ===
email = st.text_input("Enter your registered email")
user = find_user_by_email(email) if email else {}

if email and not user:
    st.error("❌ No account found with that email.")

# === Flow 1: Email Code ===
if method == "Email Code" and user:
    if "reset_code_sent" not in st.session_state:
        if st.button("Send Verification Code"):
            success, msg, token = create_reset_token(email)
            if success:
                sender.send_password_reset_email(email, token)
                st.session_state["reset_code_sent"] = True
                st.session_state["email_reset_target"] = email
                st.success("📧 Verification code sent!")
            else:
                st.error(f"❌ {msg}")

    if st.session_state.get("reset_code_sent") and st.session_state.get("email_reset_target") == email:
        code = st.text_input("Enter the code sent to your email")
        new_pass = st.text_input("New Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")

        if st.button("🔁 Reset Password"):
            if new_pass != confirm:
                st.error("❌ Passwords do not match.")
            elif len(new_pass) < 6:
                st.warning("⚠️ Password too short.")
            else:
                ok, msg = reset_password_with_token(code, new_pass)
                if ok:
                    st.success("✅ Password reset successful!")
                    sender.send_password_reset_success_email(email)
                else:
                    st.error(f"❌ {msg}")

# === Flow 2: Security Question ===
elif method == "Security Question" and user:
    question = user.get("security_q", "No security question set.")
    st.write(f"🔐 Security Question: **{question}**")
    answer = st.text_input("Your Answer")

    if answer:
        if verify_recovery(email, question, answer):
            st.success("🧠 Verified! Set a new password below:")
            new_pass = st.text_input("New Password", type="password")
            confirm = st.text_input("Confirm Password", type="password")

            if st.button("🔁 Reset Password (Security)"):
                if new_pass != confirm:
                    st.error("❌ Passwords do not match.")
                elif len(new_pass) < 6:
                    st.warning("⚠️ Password too short.")
                else:
                    success = update_password(email, new_pass)
                    if success:
                        st.success("✅ Password updated successfully!")
                        sender.send_password_reset_success_email(email)
                    else:
                        st.error("❌ Failed to update password.")
        else:
            st.error("❌ Incorrect answer to the security question.")
