# ui/forgot_password_app.py

import streamlit as st
from utils.user_manager import (
    find_user_by_email,
    verify_recovery,
    update_password
)
from utils.email_utils import send_email

st.set_page_config(page_title="🔐 Forgot Password", layout="centered")
st.title("🔑 Forgot Password")

# === Step 1: Enter Email ===
email = st.text_input("Enter your registered email address")

if email:
    user = find_user_by_email(email)
    if not user:
        st.error("❌ No account found with that email.")
    else:
        st.success("✅ Email found. Please answer your security question:")

        # === Step 2: Security Question ===
        question = user.get("security_q", "No security question set.")
        st.write(f"🔐 Security Question: **{question}**")
        answer = st.text_input("Your Answer")

        if answer:
            if verify_recovery(email, question, answer):
                st.success("🧠 Verified! Set a new password below:")

                # === Step 3: Set New Password ===
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")

                if st.button("🔁 Reset Password"):
                    if new_password != confirm_password:
                        st.error("❌ Passwords do not match.")
                    elif len(new_password) < 5:
                        st.warning("⚠️ Password should be at least 5 characters.")
                    else:
                        updated = update_password(email, new_password)
                        if updated:
                            st.success("✅ Password updated successfully!")

                            # Optional: Email confirmation
                            send_email(
                                to_email=email,
                                subject="🔐 Your password was reset",
                                body="Your password was changed via the Smart Assistant. If this wasn't you, please contact support immediately."
                            )
                        else:
                            st.error("❌ Failed to update password.")
            else:
                st.error("❌ Incorrect answer to the security question.")
