# utils/user_manager.py

import uuid
import logging
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple, List
import streamlit as st

# Import the comprehensive email validation from validation_utils
from utils.validation_utils import validate_email_format, validate_password_strength as validate_password_strength_util

# Import FirestoreManager
from database.firestore_manager import FirestoreManager

# Import ConfigManager for tier capabilities
from config.config_manager import config_manager

# Configure logging
logger = logging.getLogger(__name__)

# === Initialize Firestore Manager ===
# We initialize it here to ensure it's ready when user_manager functions are called.
# The actual initialization of the Firebase app happens lazily within FirestoreManager
# to ensure Streamlit secrets are available.
firestore_db = FirestoreManager()

# === Security Configuration ===
class SecurityConfig:
    PASSWORD_MIN_LENGTH = 8
    TOKEN_EXPIRY_HOURS = 24
    RESET_TOKEN_EXPUTES = 15
    OTP_EXPIRY_MINUTES = 5 # Added for OTP
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
    
    # Use PBKDF2 with SHA-256 for hashing
    hashed_password = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000 # Number of iterations, adjust as needed for security vs. performance
    ).hex()
    
    return hashed_password, salt

def verify_password(stored_password: str, salt: str, provided_password: str) -> bool:
    """
    Verify a provided password against a stored hash and salt.
    """
    hashed_provided_password, _ = hash_password(provided_password, salt)
    return hashed_provided_password == stored_password

# === User Management ===
def create_user(
    username: str,
    email: str,
    password: str,
    tier: str = "free",
    security_q: Optional[str] = None,
    security_a: Optional[str] = None
) -> Optional[str]:
    """
    Creates a new user and stores them in Firestore.
    Returns the user's access token if successful, None otherwise.
    """
    if not validate_email_format(email):
        logger.warning(f"Invalid email format: {email}")
        st.error("Invalid email format.")
        return None

    is_strong, strength_msg = validate_password_strength_util(password, SecurityConfig.PASSWORD_MIN_LENGTH)
    if not is_strong:
        logger.warning(f"Password strength validation failed for {email}: {strength_msg}")
        st.error(strength_msg)
        return None

    # Check if user already exists by email
    existing_user = firestore_db.get_user_by_email(email)
    if existing_user:
        st.error("A user with this email already exists.")
        return None

    user_id = str(uuid.uuid4()) # Generate a unique ID for the user
    hashed_password, salt = hash_password(password)
    user_token = secrets.token_urlsafe(32) # Generate a unique access token

    user_data = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "hashed_password": hashed_password,
        "salt": salt,
        "tier": tier,
        "access_token": user_token,
        "security_question": security_q,
        "security_answer_hash": hash_password(security_a)[0] if security_a else None, # Hash security answer
        "created_at": datetime.now(timezone.utc),
        "last_login_at": None,
        "login_attempts": 0,
        "locked_until": None,
        "is_active": True,
        "roles": ["user"] # Default role for all new users
    }
    
    # Add 'admin' role if tier is 'admin' during creation
    if tier == 'admin':
        user_data['roles'].append('admin')
        # Ensure no duplicates if 'user' is already in roles
        user_data['roles'] = list(set(user_data['roles']))


    success, msg = firestore_db.add_user(user_data)
    if success:
        logger.info(f"New user created: {username} ({email}) with tier: {tier}")
        return user_token
    else:
        logger.error(f"Failed to create user {email}: {msg}")
        st.error(f"Failed to create user: {msg}")
        return None

def find_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Finds a user by email from Firestore."""
    return firestore_db.get_user_by_email(email)

def find_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Finds a user by access token from Firestore."""
    try:
        # Firestore does not have a direct 'where' clause for unique indexes if not document ID.
        # We need to query the collection.
        users = firestore_db.get_db().collection('users').where('access_token', '==', token).limit(1).stream()
        for doc in users:
            user_data = doc.to_dict()
            if user_data:
                user_data['user_id'] = doc.id # Ensure user_id is always present
                return user_data
        return None
    except Exception as e:
        logger.error(f"Error finding user by token '{token}': {e}")
        return None

