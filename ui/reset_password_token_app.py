# ui/reset_password_token_app.py

import streamlit as st
from utils.user_manager import (
    validate_reset_token,
    reset_password_with_token
)

st.set_page_config(page_title="🔁 Reset via Token", layout="centered")
st.title("🔁 Reset Password with Token")

# === Step 1: Input reset token ===
token = st.text_input("Enter your reset token")

if token:
    is_valid, msg, email = validate_reset_token(token)

    if not is_valid:
        st.error(f"❌ {msg}")
    else:
        st.success(f"✅ Token valid for: {email}")

        # === Step 2: New password input ===
        new_pass = st.text_input("New Password", type="password")
        confirm_pass = st.text_input("Confirm Password", type="password")

        if st.button("🔒 Reset Password"):
            if not new_pass or not confirm_pass:
                st.warning("⚠️ Please fill in both fields.")
            elif new_pass != confirm_pass:
                st.error("❌ Passwords do not match.")
            else:
                success, msg = reset_password_with_token(token, new_pass)
                if success:
                    st.success("✅ Password reset successfully!")
                else:
                    st.error(f"❌ {msg}")
