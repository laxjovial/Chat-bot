# utils/email_utils.py# utils/email_utils.py

import smtplib
from email.message import EmailMessage
import yaml
import os
from typing import Optional

# === Config ===
CONFIG_FILE = "data/smtp_config.yml"
DEFAULT_SENDER = "no-reply@example.com"
DEFAULT_SUBJECT = "Notification"

# === Email Templates ===
PASSWORD_RESET_TEMPLATE = """
Hello,

You have requested to reset your password. Please click the link below to reset your password:

{reset_link}

This link will expire in 1 hour.

If you did not request this password reset, please ignore this email.

Best regards,
Your Application Team
"""

PASSWORD_RESET_SUCCESS_TEMPLATE = """
Hello,

Your password has been successfully reset.

If you did not make this change, please contact support immediately.

Best regards,
Your Application Team
"""

WELCOME_TEMPLATE = """
Hello {username},

Welcome to our application! Your account has been successfully created.

Email: {email}
Account Tier: {tier}

Thank you for joining us!

Best regards,
Your Application Team
"""

# === Load SMTP config ===
def load_smtp_config() -> dict:
    """Load SMTP configuration from YAML file"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f)
    return {}

def create_default_smtp_config() -> None:
    """Create a default SMTP configuration file"""
    default_config = {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'smtp_user': 'your-email@gmail.com',
        'smtp_password': 'your-app-password',
        'from_email': 'no-reply@yourapp.com'
    }
    
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False)
    
    print(f"Default SMTP config created at {CONFIG_FILE}")
    print("Please update with your actual SMTP credentials.")

# === Core Email Function ===
def send_email(to_email: str, subject: str = DEFAULT_SUBJECT, body: str = "", 
               html_body: Optional[str] = None) -> bool:
    """
    Send email using SMTP configuration
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: HTML body (optional)
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    config = load_smtp_config()
    
    # If no config, simulate sending (for development)
    if not config:
        print(f"[Mock Email] To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body:\n{body}")
        print("-" * 50)
        return True  # Return True for mock mode
    
    try:
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port", 587)
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        sender = config.get("from_email", DEFAULT_SENDER)
        
        # Validate required config
        if not all([smtp_server, smtp_user, smtp_password]):
            print("[Email Error] Missing required SMTP configuration")
            return False
        
        # Create message
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        
        # Set content
        msg.set_content(body)
        if html_body:
            msg.add_alternative(html_body, subtype='html')
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        print(f"[Email Sent] Successfully sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"[Email Failed] {e}")
        return False

# === Specialized Email Functions ===
def send_password_reset_email(to_email: str, reset_token: str, 
                            base_url: str = "http://localhost:8501") -> bool:
    """Send password reset email with reset link"""
    reset_link = f"{base_url}/forgot_password?token={reset_token}"
    
    subject = "Password Reset Request"
    body = PASSWORD_RESET_TEMPLATE.format(reset_link=reset_link)
    
    return send_email(to_email, subject, body)

def send_password_reset_success_email(to_email: str) -> bool:
    """Send confirmation email after successful password reset"""
    subject = "Password Reset Successful"
    body = PASSWORD_RESET_SUCCESS_TEMPLATE
    
    return send_email(to_email, subject, body)

def send_welcome_email(to_email: str, username: str, tier: str = "free") -> bool:
    """Send welcome email to new users"""
    subject = "Welcome to Our Application!"
    body = WELCOME_TEMPLATE.format(
        username=username,
        email=to_email,
        tier=tier.title()
    )
    
    return send_email(to_email, subject, body)

def send_security_alert(to_email: str, action: str) -> bool:
    """Send security alert email"""
    subject = "Security Alert - Account Activity"
    body = f"""
Hello,

We detected the following activity on your account:
{action}

If this was not you, please contact support immediately.

Best regards,
Your Application Team
"""
    
    return send_email(to_email, subject, body)

# === CLI Test ===
if __name__ == "__main__":
    # Check if config exists
    if not os.path.exists(CONFIG_FILE):
        create_default_smtp_config()
    
    # Test emails
    test_email = "test@example.com"
    
    print("Testing email functions...")
    
    # Test basic email
    send_email(test_email, "Test Email", "This is a test message.")
    
    # Test password reset email
    send_password_reset_email(test_email, "sample_reset_token")
    
    # Test welcome email
    send_welcome_email(test_email, "TestUser", "pro")
    
    print("Email tests completed!")
