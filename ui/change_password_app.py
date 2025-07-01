# ui/change_password_app.py

import streamlit as st
from utils.user_manager import change_password, get_current_user

st.set_page_config(page_title="🔐 Change Password", layout="centered")
st.title("🔐 Change Your Password")

# === Session Check ===
user = get_current_user()
if not user:
    st.warning("⚠️ You must be logged in to change your password.")
    st.stop()

# === Input Fields ===
st.write(f"👤 Logged in as: **{user.get('username')}**")
old_password = st.text_input("🔑 Current Password", type="password")
new_password = st.text_input("🆕 New Password", type="password")
confirm_password = st.text_input("✅ Confirm New Password", type="password")

# === Change Password Action ===
if st.button("🔁 Update Password"):
    if not old_password or not new_password or not confirm_password:
        st.error("❌ All fields are required.")
    elif new_password != confirm_password:
        st.error("❌ New passwords do not match.")
    else:
        success, msg = change_password(user["token"], old_password, new_password)
        if success:
            st.success("✅ Password changed successfully!")
        else:
            st.error(f"❌ {msg}")
