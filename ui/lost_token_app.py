# ui/lost_token_app.py

import streamlit as st
from utils.user_manager import (
    find_user_by_email,
    verify_recovery,
    reset_user_token
)
from utils.email_utils import EmailSender

st.set_page_config(page_title="🔑 Lost Token Recovery", layout="centered")
st.title("🔐 Recover Your User Token")

# === Step 1: Ask for email ===
email = st.text_input("Enter your registered email")

if email:
    user = find_user_by_email(email)

    if not user:
        st.error("❌ No account found with this email.")
    else:
        st.success("✅ Email found. Let's verify your identity.")

        # === Step 2: Security Question ===
        question = user.get("security_q", "No security question set.")
        st.markdown(f"**🔒 Security Question:** {question}")
        answer = st.text_input("Your Answer")

        if answer:
            if verify_recovery(email, question, answer):
                st.success("🎯 Identity verified!")

                # === Step 3: Reset Token ===
                if st.button("🔁 Generate New Token"):
                    new_token = reset_user_token(email)
                    if new_token:
                        sender = EmailSender()
                        success, msg = sender.send_token_email(email=email, username=user.get("username"), token=new_token)
                        if success:
                            st.success("✅ A new token has been sent to your email.")
                        else:
                            st.warning("⚠️ Token generated but email delivery failed.")
                    else:
                        st.error("❌ Could not generate a new token.")
            else:
                st.error("❌ Incorrect answer to the security question.")
