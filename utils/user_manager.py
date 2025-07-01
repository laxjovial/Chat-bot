# utils/user_manager.py

import uuid
import logging
import threading
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import streamlit as st

# Configure logging
logger = logging.getLogger(__name__)

# === Thread-safe in-memory storage ===
# Note: For production, consider Redis or a database
users_store: Dict[str, Dict[str, Any]] = {}
reset_tokens_store: Dict[str, Dict[str, Any]] = {}
users_lock = threading.Lock()
tokens_lock = threading.Lock()

# === Security Configuration ===
class SecurityConfig:
    PASSWORD_MIN_LENGTH = 8
    TOKEN_EXPIRY_HOURS = 24
    RESET_TOKEN_EXPIRY_MINUTES = 15
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30

# === Password Security ===
def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
    """
    Hash password using PBKDF2 with salt (secure for passwords).
    
    Args:
        password (str): Plain text password
        salt (str): Optional salt (generated if not provided)
    
    Returns:
        Tuple[str, str]: (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(32)
    
    # Use PBKDF2 with SHA-256, 100000 iterations
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    
    return password_hash, salt

def verify_password(email: str, password: str) -> bool:
    """
    Verify user password against stored hash.
    
    Args:
        email (str): User email
        password (str): Plain text password to verify
    
    Returns:
        bool: True if password is correct
    """
    try:
        with users_lock:
            user = find_user_by_email(email)
            if not user:
                return False
            
            stored_hash = user.get("password_hash", "")
            salt = user.get("salt", "")
            
            if not stored_hash or not salt:
                return False
            
            computed_hash, _ = hash_password(password, salt)
            return secrets.compare_digest(stored_hash, computed_hash)
            
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    
    Args:
        password (str): Password to validate
    
    Returns:
        Tuple[bool, str]: (is_valid, message)
    """
    if len(password) < SecurityConfig.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {SecurityConfig.PASSWORD_MIN_LENGTH} characters"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    return True, "Password is strong"