def get_user_token(email: str) -> Optional[str]:
    """Retrieves a user's access token by email."""
    user = find_user_by_email(email)
    return user.get("access_token") if user else None

def lookup_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Looks up user details by token."""
    return find_user_by_token(token)

def authenticate_user(email: str, password: str) -> Tuple[bool, str, Optional[str]]:
    """
    Authenticates a user by email and password.
    Handles login attempts and account lockout.
    Returns (success, message, token)
    """
    user = find_user_by_email(email)

    if not user:
        return False, "Invalid email or password.", None

    user_id = user['user_id']
    
    # Check for account lockout
    if user.get("locked_until") and user["locked_until"] > datetime.now(timezone.utc):
        remaining_time = user["locked_until"] - datetime.now(timezone.utc)
        minutes, seconds = divmod(int(remaining_time.total_seconds()), 60)
        return False, f"Account locked. Try again in {minutes}m {seconds}s.", None

    if verify_password(user["hashed_password"], user["salt"], password):
        # Successful login: reset attempts, update last login, unlock account
        updates = {
            "login_attempts": 0,
            "last_login_at": datetime.now(timezone.utc),
            "locked_until": None # Ensure account is unlocked
        }
        firestore_db.update_user(user_id, updates)
        logger.info(f"User {email} authenticated successfully.")
        return True, "Login successful!", user["access_token"]
    else:
        # Failed login: increment attempts
        current_attempts = user.get("login_attempts", 0) + 1
        updates = {"login_attempts": current_attempts}
        
        if current_attempts >= SecurityConfig.MAX_LOGIN_ATTEMPTS:
            locked_until = datetime.now(timezone.utc) + timedelta(minutes=SecurityConfig.LOCKOUT_DURATION_MINUTES)
            updates["locked_until"] = locked_until
            updates["login_attempts"] = 0 # Reset attempts after lockout
            firestore_db.update_user(user_id, updates)
            logger.warning(f"User {email} account locked due to too many failed attempts.")
            return False, f"Too many failed attempts. Account locked for {SecurityConfig.LOCKOUT_DURATION_MINUTES} minutes.", None
        else:
            firestore_db.update_user(user_id, updates)
            logger.warning(f"Failed login attempt for {email}. Attempts: {current_attempts}")
            return False, "Invalid email or password.", None

def change_password(user_token: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """
    Allows a logged-in user to change their password.
    """
    user = find_user_by_token(user_token)
    if not user:
        return False, "User not found or session invalid."

    user_id = user['user_id']

    # Verify old password
    if not verify_password(user["hashed_password"], user["salt"], old_password):
        return False, "Current password is incorrect."

    # Validate new password strength
    is_strong, strength_msg = validate_password_strength_util(new_password, SecurityConfig.PASSWORD_MIN_LENGTH)
    if not is_strong:
        return False, strength_msg

    # Hash and update new password
    new_hashed_password, new_salt = hash_password(new_password)
    updates = {
        "hashed_password": new_hashed_password,
        "salt": new_salt
    }
    success, msg = firestore_db.update_user(user_id, updates)
    if success:
        logger.info(f"Password changed for user {user.get('email')}")
        return True, "Password changed successfully."
    else:
        logger.error(f"Failed to change password for user {user.get('email')}: {msg}")
        return False, f"Failed to change password: {msg}"

def update_login_stats(user_token: str) -> None:
    """Updates last login timestamp and resets attempts for a user."""
    user = find_user_by_token(user_token)
    if user:
        user_id = user['user_id']
        updates = {
            "last_login_at": datetime.now(timezone.utc),
            "login_attempts": 0,
            "locked_until": None # Ensure account is unlocked on successful login/OTP
        }
        firestore_db.update_user(user_id, updates)
        logger.info(f"Login stats updated for user {user.get('email')}.")
    else:
        logger.warning(f"Attempted to update login stats for non-existent token: {user_token}")

# === Security Question Recovery ===
def verify_security_answer(email: str, answer: str) -> Tuple[bool, str]:
    """
    Verifies the security answer for a given email.
    Returns (is_correct, message).
    """
    user = find_user_by_email(email)
    if not user:
        return False, "No user found with that email."
    
    stored_answer_hash = user.get("security_answer_hash")
    if not stored_answer_hash:
        return False, "No security question answer set for this user."
    
    provided_answer_hash, _ = hash_password(answer) # Hash the provided answer
    
    if provided_answer_hash == stored_answer_hash:
        return True, "Security answer verified successfully."
    else:
        return False, "Incorrect security answer."

def reset_password_with_security_answer(email: str, new_password: str) -> Tuple[bool, str]:
    """
    Resets password after security answer verification.
    """
    user = find_user_by_email(email)
    if not user:
        return False, "User not found."

    user_id = user['user_id']

    is_strong, strength_msg = validate_password_strength_util(new_password, SecurityConfig.PASSWORD_MIN_LENGTH)
    if not is_strong:
        return False, strength_msg

    new_hashed_password, new_salt = hash_password(new_password)
    updates = {
        "hashed_password": new_hashed_password,
        "salt": new_salt
    }
    success, msg = firestore_db.update_user(user_id, updates)
    if success:
        logger.info(f"Password reset via security answer for user {email}")
        return True, "Password reset successfully."
    else:
        logger.error(f"Failed to reset password via security answer for user {email}: {msg}")
        return False, f"Failed to reset password: {msg}"

# === Password Reset Tokens ===
def create_reset_token(email: str) -> Tuple[bool, str, Optional[str]]:
    """
    Generates a unique password reset token and stores it in Firestore.
    Returns (success, message, token).
    """
    user = find_user_by_email(email)
    if not user:
        return False, "No user found with that email.", None
    
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=SecurityConfig.RESET_TOKEN_EXPIRY_MINUTES)
    
    token_data = {
        "token_id": token,
        "user_id": user['user_id'],
        "email": email,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
        "is_used": False
    }

    success, msg = firestore_db.add_reset_token(token, token_data)
    if success:
        logger.info(f"Password reset token created for {email}")
        return True, "Password reset token created.", token
    else:
        logger.error(f"Failed to create reset token for {email}: {msg}")
        return False, f"Failed to create reset token: {msg}", None

def validate_reset_token(token: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validates a password reset token from Firestore.
    Returns (is_valid, message, email_associated_with_token).
    """
    token_data = firestore_db.get_reset_token(token)
    
    if not token_data:
        return False, "Invalid or expired token."
    
    if token_data.get("is_used"):
        return False, "Token has already been used."

    if token_data.get("expires_at") and token_data["expires_at"] < datetime.now(timezone.utc):
        firestore_db.delete_reset_token(token) # Clean up expired token
        return False, "Token has expired."
        
    return True, "Token is valid.", token_data.get("email")

