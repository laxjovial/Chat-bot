# utils/auth_utils.py
import random
import string
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# === In-memory OTP store (clear on restart) ===
otp_store: Dict[str, Dict[str, any]] = {}
otp_lock = threading.Lock()  # Thread safety for concurrent access

def generate_otp(length: int = 6) -> str:
    """
    Generate a numeric OTP.
    
    Args:
        length (int): Length of the OTP (default: 6)
    
    Returns:
        str: Generated OTP
    """
    if length < 4 or length > 10:
        raise ValueError("OTP length must be between 4 and 10 digits")
    
    return ''.join(random.choices(string.digits, k=length))

def store_otp(identifier: str, otp: str, ttl: int = 300) -> bool:
    """
    Store OTP with a TTL (time to live).
    
    Args:
        identifier (str): Email or phone number
        otp (str): The OTP to store
        ttl (int): Time to live in seconds (default: 300 = 5 minutes)
    
    Returns:
        bool: True if stored successfully
    """
    try:
        with otp_lock:
            otp_store[identifier] = {
                "otp": otp,
                "expires_at": datetime.utcnow() + timedelta(seconds=ttl),
                "attempts": 0,
                "created_at": datetime.utcnow()
            }
        logger.info(f"OTP stored for identifier: {identifier[:3]}***")
        return True
    except Exception as e:
        logger.error(f"Failed to store OTP: {e}")
        return False

def verify_otp(identifier: str, otp: str, max_attempts: int = 3) -> Tuple[bool, str]:
    """
    Validate OTP with attempt limiting.
    
    Args:
        identifier (str): Email or phone number
        otp (str): OTP to verify
        max_attempts (int): Maximum verification attempts (default: 3)
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        with otp_lock:
            entry = otp_store.get(identifier)
            
            if not entry:
                return False, "OTP not found or expired"
            
            # Check if expired
            if datetime.utcnow() > entry["expires_at"]:
                del otp_store[identifier]
                return False, "OTP has expired"
            
            # Increment attempts
            entry["attempts"] += 1
            
            # Check max attempts
            if entry["attempts"] > max_attempts:
                del otp_store[identifier]
                logger.warning(f"Max OTP attempts exceeded for: {identifier[:3]}***")
                return False, "Maximum verification attempts exceeded"
            
            # Verify OTP
            if entry["otp"] == otp:
                del otp_store[identifier]  # use-once
                logger.info(f"OTP verified successfully for: {identifier[:3]}***")
                return True, "OTP verified successfully"
            
            return False, f"Invalid OTP. {max_attempts - entry['attempts']} attempts remaining"
            
    except Exception as e:
        logger.error(f"Error verifying OTP: {e}")
        return False, "Verification failed due to system error"

def is_otp_valid(identifier: str) -> bool:
    """
    Check if a valid OTP exists for the identifier.
    
    Args:
        identifier (str): Email or phone number
    
    Returns:
        bool: True if valid OTP exists
    """
    with otp_lock:
        entry = otp_store.get(identifier)
        if not entry:
            return False
        
        if datetime.utcnow() > entry["expires_at"]:
            del otp_store[identifier]
            return False
        
        return True

def revoke_otp(identifier: str) -> bool:
    """
    Manually revoke an OTP.
    
    Args:
        identifier (str): Email or phone number
    
    Returns:
        bool: True if OTP was revoked
    """
    with otp_lock:
        if identifier in otp_store:
            del otp_store[identifier]
            logger.info(f"OTP revoked for: {identifier[:3]}***")
            return True
        return False

def cleanup_expired_otps() -> int:
    """
    Clean up expired OTPs from store.
    Call this periodically to prevent memory leaks.
    
    Returns:
        int: Number of expired OTPs cleaned up
    """
    now = datetime.utcnow()
    cleaned_count = 0
    
    with otp_lock:
        expired_keys = [
            key for key, value in otp_store.items() 
            if value["expires_at"] < now
        ]
        
        for key in expired_keys:
            del otp_store[key]
            cleaned_count += 1
    
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} expired OTPs")
    
    return cleaned_count

def get_otp_stats() -> Dict[str, int]:
    """
    Get statistics about the OTP store.
    
    Returns:
        Dict[str, int]: Statistics including total OTPs and expired count
    """
    now = datetime.utcnow()
    
    with otp_lock:
        total_otps = len(otp_store)
        expired_count = sum(
            1 for value in otp_store.values() 
            if value["expires_at"] < now
        )
        active_count = total_otps - expired_count
    
    return {
        "total_otps": total_otps,
        "active_otps": active_count,
        "expired_otps": expired_count
    }

# Rate limiting helper
def can_request_otp(identifier: str, cooldown_seconds: int = 60) -> Tuple[bool, int]:
    """
    Check if an OTP can be requested (rate limiting).
    
    Args:
        identifier (str): Email or phone number
        cooldown_seconds (int): Cooldown period between requests
    
    Returns:
        Tuple[bool, int]: (can_request, seconds_remaining)
    """
    with otp_lock:
        entry = otp_store.get(identifier)
        if not entry:
            return True, 0
        
        time_since_creation = datetime.utcnow() - entry["created_at"]
        if time_since_creation.total_seconds() < cooldown_seconds:
            remaining = cooldown_seconds - int(time_since_creation.total_seconds())
            return False, remaining
        
        return True, 0
