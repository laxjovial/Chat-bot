# utils/email_utils.py
import smtplib
import logging
import os
from email.message import EmailMessage
from typing import Optional, Dict, Any
import streamlit as st
from datetime import datetime

# Import the centralized ConfigManager
from config.config_manager import config_manager

# Configure logging
logger = logging.getLogger(__name__)

# === Configuration ===
class EmailConfig:
    """
    Email configuration class.
    Now primarily loads settings via ConfigManager, falling back to env vars.
    """
    
    @staticmethod
    def get_smtp_config() -> Dict[str, Any]:
        """
        Get SMTP configuration from ConfigManager (which pulls from config.yml or secrets).
        Falls back to environment variables for Render deployment if not in config.
        """
        smtp_config = {}
        
        # Try to load from centralized config_manager first
        smtp_config['smtp_server'] = config_manager.get('email.smtp_server', os.getenv('SMTP_SERVER', 'smtp.gmail.com'))
        smtp_config['smtp_port'] = int(config_manager.get('email.smtp_port', os.getenv('SMTP_PORT', 587)))
        smtp_config['smtp_user'] = config_manager.get_secret('email_smtp_user', os.getenv('SMTP_USER'))
        smtp_config['smtp_password'] = config_manager.get_secret('email_smtp_password', os.getenv('SMTP_PASSWORD'))
        smtp_config['from_email'] = config_manager.get('email.from_email', os.getenv('FROM_EMAIL'))
        smtp_config['from_name'] = config_manager.get('email.from_name', os.getenv('FROM_NAME', 'Your Unified AI Agent'))

        # Check if essential configs are available
        if not all([smtp_config['smtp_server'], smtp_config['smtp_user'], smtp_config['smtp_password'], smtp_config['from_email']]):
            logger.warning("SMTP configuration incomplete via config_manager or environment variables.")
            return {}
            
        return smtp_config

    @staticmethod
    def is_configured() -> bool:
        """Check if essential SMTP configuration details are available."""
        config = EmailConfig.get_smtp_config()
        return all([
            config.get('smtp_server'), 
            config.get('smtp_user'), 
            config.get('smtp_password'), 
            config.get('from_email')
        ])

# === Email Sending Class ===
class EmailSender:
    def __init__(self):
        self.smtp_config = EmailConfig.get_smtp_config()
        if not self.smtp_config:
            logger.error("EmailSender initialized without full SMTP configuration.")
        
    def _send(self, msg: EmailMessage) -> Tuple[bool, str]:
        """Helper to send the email message."""
        if not self.smtp_config:
            return False, "SMTP configuration missing or incomplete."

        try:
            with smtplib.SMTP(self.smtp_config['smtp_server'], self.smtp_config['smtp_port']) as server:
                server.starttls()  # Secure the connection
                server.login(self.smtp_config['smtp_user'], self.smtp_config['smtp_password'])
                server.send_message(msg)
            logger.info(f"Email sent successfully to {msg['To']}")
            return True, "Email sent successfully."
        except smtplib.SMTPAuthenticationError:
            logger.error(f"SMTP Authentication Error: Check username and password for {self.smtp_config.get('smtp_user')}")
            return False, "Authentication failed. Check your email credentials."
        except smtplib.SMTPException as e:
            logger.error(f"SMTP Error: {e}")
            return False, f"SMTP error occurred: {e}"
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False, f"An unexpected error occurred: {e}"

    def send_email(self, to_email: str, subject: str, body: str = "", html_body: Optional[str] = None) -> Tuple[bool, str]:
        """
        Send a generic email.
        """
        msg = EmailMessage()
        msg['From'] = f"{self.smtp_config.get('from_name', 'Your App')} <{self.smtp_config.get('from_email')}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if html_body:
            msg.set_content(body) # Plain text fallback
            msg.add_alternative(html_body, subtype='html')
        else:
            msg.set_content(body)
            
        return self._send(msg)

    def send_otp_email(self, email: str, otp: str) -> Tuple[bool, str]:
        """
        Send an OTP (One-Time Password) email.
        """
        subject = "Your One-Time Password (OTP)"
        body = f"Your OTP is: {otp}\n\nThis OTP is valid for a limited time. Do not share it with anyone."
        html_body = f"""
        <html>
            <body>
                <p>Hello,</p>
                <p>Your One-Time Password (OTP) for verification is: <strong>{otp}</strong></p>
                <p>This OTP is valid for a limited time. Please do not share this code with anyone.</p>
                <p>If you did not request this, please ignore this email.</p>
                <p>Best regards,<br>{self.smtp_config.get('from_name', 'Your Unified AI Agent')}</p>
            </body>
        </html>
        """
        return self.send_email(email, subject, body, html_body)

    def send_password_reset_email(self, email: str, reset_link: str) -> Tuple[bool, str]:
        """
        Send a password reset email with a link.
        """
        subject = "Password Reset Request"
        body = f"You have requested a password reset. Please click on the following link to reset your password: {reset_link}\n\nThis link is valid for a limited time."
        html_body = f"""
        <html>
            <body>
                <p>Hello,</p>
                <p>You have requested a password reset for your account.</p>
                <p>Please click on the link below to reset your password:</p>
                <p><a href="{reset_link}">Reset Your Password</a></p>
                <p>This link is valid for a limited time. If you did not request this, please ignore this email.</p>
                <p>Best regards,<br>{self.smtp_config.get('from_name', 'Your Unified AI Agent')}</p>
            </body>
        </html>
        """
        return self.send_email(email, subject, body, html_body)