def reset_password_with_token(token: str, new_password: str) -> Tuple[bool, str]:
    """
    Resets user's password using a valid reset token.
    Marks the token as used.
    """
    is_valid, msg, email = validate_reset_token(token)
    if not is_valid:
        return False, msg

    user = find_user_by_email(email)
    if not user:
        # This should ideally not happen if token validation passed, but as a safeguard
        return False, "Associated user not found."

    user_id = user['user_id']

    is_strong, strength_msg = validate_password_strength_util(new_password, SecurityConfig.PASSWORD_MIN_LENGTH)
    if not is_strong:
        return False, strength_msg

    new_hashed_password, new_salt = hash_password(new_password)
    
    # Update user's password
    user_update_success, user_update_msg = firestore_db.update_user(user_id, {
        "hashed_password": new_hashed_password,
        "salt": new_salt
    })

    if user_update_success:
        # Mark token as used
        token_update_success, token_update_msg = firestore_db.update_reset_token(token, {"is_used": True})
        if not token_update_success:
            logger.error(f"Failed to mark reset token {token} as used: {token_update_msg}")
        
        logger.info(f"Password reset successfully for {email} using token.")
        return True, "Password reset successfully."
    else:
        logger.error(f"Failed to reset password for {email} using token: {user_update_msg}")
        return False, f"Failed to reset password: {user_update_msg}"

