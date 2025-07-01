# utils/otp_utils.py

import random
import time

# In-memory OTP store (replace with Redis or DB in production)
otp_store = {}


def generate_otp(email: str) -> str:
    """
    Generate a 6-digit OTP and store with timestamp.
    """
    otp = str(random.randint(100000, 999999))
    otp_store[email] = {"otp": otp, "timestamp": time.time()}
    return otp


def validate_otp(email: str, entered_otp: str, expiry_seconds: int = 300) -> bool:
    """
    Check if entered OTP is valid and not expired.
    """
    record = otp_store.get(email)
    if not record:
        return False

    if time.time() - record["timestamp"] > expiry_seconds:
        del otp_store[email]
        return False

    if record["otp"] == entered_otp:
        del otp_store[email]
        return True

    return False
