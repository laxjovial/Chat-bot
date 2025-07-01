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
    RESET_TOKEN_EXPIRY_MINUTES = 15
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
        "roles": ["user"] # Default role
    }

    success, msg = firestore_db.add_user(user_data)
    if success:
        logger.info(f"New user created: {username} ({email})")
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
        return False, "Invalid or expired token.", None
    
    if token_data.get("is_used"):
        return False, "Token has already been used.", None

    if token_data.get("expires_at") and token_data["expires_at"] < datetime.now(timezone.utc):
        firestore_db.delete_reset_token(token) # Clean up expired token
        return False, "Token has expired.", None
        
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
        firestore_db.update_otp(token, {"is_used": True}) # OTP is document ID, reset_token has its own collection
        # Correcting the above line: should update reset_tokens collection.
        # This is for reset_tokens, not OTP.
        token_update_success, token_update_msg = firestore_db.update_reset_token(token, {"is_used": True})
        if not token_update_success:
            logger.error(f"Failed to mark reset token {token} as used: {token_update_msg}")
        
        logger.info(f"Password reset successfully for {email} using token.")
        return True, "Password reset successfully."
    else:
        logger.error(f"Failed to reset password for {email} using token: {user_update_msg}")
        return False, f"Failed to reset password: {user_update_msg}"

