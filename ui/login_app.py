# ui/login_app.py

import streamlit as st
from utils.user_manager import (
    get_user_token, lookup_user_by_token,
    find_user_by_email, verify_password, 
    create_otp, verify_otp, update_login_stats
)
from utils.email_utils import send_otp_email, send_security_alert

# === Page Configuration ===
st.set_page_config(
    page_title="🔐 Login", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# === Initialize Session State ===
if "login_attempts" not in st.session_state:
    st.session_state.login_attempts = 0
if "otp_sent" not in st.session_state:
    st.session_state.otp_sent = False
if "otp_email" not in st.session_state:
    st.session_state.otp_email = ""

# === Check if already logged in ===
if "user_token" in st.session_state:
    user = lookup_user_by_token(st.session_state.user_token)
    st.success(f"✅ You are already logged in as {user.get('username', 'User')}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏠 Go to Dashboard", use_container_width=True):
            # Redirect to main app or dashboard
            st.info("🚀 Redirecting to dashboard...")
    
    with col2:
        if st.button("🚪 Logout", use_container_width=True):
            del st.session_state.user_token
            if "login_attempts" in st.session_state:
                del st.session_state.login_attempts
            if "otp_sent" in st.session_state:
                del st.session_state.otp_sent
            if "otp_email" in st.session_state:
                del st.session_state.otp_email
            st.rerun()
    
    st.stop()

# === Main App Header ===
st.title("🔐 Secure Login")
st.markdown("---")

# === Security Warning for Multiple Failed Attempts ===
if st.session_state.login_attempts >= 3:
    st.error("⚠️ Multiple failed login attempts detected. Please try again later or use the 'Forgot Password' option.")
    if st.button("🔄 Reset Login Attempts"):
        st.session_state.login_attempts = 0
        st.rerun()

# === Login Method Selection ===
login_method = st.radio(
    "Choose your login method:",
    ["🔑 Username/Email + Password", "🎫 Access Token", "📧 Email + OTP"],
    horizontal=False
)

st.markdown("---")

# === Method 1: Username/Email + Password ===
if login_method == "🔑 Username/Email + Password":
    st.subheader("Login with Credentials")
    
    username_or_email = st.text_input("📧 Username or Email", placeholder="Enter your username or email")
    password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🚀 Login", type="primary", use_container_width=True):
            if not username_or_email or not password:
                st.error("❌ Please fill in all fields")
            elif st.session_state.login_attempts >= 5:
                st.error("❌ Too many failed attempts. Please try again later.")
            else:
                # Get user token and verify credentials
                token = get_user_token(username_or_email)
                user = lookup_user_by_token(token) if token else None
                
                if user and verify_password(user.get("email"), password):
                    # Successful login
                    st.session_state.user_token = token
                    st.session_state.login_attempts = 0  # Reset attempts
                    
                    # Update login stats
                    update_login_stats(token)
                    
                    # Send security alert for login
                    send_security_alert(user.get("email"), "Successful login from new session")
                    
                    st.success(f"🎉 Welcome back, {user.get('username')}!")
                    st.balloons()
                    
                    # Auto-refresh after success
                    st.rerun()
                else:
                    # Failed login
                    st.session_state.login_attempts += 1
                    st.error(f"❌ Invalid credentials. Attempt {st.session_state.login_attempts}/5")
    
    with col2:
        if st.button("🔑 Forgot Password?", use_container_width=True):
            st.info("🔗 Click here to reset your password")
            # In a real app, you'd redirect to forgot password page

# === Method 2: Access Token ===
elif login_method == "🎫 Access Token":
    st.subheader("Login with Access Token")
    st.info("💡 Use the unique token that was sent to your email during registration")
    
    token = st.text_input("🎫 Access Token", placeholder="Paste your unique token here")
    
    if st.button("🔓 Access Account", type="primary", use_container_width=True):
        if not token:
            st.error("❌ Please enter your access token")
        else:
            user = lookup_user_by_token(token)
            if user:
                st.session_state.user_token = token
                st.session_state.login_attempts = 0  # Reset attempts
                
                # Update login stats
                update_login_stats(token)
                
                # Send security alert
                send_security_alert(user.get("email"), "Login via access token")
                
                st.success(f"🔓 Access granted for {user.get('username')}!")
                st.balloons()
                
                # Auto-refresh after success
                st.rerun()
            else:
                st.session_state.login_attempts += 1
                st.error(f"❌ Invalid token. Attempt {st.session_state.login_attempts}/5")

# === Method 3: Email + OTP ===
elif login_method == "📧 Email + OTP":
    st.subheader("Login with Email OTP")
    st.info("🔒 We'll send a one-time password to your registered email")
    
    email = st.text_input("📧 Email Address", placeholder="Enter your registered email")
    
    # Step 1: Send OTP
    if not st.session_state.otp_sent or st.session_state.otp_email != email:
        if st.button("📨 Send OTP", type="secondary", use_container_width=True):
            if not email:
                st.error("❌ Please enter your email address")
            else:
                user = find_user_by_email(email)
                if user:
                    # Create and send OTP
                    otp = create_otp(email)
                    if otp and send_otp_email(email, otp):
                        st.session_state.otp_sent = True
                        st.session_state.otp_email = email
                        st.success("📧 OTP sent to your email! Check your inbox.")
                        st.rerun()
                    else:
                        st.error("❌ Failed to send OTP. Please try again.")
                else:
                    st.error("❌ No account found with this email address")
    
    # Step 2: Verify OTP
    if st.session_state.otp_sent and st.session_state.otp_email == email:
        st.success(f"📧 OTP sent to {email}")
        
        user_otp = st.text_input("🔢 Enter OTP", placeholder="Enter the 6-digit code", max_chars=6)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if st.button("✅ Verify OTP", type="primary", use_container_width=True):
                if not user_otp:
                    st.error("❌ Please enter the OTP")
                elif len(user_otp) != 6 or not user_otp.isdigit():
                    st.error("❌ OTP must be 6 digits")
                else:
                    if verify_otp(email, user_otp):
                        # Successful OTP verification
                        token = get_user_token(email)
                        st.session_state.user_token = token
                        st.session_state.login_attempts = 0
                        st.session_state.otp_sent = False
                        st.session_state.otp_email = ""
                        
                        # Update login stats
                        update_login_stats(token)
                        
                        # Send security alert
                        user = lookup_user_by_token(token)
                        send_security_alert(email, "Login via OTP verification")
                        
                        st.success(f"✅ OTP verified! Welcome back, {user.get('username')}!")
                        st.balloons()
                        
                        # Auto-refresh after
