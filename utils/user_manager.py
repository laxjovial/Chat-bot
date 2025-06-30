# utils/user_manager.py

import uuid
import json
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

# === Config Paths ===
USER_DATA_FILE = Path("data/users.json")
RESET_TOKENS_FILE = Path("data/reset_tokens.json")
USER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

# === Utility: Password Hashing ===
def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(email: str, password: str) -> bool:
    """Verify user password against stored hash"""
    users = load_user_data()
    for user in users.values():
        if user.get("email") == email:
            stored_hash = user.get("password_hash", "")
            return hash_password(password) == stored_hash
    return False

# === Token Generation ===
def generate_token(prefix="usr"):
    """Generates a unique internal user token."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def generate_reset_token():
    """Generate a secure reset token"""
    return uuid.uuid4().hex

# === Data Management ===
def load_user_data() -> Dict[str, Any]:
    """Load user data from JSON file"""
    if USER_DATA_FILE.exists():
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_user_data(data: Dict[str, Any]) -> None:
    """Save user data to JSON file"""
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_reset_tokens() -> Dict[str, Any]:
    """Load password reset tokens"""
    if RESET_TOKENS_FILE.exists():
        with open(RESET_TOKENS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_reset_tokens(data: Dict[str, Any]) -> None:
    """Save password reset tokens"""
    with open(RESET_TOKENS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def cleanup_expired_tokens() -> None:
    """Remove expired reset tokens"""
    tokens = load_reset_tokens()
    current_time = datetime.utcnow()
    
    expired_tokens = []
    for token, data in tokens.items():
        expiry = datetime.fromisoformat(data['expires_at'])
        if current_time > expiry:
            expired_tokens.append(token)
    
    for token in expired_tokens:
        del tokens[token]
    
    if expired_tokens:
        save_reset_tokens(tokens)

# === User Management ===
def create_user(username: str, email: str, password: str = "", tier="free", 
                security_q="", security_a="") -> str:
    """
    Creates a new user with a unique token.
    Returns the user token.
    """
    users = load_user_data()

    # Check if email already registered
    for token, u in users.items():
        if u.get("email") == email:
            return token  # already exists

    token = generate_token()
    users[token] = {
        "username": username,
        "email": email,
        "tier": tier,
        "created_at": datetime.utcnow().isoformat(),
        "security_q": security_q,
        "security_a": security_a,
        "password_hash": hash_password(password) if password else ""
    }
    save_user_data(users)
    return token

def get_user_token(username_or_email: str) -> Optional[str]:
    """Returns the user token based on email or username."""
    users = load_user_data()
    for token, u in users.items():
        if u.get("username") == username_or_email or u.get("email") == username_or_email:
            return token
    return None

def lookup_user_by_token(token: str) -> Dict[str, Any]:
    """Get user data by token"""
    return load_user_data().get(token, {})

def find_user_by_email(email: str) -> Dict[str, Any]:
    """Find user by email address"""
    users = load_user_data()
    for token, u in users.items():
        if u.get("email") == email:
            return {"token": token, **u}
    return {}

# === Password Recovery ===
def verify_recovery(email: str, question: str, answer: str) -> bool:
    """Verify security question answer for password recovery"""
    u = find_user_by_email(email)
    return u and u.get("security_q") == question and u.get("security_a") == answer

def create_reset_token(email: str) -> Optional[str]:
    """Create a password reset token for email"""
    user = find_user_by_email(email)
    if not user:
        return None
    
    # Clean up expired tokens first
    cleanup_expired_tokens()
    
    reset_token = generate_reset_token()
    expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
    
    tokens = load_reset_tokens()
    tokens[reset_token] = {
        "email": email,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at.isoformat(),
        "used": False
    }
    save_reset_tokens(tokens)
    
    return reset_token

def verify_reset_token(token: str) -> Optional[str]:
    """Verify reset token and return associated email"""
    cleanup_expired_tokens()
    tokens = load_reset_tokens()
    
    token_data = tokens.get(token)
    if not token_data or token_data.get('used'):
        return None
    
    return token_data.get('email')

def use_reset_token(token: str) -> bool:
    """Mark reset token as used"""
    tokens = load_reset_tokens()
    if token in tokens:
        tokens[token]['used'] = True
        save_reset_tokens(tokens)
        return True
    return False

def reset_password(email: str, new_password: str) -> bool:
    """Reset user password"""
    users = load_user_data()
    for token, u in users.items():
        if u.get("email") == email:
            u["password_hash"] = hash_password(new_password)
            u["password_updated_at"] = datetime.utcnow().isoformat()
            save_user_data(users)
            return True
    return False

def reset_user_token(email: str) -> str:
    """Generate new user token (for security purposes)"""
    users = load_user_data()
    for token, u in list(users.items()):
        if u.get("email") == email:
            new_token = generate_token()
            users[new_token] = u
            del users[token]
            save_user_data(users)
            return new_token
    return ""

# === CLI Example ===
if __name__ == "__main__":
    # Test user creation
    t = create_user("Victor", "victor@gmail.com", password="pass123", 
                   tier="pro", security_q="Best team?", security_a="Arsenal")
    print(f"Created user token: {t}")
    print("User data:", lookup_user_by_token(t))
    
    # Test reset token creation
    reset_token = create_reset_token("victor@gmail.com")
    print(f"Reset token: {reset_token}")
    
    # Test token verification
    email = verify_reset_token(reset_token)
    print(f"Token verified for email: {email}")


