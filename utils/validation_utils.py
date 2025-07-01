# utils/validation_utils.py
import re
from typing import Tuple

def validate_email_format(email: str) -> bool:
    """
    Comprehensive email format validation.
    
    Args:
        email (str): Email address to validate
    
    Returns:
        bool: True if email format is valid
    """
    if not email or not isinstance(email, str):
        return False
    
    # Basic regex pattern for email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    # Check length limits
    if len(email) > 254:  # RFC 5321 limit
        return False
    
    # Check local part length (before @)
    local_part = email.split('@')[0] if '@' in email else email
    if len(local_part) > 64:  # RFC 5321 limit
        return False
    
    return re.match(pattern, email) is not None

def validate_password_strength(password: str, min_length: int = 8) -> Tuple[bool, str]:
    """
    Validate password strength with customizable rules.
    
    Args:
        password (str): Password to validate
        min_length (int): Minimum password length
    
    Returns:
        Tuple[bool, str]: (is_valid, message)
    """
    if not password:
        return False, "Password is required"
    
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    # Optional: Check for special characters
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password should contain at least one special character"
    
    return True, "Password is strong"