# === OTP (One-Time Password) Management ===
def create_otp(identifier: str, purpose: str = "login") -> Tuple[bool, str, Optional[str]]:
    """
    Generates an OTP and stores it in Firestore for the given identifier (e.g., email).
    Purpose can be 'login' or 'registration'.
    Returns (success, message, otp).
    """
    # Clean up expired OTPs for this identifier before creating a new one
    firestore_db.clean_expired_otps()

    otp_code = ''.join(secrets.choice('0123456789') for _ in range(6)) # 6-digit OTP
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=SecurityConfig.OTP_EXPIRY_MINUTES)
    
    otp_data = {
        "otp": otp_code,
        "identifier": identifier,
        "purpose": purpose,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at,
        "attempts": 0,
        "is_verified": False
    }

    success, msg = firestore_db.add_otp(identifier, otp_data)
    if success:
        logger.info(f"OTP created for {identifier} for {purpose}.")
        return True, "OTP created successfully.", otp_code
    else:
        logger.error(f"Failed to create OTP for {identifier}: {msg}")
        return False, f"Failed to create OTP: {msg}", None

def verify_otp(identifier: str, otp_code: str) -> Tuple[bool, str]:
    """
    Verifies an OTP against the stored value in Firestore.
    """
    otp_entry = firestore_db.get_otp(identifier)

    if not otp_entry:
        return False, "Invalid or expired OTP."

    if otp_entry.get("is_verified"):
        return False, "OTP has already been used."

    if otp_entry.get("expires_at") and otp_entry["expires_at"] < datetime.now(timezone.utc):
        firestore_db.delete_otp(identifier) # Clean up expired OTP
        return False, "OTP has expired."
    
    if otp_entry.get("otp") == otp_code:
        # Mark OTP as verified/used
        success, msg = firestore_db.update_otp(identifier, {"is_verified": True})
        if not success:
            logger.error(f"Failed to mark OTP {identifier} as verified: {msg}")
        logger.info(f"OTP verified for {identifier}.")
        return True, "OTP verified successfully."
    else:
        # Increment attempts for this OTP (if needed, though current design deletes on expiry)
        # For now, just return failure without persisting attempt count on wrong OTP
        return False, "Incorrect OTP."

def clean_expired_data() -> None:
    """Cleans up expired reset tokens and OTPs from the database."""
    logger.info("Running scheduled cleanup of expired data...")
    cleaned_tokens_count = firestore_db.clean_expired_reset_tokens()
    cleaned_otps_count = firestore_db.clean_expired_otps()
    logger.info(f"Cleanup complete: {cleaned_tokens_count} reset tokens, {cleaned_otps_count} OTPs removed.")

# === Streamlit Integration ===
def get_current_user() -> Dict[str, Any]:
    """Get current user from Streamlit session state."""
    if hasattr(st, 'session_state') and 'user_token' in st.session_state and st.session_state.user_token:
        user = find_user_by_token(st.session_state.user_token)
        if user and user.get('is_active', True): # Ensure user is active
            return user
    return {}

def set_current_user(token: str) -> None:
    """Set current user in Streamlit session state."""
    if hasattr(st, 'session_state'):
        st.session_state.user_token = token

def logout_user() -> None:
    """Clear user from Streamlit session state."""
    if hasattr(st, 'session_state') and 'user_token' in st.session_state:
        del st.session_state.user_token
    logger.info("User logged out.")

def get_user_tier_capability(user_token: Optional[str], capability_key: str, default_value: Any = None) -> Any:
    """
    Retrieves a specific capability value for the current user's tier from config.yml.
    If user is admin, they implicitly have full access (True for booleans, max for numbers).
    """
    user = find_user_by_token(user_token)
    user_tier = user.get('tier', 'free') if user else 'free'
    user_roles = user.get('roles', []) if user else []

    # Admins have full access to all capabilities unless explicitly restricted for admin tier
    if 'admin' in user_roles:
        # For boolean capabilities, admin always gets True
        if isinstance(default_value, bool):
            return True
        # For numerical limits, admin gets a very high value or specific admin limit
        if isinstance(default_value, (int, float)):
            # You might define specific admin limits in config if needed,
            # but for now, assume effectively unlimited for admin.
            return float('inf') if default_value is not None else default_value
        return default_value # For other types, return default or specific admin config if added

    # Retrieve capability from config_manager based on user's tier
    # Path example: 'tiers.pro.web_search_limit_chars'
    return config_manager.get(f'tiers.{user_tier}.{capability_key}', default_value)