# === Helper Functions (for backward compatibility or simpler access) ===
def send_otp_email(email: str, otp: str) -> Tuple[bool, str]:
    """Convenience function - redirects to EmailSender.send_otp_email"""
    sender = EmailSender()
    return sender.send_otp_email(email, otp)

def send_email_legacy(to_email: str = None, subject: str = "Notification", 
                     body: str = "", html_body: Optional[str] = None, 
                     email: str = None) -> bool:
    """Legacy send_email function for backward compatibility"""
    sender = EmailSender()
    recipient_email = to_email or email
    
    if not recipient_email:
        return False, "Recipient email is missing." # Changed return type to match _send
    
    success, _ = sender.send_email(recipient_email, subject, body, html_body)
    return success

def validate_email_format(email: str) -> bool:
    """Basic email format validation - kept for local use but prefer utils/validation_utils.py"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_email_sender() -> EmailSender:
    """Get configured email sender instance"""
    return EmailSender()

# === For Testing ===
if __name__ == "__main__":
    import os
    import sys
    
    # Mock Streamlit secrets and config_manager for CLI testing
    class MockSecrets:
        def __init__(self):
            # Replace with your actual test credentials if you want to send a real email
            self.email = {
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": os.environ.get("TEST_SMTP_USER", "your_test_email@gmail.com"), 
                "smtp_password": os.environ.get("TEST_SMTP_PASSWORD", "your_app_password"), # Use an app password for Gmail
                "from_email": os.environ.get("TEST_FROM_EMAIL", "your_test_email@gmail.com"),
                "from_name": "Test Unified AI Agent"
            }
        # Add a way for config_manager to access secrets via `get_secret`
        def get(self, key):
            parts = key.split('.')
            val = self
            for part in parts:
                if hasattr(val, part):
                    val = getattr(val, part)
                elif isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    return None # Key not found
            return val

    class MockConfigManager:
        def __init__(self, secrets_mock):
            self._secrets = secrets_mock
            self._config_data = {
                'email': {
                    'smtp_server': 'smtp.gmail.com',
                    'smtp_port': 587,
                    'from_email': 'your_test_email@gmail.com', # Should match test_smtp_user
                    'from_name': 'CLI Test Agent'
                }
            }
        def get(self, key, default=None):
            parts = key.split('.')
            val = self._config_data
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    return default
            return val
        
        def get_secret(self, key, default=None):
            # Simulate fetching from st.secrets directly for email credentials
            return self._secrets.get(f"email.{key}") or default

    if not hasattr(st, 'secrets'):
        st.secrets = MockSecrets()
        print("Mocked st.secrets for standalone testing.")
    
    # Ensure config_manager is a fresh instance for this test run
    # Override the global config_manager with a mock for testing
    config_manager = MockConfigManager(st.secrets)
    print("Mocked config_manager for CLI testing.")

    print("Testing email_utils.py:")
    
    test_recipient_email = "recipient@example.com" # CHANGE THIS to a real email for actual testing
    if config_manager.get_secret('email_smtp_user') == "your_test_email@gmail.com":
        print("\n!!! WARNING: Using default test email credentials. Email sending will likely FAIL. !!!")
        print("!!! Please set TEST_SMTP_USER, TEST_SMTP_PASSWORD, TEST_FROM_EMAIL environment variables or update MockSecrets !!!")
        print(f"!!! Attempting to send to: {test_recipient_email} !!!")
        proceed = input("Do you want to attempt sending a test email with current settings? (yes/no): ").lower()
        if proceed != 'yes':
            sys.exit("Test aborted.")
        
    print(f"\nSMTP Config: {EmailConfig.get_smtp_config()}")
    print(f"Is configured: {EmailConfig.is_configured()}")

    if EmailConfig.is_configured():
        # Test generic email
        success, msg = EmailSender().send_email(
            test_recipient_email,
            "Test Subject from Unified AI Agent CLI",
            "This is a plain text test email from the Unified AI Agent utility script.",
            "<h1>Hello from Unified AI Agent!</h1><p>This is an HTML test email from the <strong>Unified AI Agent</strong> utility script.</p>"
        )
        print(f"Generic email test result: Success={success}, Message={msg}")

        # Test OTP email
        test_otp = "123456"
        success_otp, msg_otp = send_otp_email(test_recipient_email, test_otp)
        print(f"OTP email test result: Success={success_otp}, Message={msg_otp}")

        # Test password reset email
        test_reset_link = "http://localhost:8501/reset_password?token=some_reset_token"
        success_reset, msg_reset = EmailSender().send_password_reset_email(test_recipient_email, test_reset_link)
        print(f"Password reset email test result: Success={success_reset}, Message={msg_reset}")
    else:
        print("Skipping email sending tests as configuration is incomplete.")