# === Token Generation ===
def generate_user_token(prefix: str = "usr") -> str:
    """Generate a unique user token."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"

def generate_reset_token() -> str:
    """Generate a secure reset token."""
    return secrets.token_urlsafe(32)

# === User Management ===
def create_user(username: str, email: str, password: str = "", tier: str = "free") -> Tuple[bool, str, str]:
    """
    Create a new user account.
    
    Args:
        username (str): Username
        email (str): Email address
        password (str): Password (optional for token-only access)
        tier (str): User tier (free, pro, etc.)
    
    Returns:
        Tuple[bool, str, str]: (success, message, user_token)
    """
    try:
        # Validate email format
        if not _is_valid_email(email):
            return False, "Invalid email format", ""
        
        # Validate password if provided
        if password:
            is_valid, msg = validate_password_strength(password)
            if not is_valid:
                return False, msg, ""
        
        with users_lock:
            # Check if email already exists
            existing_user = find_user_by_email(email)
            if existing_user:
                return False, "Email already registered", existing_user.get("token", "")
            
            # Check if username already exists
            if find_user_by_username(username):
                return False, "Username already taken", ""
            
            # Create new user
            token = generate_user_token()
            password_hash, salt = "", ""
            
            if password:
                password_hash, salt = hash_password(password)
            
            user_data = {
                "token": token,
                "username": username,
                "email": email,
                "tier": tier,
                "created_at": datetime.utcnow().isoformat(),
                "password_hash": password_hash,
                "salt": salt,
                "last_login": None,
                "login_count": 0,
                "failed_login_attempts": 0,
                "locked_until": None,
                "is_active": True
            }
            
            users_store[token] = user_data
            logger.info(f"User created: {username} ({email})")
            
            return True, "User created successfully", token
            
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False, f"Failed to create user: {str(e)}", ""

def find_user_by_email(email: str) -> Dict[str, Any]:
    """
    Find user by email address.
    
    Args:
        email (str): Email to search for
    
    Returns:
        Dict[str, Any]: User data or empty dict if not found
    """
    for user_data in users_store.values():
        if user_data.get("email", "").lower() == email.lower():
            return user_data
    return {}

def find_user_by_username(username: str) -> Dict[str, Any]:
    """
    Find user by username.
    
    Args:
        username (str): Username to search for
    
    Returns:
        Dict[str, Any]: User data or empty dict if not found
    """
    for user_data in users_store.values():
        if user_data.get("username", "").lower() == username.lower():
            return user_data
    return {}

def find_user_by_token(token: str) -> Dict[str, Any]:
    """
    Find user by token.
    
    Args:
        token (str): User token
    
    Returns:
        Dict[str, Any]: User data or empty dict if not found
    """
    return users_store.get(token, {})

def get_user_token(username_or_email: str) -> Optional[str]:
    """
    Get user token by username or email.
    
    Args:
        username_or_email (str): Username or email
    
    Returns:
        Optional[str]: User token if found
    """
    # Try email first
    user = find_user_by_email(username_or_email)
    if user:
        return user.get("token")
    
    # Try username
    user = find_user_by_username(username_or_email)
    if user:
        return user.get("token")
    
    return None

def authenticate_user(username_or_email: str, password: str) -> Tuple[bool, str, str]:
    """
    Authenticate user with username/email and password.
    
    Args:
        username_or_email (str): Username or email
        password (str): Password
    
    Returns:
        Tuple[bool, str, str]: (success, message, user_token)
    """
    try:
        with users_lock:
            # Find user
            user = find_user_by_email(username_or_email)
            if not user:
                user = find_user_by_username(username_or_email)
            
            if not user:
                return False, "User not found", ""
            
            # Check if account is active
            if not user.get("is_active", True):
                return False, "Account is deactivated", ""
            
            # Check if account is locked
            locked_until = user.get("locked_until")
            if locked_until:
                if datetime.utcnow() < datetime.fromisoformat(locked_until):
                    return False, "Account is temporarily locked", ""
                else:
                    # Unlock account
                    user["locked_until"] = None
                    user["failed_login_attempts"] = 0
            
            # Verify password
            if not verify_password(user["email"], password):
                # Increment failed attempts
                user["failed_login_attempts"] = user.get("failed_login_attempts", 0) + 1
                
                # Lock account if too many failed attempts
                if user["failed_login_attempts"] >= SecurityConfig.MAX_LOGIN_ATTEMPTS:
                    lockout_time = datetime.utcnow() + timedelta(minutes=SecurityConfig.LOCKOUT_DURATION_MINUTES)
                    user["locked_until"] = lockout_time.isoformat()
                    return False, f"Too many failed attempts. Account locked for {SecurityConfig.LOCKOUT_DURATION_MINUTES} minutes", ""
                
                remaining_attempts = SecurityConfig.MAX_LOGIN_ATTEMPTS - user["failed_login_attempts"]
                return False, f"Invalid password. {remaining_attempts} attempts remaining", ""
            
            # Successful login
            user["failed_login_attempts"] = 0
            user["locked_until"] = None
            update_login_stats(user["token"])
            
            return True, "Login successful", user["token"]
            
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return False, "Authentication failed", ""

def update_login_stats(token: str) -> None:
    """
    Update user login statistics.
    
    Args:
        token (str): User token
    """
    try:
        with users_lock:
            if token in users_store:
                users_store[token]["last_login"] = datetime.utcnow().isoformat()
                users_store[token]["login_count"] = users_store[token].get("login_count", 0) + 1
                logger.info(f"Login stats updated for token: {token[:8]}...")
    except Exception as e:
        logger.error(f"Error updating login stats: {e}")

def change_password(token: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """
    Change user password.
    
    Args:
        token (str): User token
        old_password (str): Current password
        new_password (str): New password
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        with users_lock:
            user = users_store.get(token)
            if not user:
                return False, "User not found"
            
            # Verify old password
            if not verify_password(user["email"], old_password):
                return False, "Current password is incorrect"
            
            # Validate new password
            is_valid, msg = validate_password_strength(new_password)
            if not is_valid:
                return False, msg
            
            # Update password
            password_hash, salt = hash_password(new_password)
            user["password_hash"] = password_hash
            user["salt"] = salt
            
            logger.info(f"Password changed for user: {user['email']}")
            return True, "Password updated successfully"
            
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return False, "Failed to change password"