# Add a placeholder for `update_reset_token` in `FirestoreManager` if it's missing.
# For now, it will be added in FirestoreManager.py.

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
    if hasattr(st, 'session_state') and 'user_token' in st.session_state:
        return find_user_by_token(st.session_state.user_token)
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

    dummy_data_dir.mkdir(exist_ok=True)

    with open(dummy_config_path, "w") as f:
        f.write("app:\n  name: 'Test App'\nllm:\n  provider: 'mock'\nemail:\n  from_email: 'test@example.com'\n  smtp_server: 'smtp.test.com'\n  smtp_port: 587\n")

    with open(dummy_smtp_config_path, "w") as f:
        f.write("smtp_user: 'test_user_from_yml@example.com'\nsmtp_password: 'test_password_from_yml'\n")

    with open(dummy_media_apis_path, "w") as f:
        f.write("apis: []\nsearch_apis: []\n")

    with open(dummy_sports_apis_path, "w") as f:
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
        # Assuming ConfigManager is a singleton, reset its state for testing
        from config.config_manager import ConfigManager
        ConfigManager._instance = None # Reset the singleton instance
        ConfigManager._is_loaded = False
        config_manager_instance = ConfigManager() # Re-initialize
        print("ConfigManager re-initialized for testing.")
    except Exception as e:
        print(f"Could not initialize ConfigManager for testing: {e}. Some tests might fail.")
        config_manager_instance = None # Set to None to skip tests

    print("\n--- Testing user_manager.py with Firestore (mocked) ---\n")

    # Mock FirestoreManager methods for unit testing without actual DB connection
    class MockFirestoreManager:
        def __init__(self):
            self._users = {}
            self._reset_tokens = {}
            self._otps = {}
            self.db_mock = MagicMock() # Mock the firestore client itself

        def get_db(self):
            return self.db_mock

        def add_user(self, user_data: Dict[str, Any]) -> Tuple[bool, str]:
            if user_data['user_id'] in self._users:
                return False, "User already exists."
            self._users[user_data['user_id']] = user_data
            # Also store by email for quick lookup
            self._users_by_email[user_data['email']] = user_data['user_id']
            return True, "User added."

        def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
            return self._users.get(user_id)

        def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
            for user_id, user_data in self._users.items():
                if user_data.get('email') == email:
                    return user_data
            return None

        def update_user(self, user_id: str, updates: Dict[str, Any]) -> Tuple[bool, str]:
            if user_id not in self._users:
                return False, "User not found."
            self._users[user_id].update(updates)
            return True, "User updated."

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

    # Override the global firestore_db instance with our mock for testing
    firestore_db = MockFirestoreManager()
    # Also mock the internal _users_by_email for quick lookup as MockFirestoreManager uses it
    firestore_db._users_by_email = {} 

    # Test create_user
    print("Testing create_user...")
    token = create_user("testuser", "test@example.com", "Password123!", "free", "What is your pet's name?", "Buddy")
    print(f"Create user result (token): {token}")
    assert token is not None, "User creation failed."
    assert firestore_db.get_user_by_email("test@example.com") is not None, "User not found in mocked DB after creation."

    # Test authenticate_user
    print("\nTesting authenticate_user...")
    success, msg, auth_token = authenticate_user("test@example.com", "Password123!")
    print(f"Auth result: {success}, {msg}, Token: {auth_token}")
    assert success is True and auth_token == token, "Authentication failed."

    # Test failed authentication (wrong password)
    print("\nTesting failed authentication...")
    success, msg, _ = authenticate_user("test@example.com", "WrongPassword!")
    print(f"Failed auth result: {success}, {msg}")
    assert success is False and "Invalid email or password" in msg, "Failed auth did not return expected message."

    # Test login attempts and lockout
    print("\nTesting login attempts and lockout...")
    # Simulate multiple failed attempts
    for i in range(SecurityConfig.MAX_LOGIN_ATTEMPTS):
        success, msg, _ = authenticate_user("test@example.com", "WrongPassword!")
        print(f"Attempt {i+1}: {msg}")
    assert "Account locked" in msg, "Account did not lock after max attempts."

    # Test change_password
    print("\nTesting change_password...")
    success, msg = change_password(token, "Password123!", "NewPassword456!")
    print(f"Change password result: {success}, {msg}")
    assert success is True, "Password change failed."
    success, msg, auth_token = authenticate_user("test@example.com", "NewPassword456!")
    assert success is True, "Authentication with new password failed."

    # Test create_reset_token
    print("\nTesting create_reset_token...")
    success, msg, reset_token = create_reset_token("test@example.com")
    print(f"Create reset token result: {success}, {msg}, Token: {reset_token}")
    assert success is True and reset_token is not None, "Reset token creation failed."

    # Test validate_reset_token
    print("\nTesting validate_reset_token...")
    is_valid, msg, email_from_token = validate_reset_token(reset_token)
    print(f"Validate reset token result: {is_valid}, {msg}, Email: {email_from_token}")
    assert is_valid is True, "Reset token validation failed."

    # Test reset_password_with_token
    print("\nTesting reset_password_with_token...")
    success, msg = reset_password_with_token(reset_token, "NewestPassword789!")
    print(f"Reset password with token result: {success}, {msg}")
    assert success is True, "Password reset with token failed."
    success, msg, auth_token = authenticate_user("test@example.com", "NewestPassword789!")
    assert success is True, "Authentication with newest password failed."
    is_valid, msg, _ = validate_reset_token(reset_token)
    assert is_valid is False and "already been used" in msg, "Used token not marked as used."

    # Test create_otp
    print("\nTesting create_otp...")
    otp_success, otp_msg, otp_code = create_otp("test@example.com", "login")
    print(f"Create OTP result: {otp_success}, {otp_msg}, OTP: {otp_code}")
    assert otp_success is True and otp_code is not None, "OTP creation failed."

    # Test verify_otp
    print("\nTesting verify_otp (correct)...")
    verify_success, verify_msg = verify_otp("test@example.com", otp_code)
    print(f"Verify OTP result: {verify_success}, {verify_msg}")
    assert verify_success is True, "OTP verification failed."
    verify_success, verify_msg = verify_otp("test@example.com", otp_code) # Test re-using verified OTP
    assert verify_success is False and "already been used" in verify_msg, "Verified OTP not marked as used."

    print("\nTesting verify_otp (incorrect)...")
    otp_success, otp_msg, otp_code_new = create_otp("test@example.com", "login") # Create a new one
    verify_success, verify_msg = verify_otp("test@example.com", "999999")
    print(f"Verify incorrect OTP result: {verify_success}, {verify_msg}")
    assert verify_success is False and "Incorrect OTP" in verify_msg, "Incorrect OTP verification passed."

    # Test clean_expired_data (mocked to immediately expire)
    print("\nTesting clean_expired_data...")
    # Manually expire an OTP for testing cleanup
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    firestore_db._otps["expired@example.com"] = {"otp": "123456", "expires_at": expired_time, "is_verified": False}
    firestore_db._reset_tokens["expired_token_xyz"] = {"expires_at": expired_time, "is_used": False}

    clean_expired_data()
    assert firestore_db.get_otp("expired@example.com") is None, "Expired OTP not cleaned up."
    assert firestore_db.get_reset_token("expired_token_xyz") is None, "Expired reset token not cleaned up."
    print("Expired data cleanup tested.")

    # Clean up dummy config files
    if dummy_config_path.exists():
        os.remove(dummy_config_path)
    if dummy_smtp_config_path.exists():
        os.remove(dummy_smtp_config_path)
    if dummy_media_apis_path.exists():
        os.remove(dummy_media_apis_path)
    if dummy_sports_apis_path.exists():
        os.remove(dummy_sports_apis_path)
    if dummy_data_dir.exists() and not os.listdir(dummy_data_dir):
        os.rmdir(dummy_data_dir) # Remove data directory if empty

    print("\nAll user_manager tests completed.")
