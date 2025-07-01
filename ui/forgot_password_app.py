# ui/forgot_password_app.py

import streamlit as st
from utils.user_manager import (
    find_user_by_email,
    create_reset_token,
    reset_password_with_token
)
from utils.email_utils import EmailSender # Import the EmailSender class

st.set_page_config(page_title="🔐 Forgot Password", layout="centered")
st.title("🔑 Forgot Password")

# === Step 0: Setup ===
sender = EmailSender() # Instantiate the EmailSender

# === Step 1: Enter Email ===
email = st.text_input("Enter your registered email")
user = find_user_by_email(email) if email else None # User will be None if not found

if email and not user:
    st.error("❌ No account found with that email.")

# === Flow: Email Code for Password Reset ===
if user:
    # Check if a reset code has been sent for this email in the current session
    if "reset_code_sent" not in st.session_state or st.session_state.get("email_reset_target") != email:
        st.session_state["reset_code_sent"] = False # Reset if email changed
        st.session_state["email_reset_target"] = ""

    if not st.session_state["reset_code_sent"]:
        if st.button("Send Password Reset Link"):
            if not email:
                st.error("Please enter your email address.")
            else:
                success, msg, token = create_reset_token(email)
                if success:
                    # The reset_link should point to your reset_password_token_app.py
                    # In a deployed app, this would be your app's base URL + /reset_password_token_app
                    # For local testing, you might need to adjust this URL.
                    reset_link = f"http://localhost:8501/reset_password_token_app?token={token}"
                    email_sent_success, email_sent_msg = sender.send_password_reset_email(email, reset_link)
                    
                    if email_sent_success:
                        st.session_state["reset_code_sent"] = True
                        st.session_state["email_reset_target"] = email
                        st.success("📧 A password reset link has been sent to your email! Check your inbox.")
                        st.info(f"For local testing, link is: {reset_link}") # Display for dev/debug
                    else:
                        st.error(f"❌ Failed to send email: {email_sent_msg}. Reset token created but not delivered.")
                        st.session_state["reset_code_sent"] = True # Still mark as sent to allow manual token entry if needed
                        st.session_state["email_reset_target"] = email
                else:
                    st.error(f"❌ Failed to create reset token: {msg}")

    if st.session_state.get("reset_code_sent") and st.session_state.get("email_reset_target") == email:
        st.markdown("---")
        st.subheader("Reset Password using Token")
        st.info("A reset token has been sent to your email. Enter it below along with your new password.")
        
        token_input = st.text_input("Enter the reset token from your email")
        new_pass = st.text_input("New Password", type="password")
        confirm = st.text_input("Confirm New Password", type="password")

        if st.button("🔁 Reset Password"):
            if not token_input or not new_pass or not confirm:
                st.error("❌ All fields are required.")
            elif new_pass != confirm:
                st.error("❌ New passwords do not match.")
            elif len(new_pass) < 6: # Basic client-side check, server-side validation is more robust
                st.warning("⚠️ Password too short. Minimum 6 characters.")
            else:
                ok, msg = reset_password_with_token(token_input, new_pass)
                if ok:
                    st.success("✅ Password reset successful! You can now log in with your new password.")
                    # Optionally, send a success notification email
                    # sender.send_email(email, "Password Reset Successful", "Your password has been successfully reset.")
                    st.session_state["reset_code_sent"] = False # Clear state
                    st.session_state["email_reset_target"] = ""
                else:
                    st.error(f"❌ {msg}")