# === Password Reset ===
def create_reset_token(email: str) -> Tuple[bool, str, str]:
    """
    Create a password reset token for email.
    
    Args:
        email (str): User email
    
    Returns:
        Tuple[bool, str, str]: (success, message, reset_token)
    """
    try:
        user = find_user_by_email(email)
        if not user:
            return False, "Email not found", ""
        
        with tokens_lock:
            reset_token = generate_reset_token()
            expiry_time = datetime.utcnow() + timedelta(minutes=SecurityConfig.RESET_TOKEN_EXPIRY_MINUTES)
            
            reset_tokens_store[reset_token] = {
                "email": email,
                "expires_at": expiry_time.isoformat(),
                "used": False
            }
            
            logger.info(f"Reset token created for: {email}")
            return True, "Reset token created", reset_token
            
    except Exception as e:
        logger.error(f"Error creating reset token: {e}")
        return False, "Failed to create reset token", ""

def validate_reset_token(token: str) -> Tuple[bool, str, str]:
    """
    Validate a password reset token.
    
    Args:
        token (str): Reset token
    
    Returns:
        Tuple[bool, str, str]: (is_valid, message, email)
    """
    try:
        with tokens_lock:
            token_data = reset_tokens_store.get(token)
            if not token_data:
                return False, "Invalid reset token", ""
            
            if token_data.get("used", False):
                return False, "Reset token already used", ""
            
            expiry_time = datetime.fromisoformat(token_data["expires_at"])
            if datetime.utcnow() > expiry_time:
                del reset_tokens_store[token]
                return False, "Reset token expired", ""
            
            return True, "Valid reset token", token_data["email"]
            
    except Exception as e:
        logger.error(f"Error validating reset token: {e}")
        return False, "Token validation failed", ""

def reset_password_with_token(token: str, new_password: str) -> Tuple[bool, str]:
    """
    Reset password using a valid reset token.
    
    Args:
        token (str): Reset token
        new_password (str): New password
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        # Validate token
        is_valid, msg, email = validate_reset_token(token)
        if not is_valid:
            return False, msg
        
        # Validate new password
        is_valid, msg = validate_password_strength(new_password)
        if not is_valid:
            return False, msg
        
        with users_lock, tokens_lock:
            # Find user
            user = find_user_by_email(email)
            if not user:
                return False, "User not found"
            
            # Update password
            password_hash, salt = hash_password(new_password)
            user["password_hash"] = password_hash
            user["salt"] = salt
            
            # Reset login attempts
            user["failed_login_attempts"] = 0
            user["locked_until"] = None
            
            # Mark token as used
            reset_tokens_store[token]["used"] = True
            
            logger.info(f"Password reset completed for: {email}")
            return True, "Password reset successfully"
            
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        return False, "Failed to reset password"

# === Utility Functions ===
def _is_valid_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def cleanup_expired_tokens() -> int:
    """
    Clean up expired reset tokens.
    
    Returns:
        int: Number of tokens cleaned up
    """
    current_time = datetime.utcnow()
    cleaned_count = 0
    
    with tokens_lock:
        expired_tokens = []
        for token, data in reset_tokens_store.items():
            expiry = datetime.fromisoformat(data['expires_at'])
            if current_time > expiry:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del reset_tokens_store[token]
            cleaned_count += 1
    
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} expired reset tokens")
    
    return cleaned_count

def get_user_stats() -> Dict[str, int]:
    """
    Get user statistics.
    
    Returns:
        Dict[str, int]: User statistics
    """
    with users_lock:
        total_users = len(users_store)
        active_users = sum(1 for user in users_store.values() if user.get("is_active", True))
        locked_users = sum(1 for user in users_store.values() if user.get("locked_until"))
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "locked_users": locked_users
    }

# === Streamlit Integration ===
def get_current_user() -> Dict[str, Any]:
    """Get current user from Streamlit session state."""
    if hasattr(st, 'session_state') and 'user_token' in st.session_state:
        return find_user_by_token(st.session_state.user_token)
    return {}

def set_current_user(token: str) -> None:
    """Set current user in Streamlit session state."""
    if hasattr(st, 'session_state'):
        st.session_state.user_token = token

def logout_current_user() -> None:
    """Logout current user from Streamlit session state."""
    if hasattr(st, 'session_state') and 'user_token' in st.session_state:
        del st.session_state.user_token
