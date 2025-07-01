# ui/lost_token_app.py

import streamlit as st
from utils.user_manager import (
    find_user_by_email,
    verify_recovery,
    reset_user_token
)
from utils.email_utils import send_email

st.set_page_config(page_title="🔑 Recover Lost Token", layout="centered")
st.title("🔁 Lost Token Recovery")

# === Step 1: Enter Email ===
email = st.text_input("Enter your registered email")

if email:
    user = find_user_by_email(email)
    if not user:
        st.error("❌ No account found with that email.")
    else:
        st.success("✅ Email found. Please answer your security question:")

        # === Step 2: Security Q ===
        question = user.get("security_q", "No question set.")
        st.write(f"🔐 Security Question: **{question}**")
        answer = st.text_input("Your Answer")

        if answer:
            if verify_recovery(email, question, answer):
                st.success("🧠 Verified! You can now generate a new token.")
                
                if st.button("🔁 Generate New Token"):
                    new_token = reset_user_token(email)
                    if new_token:
                        st.success("✅ New token created and sent to your email.")
                        send_email(
                            to_email=email,
                            subject="🆕 Your New Access Token",
                            body=f"Hello!\n\nA new token has been generated for your account:\n\n🔑 {new_token}\n\nKeep this token safe and private.\n\n— Smart Assistant"
                        )
                    else:
                        st.error("❌ Could not reset token.")
            else:
                st.error("❌ Incorrect answer to the security question.")
