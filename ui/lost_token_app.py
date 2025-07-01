# ui/lost_token_app.py

import streamlit as st
from utils.user_manager import find_user_by_email, create_otp, verify_otp, get_user_token
from utils.email_utils import EmailSender # Import the EmailSender class

# === Page Configuration ===
st.set_page_config(
    page_title="❓ Lost Token",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# === Initialize Session State ===
if "lost_token_email_sent" not in st.session_state:
    st.session_state.lost_token_email_sent = False
if "lost_token_email_address" not in st.session_state:
    st.session_state.lost_token_email_address = ""

# === Main App Header ===
st.title("❓ Lost Your Access Token?")
st.markdown("---")

st.info("Enter your registered email address below. We'll send your unique access token to your inbox.")

email = st.text_input("📧 Email Address", placeholder="Enter your registered email")

if st.button("🚀 Recover Access Token", type="primary", use_container_width=True):
    if not email:
        st.error("❌ Please enter your email address.")
    else:
        user = find_user_by_email(email)
        if user:
            # Get the existing token
            user_token = get_user_token(email)
            if user_token:
                # Send the token via email
                sender = EmailSender() # Instantiate EmailSender
                success, message = sender.send_access_token_email(email, user_token)
                if success:
                    st.success("✅ Your access token has been sent to your email address!")
                    st.session_state.lost_token_email_sent = True
                    st.session_state.lost_token_email_address = email
                else:
                    st.error(f"❌ Failed to send access token email: {message}. Please try again.")
            else:
                st.error("❌ Could not retrieve an access token for this email. Please ensure you have registered.")
        else:
            st.error("❌ No account found with that email address.")

st.markdown("---")
if st.session_state.lost_token_email_sent:
    st.info(f"If you don't receive the email within a few minutes, please check your spam folder or re-enter your email to try again.")