# Self-contained test (if executed directly)
if __name__ == "__main__":
    import os
    import sys
    import shutil
    from unittest.mock import MagicMock

    # Setup dummy Streamlit secrets and config for testing purposes if not running in Streamlit env
    # This part mocks Streamlit's behavior for standalone testing.
    class MockSecrets:
        def __init__(self):
            # Mimic secrets.toml structure
            self.firestore = {
                "type": "service_account",
                "project_id": "test-project-id",
                "private_key_id": "test-private-key-id",
                "private_key": "-----BEGIN PRIVATE KEY-----\\nFAKE_TEST_KEY\\n-----END PRIVATE KEY-----\\n",
                "client_email": "test-service-account@test-project-id.iam.gserviceaccount.com",
            }
            self.email = {
                "smtp_user": "test_user@example.com",
                "smtp_password": "test_password"
            }

    if not hasattr(st, 'secrets'):
        st.secrets = MockSecrets()
        print("Mocked st.secrets for standalone testing.")

    # Create dummy config.yml for ConfigManager
    dummy_data_dir = Path("data")
    dummy_config_path = dummy_data_dir / "config.yml"
    dummy_smtp_config_path = dummy_data_dir / "smtp_config.yml"
    dummy_media_apis_path = dummy_data_dir / "media_apis.yaml"
    dummy_sports_apis_path = dummy_data_dir / "sports_apis.yaml"
    dummy_finance_apis_path = dummy_data_dir / "finance_apis.yaml"
    dummy_entertainment_apis_path = dummy_data_dir / "entertainment_apis.yaml"
    dummy_medical_apis_path = dummy_data_dir / "medical_apis.yaml"
    dummy_legal_apis_path = dummy_data_dir / "legal_apis.yaml"
    dummy_weather_apis_path = dummy_data_dir / "weather_apis.yaml"
    dummy_news_apis_path = dummy_data_dir / "news_apis.yaml"


    dummy_data_dir.mkdir(exist_ok=True)

    with open(dummy_config_path, "w") as f:
        f.write("""
app:
  name: "Test App"
llm:
  provider: 'mock'
email:
  from_email: 'test@example.com'
  smtp_server: 'smtp.test.com'
  smtp_port: 587
tiers:
  free:
    max_agent_modules: 1
    web_search_limit_chars: 500
    uploaded_docs_query_enabled: false
    charts_enabled: false
    data_analysis_enabled: false
    sentiment_analysis_enabled: false
  pro:
    max_agent_modules: 7
    web_search_limit_chars: 3000
    uploaded_docs_query_enabled: true
    charts_enabled: true
    data_analysis_enabled: true
    sentiment_analysis_enabled: false
  elite:
    max_agent_modules: 7
    web_search_limit_chars: 5000
    uploaded_docs_query_enabled: true
    charts_enabled: true
    data_analysis_enabled: true
    sentiment_analysis_enabled: true
""")

    # Create dummy YAMLs for other agents if they don't exist
    for path in [dummy_smtp_config_path, dummy_media_apis_path, dummy_sports_apis_path,
                 dummy_finance_apis_path, dummy_entertainment_apis_path,
                 dummy_medical_apis_path, dummy_legal_apis_path,
                 dummy_weather_apis_path, dummy_news_apis_path]:
        if not path.exists():
            with open(path, "w") as f:
                f.write("apis: []\nsearch_apis: []\n")


    # Mock st.session_state for testing Streamlit integration
    if not hasattr(st, 'session_state'):
        st.session_state = MagicMock()
        st.session_state.user_token = None
        print("Mocked st.session_state for standalone testing.")

    # Redirect logging to stdout for tests
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Reload ConfigManager to pick up mock secrets and dummy config files
    try:
        from config.config_manager import ConfigManager
        ConfigManager._instance = None # Reset the singleton instance
        ConfigManager._is_loaded = False
        config_manager_instance = ConfigManager() # Re-initialize
        print("ConfigManager re-initialized for testing.")
    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Some tests might fail.")
        config_manager_instance = None # Set to None to skip tests

    print("\n--- Testing user_manager.py with Firestore (mocked) ---\n")

    # Override the global firestore_db instance with our mock for testing
    class MockFirestoreManager:
        def __init__(self):
            self._users = {}
            self._reset_tokens = {}
            self._otps = {}
            self.db_mock = MagicMock() # Mock the firestore client itself

        def get_db(self):
            return self.db_mock

        def add_user(self, user_data: Dict[str, Any]) -> Tuple[bool, str]:
            # Use email as key for simplicity in mock
            if user_data['email'] in self._users:
                return False, "User already exists."
            self._users[user_data['email']] = user_data
            return True, "User added."

        def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
            # In mock, user_id is the actual user_id from Firestore, which is the doc ID.
            # In our mock, we're using email as the primary key for _users.
            # So, find by user_id will need to iterate or be mocked better if user_id is truly random UUID.
            for user_email, user_data in self._users.items():
                if user_data.get('user_id') == user_id:
                    return user_data
            return None

        def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
            return self._users.get(email)

        def update_user(self, user_id: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
            # Find user by user_id (UUID)
            user_found = False
            for email, user_data in self._users.items():
                if user_data.get('user_id') == user_id:
                    self._users[email].update(updates)
                    user_found = True
                    break
            if user_found:
                return True, "User updated."
            return False, "User not found."

        def add_reset_token(self, token_id: str, token_data: Dict[str, Any]) -> Tuple[bool, str]:
            self._reset_tokens[token_id] = token_data
            return True, "Token added."

        def get_reset_token(self, token_id: str) -> Optional[Dict[str, Any]]:
            return self._reset_tokens.get(token_id)

        def update_reset_token(self, token_id: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
            if token_id not in self._reset_tokens:
                return False, "Token not found."
            self._reset_tokens[token_id].update(updates)
            return True, "Token updated."

        def delete_reset_token(self, token_id: str) -> Tuple[bool, str]:
            if token_id in self._reset_tokens:
                del self._reset_tokens[token_id]
                return True, "Token deleted."
            return False, "Token not found."

        def clean_expired_reset_tokens(self) -> int:
            initial_count = len(self._reset_tokens)
            expired_ids = [
                token_id for token_id, data in self._reset_tokens.items()
                if data.get('expires_at') and data['expires_at'] < datetime.now(timezone.utc)
            ]
            for token_id in expired_ids:
                del self._reset_tokens[token_id]
            return initial_count - len(self._reset_tokens)

        def add_otp(self, identifier: str, otp_data: Dict[str, Any]) -> Tuple[bool, str]:
            self._otps[identifier] = otp_data
            return True, "OTP added."

        def get_otp(self, identifier: str) -> Optional[Dict[str, Any]]:
            return self._otps.get(identifier)

        def update_otp(self, identifier: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
            if identifier not in self._otps:
                return False, "OTP not found."
            self._otps[identifier].update(updates)
            return True, "OTP updated."

        def delete_otp(self, identifier: str) -> Tuple[bool, str]:
            if identifier in self._otps:
                del self._otps[identifier]
                return True, "OTP deleted."
            return False, "OTP not found."

        def clean_expired_otps(self) -> int:
            initial_count = len(self._otps)
            expired_ids = [
                id for id, data in self._otps.items()
                if data.get('expires_at') and data['expires_at'] < datetime.now(timezone.utc)
            ]
            for id in expired_ids:
                del self._otps[id]
            return initial_count - len(self._otps)

        def get_all_users(self) -> List[Dict[str, Any]]:
            return list(self._users.values())

    firestore_db = MockFirestoreManager()

    # Test get_user_tier_capability
    print("\n--- Testing get_user_tier_capability ---")

    # Create mock users with different tiers
    free_user_token = create_user("freeuser", "free@example.com", "Password123!", "free")
    pro_user_token = create_user("prouser", "pro@example.com", "Password123!", "pro")
    elite_user_token = create_user("eliteuser", "elite@example.com", "Password123!", "elite")
    admin_user_token = create_user("adminuser", "admin@example.com", "Password123!", "admin")

    # Test capabilities for 'free' user
    print(f"\nFree User Capabilities (token: {free_user_token}):")
    print(f"  Web Search Limit Chars: {get_user_tier_capability(free_user_token, 'web_search_limit_chars', 0)}")
    print(f"  Uploaded Docs Query Enabled: {get_user_tier_capability(free_user_token, 'uploaded_docs_query_enabled', False)}")
    print(f"  Charts Enabled: {get_user_tier_capability(free_user_token, 'charts_enabled', False)}")
    print(f"  Sentiment Analysis Enabled: {get_user_tier_capability(free_user_token, 'sentiment_analysis_enabled', False)}")

    # Test capabilities for 'pro' user
    print(f"\nPro User Capabilities (token: {pro_user_token}):")
    print(f"  Web Search Limit Chars: {get_user_tier_capability(pro_user_token, 'web_search_limit_chars', 0)}")
    print(f"  Uploaded Docs Query Enabled: {get_user_tier_capability(pro_user_token, 'uploaded_docs_query_enabled', False)}")
    print(f"  Charts Enabled: {get_user_tier_capability(pro_user_token, 'charts_enabled', False)}")
    print(f"  Sentiment Analysis Enabled: {get_user_tier_capability(pro_user_token, 'sentiment_analysis_enabled', False)}")

    # Test capabilities for 'elite' user
    print(f"\nElite User Capabilities (token: {elite_user_token}):")
    print(f"  Web Search Limit Chars: {get_user_tier_capability(elite_user_token, 'web_search_limit_chars', 0)}")
    print(f"  Uploaded Docs Query Enabled: {get_user_tier_capability(elite_user_token, 'uploaded_docs_query_enabled', False)}")
    print(f"  Charts Enabled: {get_user_tier_capability(elite_user_token, 'charts_enabled', False)}")
    print(f"  Sentiment Analysis Enabled: {get_user_tier_capability(elite_user_token, 'sentiment_analysis_enabled', False)}")

    # Test capabilities for 'admin' user
    print(f"\nAdmin User Capabilities (token: {admin_user_token}):")
    print(f"  Web Search Limit Chars: {get_user_tier_capability(admin_user_token, 'web_search_limit_chars', 0)}")
    print(f"  Uploaded Docs Query Enabled: {get_user_tier_capability(admin_user_token, 'uploaded_docs_query_enabled', False)}")
    print(f"  Charts Enabled: {get_user_tier_capability(admin_user_token, 'charts_enabled', False)}")
    print(f"  Sentiment Analysis Enabled: {get_user_tier_capability(admin_user_token, 'sentiment_analysis_enabled', False)}")


    # Clean up dummy config files
    if dummy_config_path.exists(): os.remove(dummy_config_path)
    if dummy_smtp_config_path.exists(): os.remove(dummy_smtp_config_path)
    if dummy_media_apis_path.exists(): os.remove(dummy_media_apis_path)
    if dummy_sports_apis_path.exists(): os.remove(dummy_sports_apis_path)
    if dummy_finance_apis_path.exists(): os.remove(dummy_finance_apis_path)
    if dummy_entertainment_apis_path.exists(): os.remove(dummy_entertainment_apis_path)
    if dummy_medical_apis_path.exists(): os.remove(dummy_medical_apis_path)
    if dummy_legal_apis_path.exists(): os.remove(dummy_legal_apis_path)
    if dummy_weather_apis_path.exists(): os.remove(dummy_weather_apis_path)
    if dummy_news_apis_path.exists(): os.remove(dummy_news_apis_path)
    if dummy_data_dir.exists() and not os.listdir(dummy_data_dir):
        os.rmdir(dummy_data_dir) # Remove data directory if empty
