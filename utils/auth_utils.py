# utils/auth_utils.py

import random
import string
from datetime import datetime, timedelta

# === In-memory OTP store (clear on restart) ===
otp_store = {}


def generate_otp(length=6) -> str:
    """Generate a numeric OTP."""
    return ''.join(random.choices(string.digits, k=length))


def store_otp(identifier: str, otp: str, ttl: int = 300):
    """
    Store OTP with a TTL (time to live).
    identifier = email or phone
    """
    otp_store[identifier] = {
        "otp": otp,
        "expires_at": datetime.utcnow() + timedelta(seconds=ttl)
    }


def verify_otp(identifier: str, otp: str) -> bool:
    """
    Validate OTP.
    """
    entry = otp_store.get(identifier)
    if not entry:
        return False

    if datetime.utcnow() > entry["expires_at"]:
        del otp_store[identifier]
        return False

    if entry["otp"] == otp:
        del otp_store[identifier]  # use-once
        return True

    return False


# Optional: cleanup expired (call periodically if needed)
def cleanup_otp_store():
    now = datetime.utcnow()
    expired = [k for k, v in otp_store.items() if v["expires_at"] < now]
    for k in expired:
        del otp_store[k]
