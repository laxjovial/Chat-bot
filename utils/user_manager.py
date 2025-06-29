# utils/user_manager.py

import uuid
import json
import os
from datetime import datetime
from pathlib import Path

# === Config Paths ===
USER_DATA_FILE = Path("data/users.json")
USER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

# === Core Functions ===

def generate_token(prefix="usr"):
    """Generates a unique internal user token."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def load_user_data():
    if USER_DATA_FILE.exists():
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def create_user(username: str, email: str, tier="free", password="", security_q="", security_a="") -> str:
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
        "password": password,  # NOTE: can hash later for security
        "created_at": datetime.utcnow().isoformat(),
        "security_q": security_q,
        "security_a": security_a
    }
    save_user_data(users)
    return token

def get_user_token(username_or_email: str) -> str:
    """
    Returns the user token based on email or username.
    """
    users = load_user_data()
    for token, u in users.items():
        if u.get("username") == username_or_email or u.get("email") == username_or_email:
            return token
    return None

def lookup_user_by_token(token: str) -> dict:
    return load_user_data().get(token, {})

def find_user_by_email(email: str) -> dict:
    users = load_user_data()
    for token, u in users.items():
        if u.get("email") == email:
            return {"token": token, **u}
    return {}

def verify_password(email: str, input_password: str) -> bool:
    """
    Compares input password with stored password for the given email.
    """
    user = find_user_by_email(email)
    return user and user.get("password") == input_password

def verify_recovery(email: str, question: str, answer: str) -> bool:
    u = find_user_by_email(email)
    return u and u.get("security_q") == question and u.get("security_a") == answer

def send_token_to_email(email: str, token: str = None):
    """
    (Mock) Sends token or OTP to email. Replace with SMTP for production.
    """
    if not token:
        user = find_user_by_email(email)
        if user:
            token = user["token"]
    if token:
        print(f"📬 Sending token or OTP '{token}' to {email}")
        return True
    return False

# === CLI Example ===
if __name__ == "__main__":
    t = create_user(
        "Victor", "victor@gmail.com", tier="pro", password="arsenal123",
        security_q="Best team?", security_a="Arsenal"
    )
    print(f"Created user token: {t}")
    print("Resolved:", lookup_user_by_token(t))

