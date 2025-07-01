# utils/email_utils.py
import smtplib
import logging
import os
from email.message import EmailMessage
from typing import Optional, Dict, Any
import streamlit as st
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# === Configuration ===
class EmailConfig:
    """Email configuration class for Streamlit apps"""
    
    @staticmethod
    def get_smtp_config() -> Dict[str, Any]:
        """
        Get SMTP configuration from Streamlit secrets or environment variables.
        For Render deployment, use environment variables.
        """
        try:
            # Try Streamlit secrets first (for local development)
            if hasattr(st, 'secrets') and 'email' in st.secrets:
                return {
                    'smtp_server': st.secrets.email.smtp_server,
                    'smtp_port': int(st.secrets.email.smtp_port),
                    'smtp_user': st.secrets.email.smtp_user,
                    'smtp_password': st.secrets.email.smtp_password,
                    'from_email': st.secrets.email.from_email,
                    'from_name': st.secrets.email.get('from_name', 'Your App')
                }
        except Exception as e:
            logger.warning(f"Could not load from Streamlit secrets: {e}")
        
        # Fallback to environment variables (for Render deployment)
        return {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', 587)),
            'smtp_user': os.getenv('SMTP_USER', ''),
            'smtp_password': os.getenv('SMTP_PASSWORD', ''),
            'from_email': os.getenv('FROM_EMAIL', 'no-reply@yourapp.com'),
            'from_name': os.getenv('FROM_NAME', 'Your App')
        }
    
    @staticmethod
    def is_configured() -> bool:
        """Check if email is properly configured"""
        config = EmailConfig.get_smtp_config()
        required_fields = ['smtp_server', 'smtp_user', 'smtp_password', 'from_email']
        return all(config.get(field) for field in required_fields)

# === Email Templates ===
class EmailTemplates:
    """Email template collection"""
    
    OTP_TEMPLATE = """
Hello,

Your One-Time Password (OTP) for login is:

{otp}

This OTP will expire in {expiry_minutes} minutes.

If you did not request this OTP, please ignore this email.

Best regards,
{app_name}
"""

    TOKEN_DELIVERY_TEMPLATE = """
Hello {username},

Your account has been successfully created!

🔑 Your unique token: {token}

This token gives you secure access. Please keep it safe and do not share it with others.
You can also log in using your username/password or OTP via email.

Best regards,
{app_name} Team
"""

    PASSWORD_RESET_TEMPLATE = """
Hello,

You have requested to reset your password. Please use the following verification code:

{reset_code}

This code will expire in {expiry_minutes} minutes.

If you did not request this password reset, please ignore this email.

Best regards,
{app_name}
"""

    PASSWORD_RESET_SUCCESS_TEMPLATE = """
Hello,

Your password has been successfully reset at {timestamp}.

If you did not make this change, please contact support immediately.

Best regards,
{app_name}
"""

    WELCOME_TEMPLATE = """
Hello {username},

Welcome to {app_name}! Your account has been successfully created.

Email: {email}
Registration Date: {registration_date}
🔑 Your unique token: {token}

This token gives you secure access. Please keep it safe and do not share it with others.
You can also log in using your username/password or OTP via email.

Thank you for joining us!

Best regards,
{app_name} Team
"""

    SECURITY_ALERT_TEMPLATE = """
Hello,

We detected the following security activity on your account:

Action: {action}
Time: {timestamp}
Location: {location}

If this was not you, please contact support immediately and change your password.

Best regards,
{app_name} Security Team
"""

# === Core Email Functions ===
class EmailSender:
    """Main email sending class"""
    
    def __init__(self):
        self.config = EmailConfig.get_smtp_config()
        self.app_name = os.getenv('APP_NAME', 'Your Application')
    
    def send_email(self, to_email: str, subject: str, body: str, 
                   html_body: Optional[str] = None) -> tuple[bool, str]:
        """
        Send email using SMTP configuration
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)
        
        Returns:
            tuple[bool, str]: (success, message)
        """
        # Check if email is configured
        if not EmailConfig.is_configured():
            # For development/testing - log email instead of sending
            logger.info(f"[MOCK EMAIL] To: {to_email}, Subject: {subject}")
            logger.info(f"Body: {body}")
            if os.getenv('ENVIRONMENT') != 'production':
                return True, "Email sent (mock mode)"
            else:
                return False, "Email configuration missing"
        
        try:
            # Create message
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = f"{self.config['from_name']} <{self.config['from_email']}>"
            msg["To"] = to_email
            msg["Reply-To"] = self.config['from_email']
            
            # Set content
            msg.set_content(body)
            if html_body:
                msg.add_alternative(html_body, subtype='html')
            
            # Send email
            with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                server.starttls()
                server.login(self.config['smtp_user'], self.config['smtp_password'])
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True, "Email sent successfully"
            
        except smtplib.SMTPAuthenticationError:
            error_msg = "SMTP authentication failed. Check email credentials."
            logger.error(error_msg)
            return False, error_msg
            
        except smtplib.SMTPRecipientsRefused:
            error_msg = f"Invalid recipient email address: {to_email}"
            logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def send_otp_email(self, to_email: str, otp: str, expiry_minutes: int = 5) -> tuple[bool, str]:
        """Send OTP verification email"""
        subject = f"Your {self.app_name} Verification Code"
        body = EmailTemplates.OTP_TEMPLATE.format(
            otp=otp,
            expiry_minutes=expiry_minutes,
            app_name=self.app_name
        )
        
        return self.send_email(to_email, subject, body)
    
    def send_password_reset_email(self, to_email: str, reset_code: str, 
                                expiry_minutes: int = 15) -> tuple[bool, str]:
        """Send password reset email with verification code"""
        subject = f"{self.app_name} - Password Reset Code"
        body = EmailTemplates.PASSWORD_RESET_TEMPLATE.format(
            reset_code=reset_code,
            expiry_minutes=expiry_minutes,
            app_name=self.app_name
        )
        
        return self.send_email(to_email, subject, body)
    
    def send_password_reset_success_email(self, to_email: str) -> tuple[bool, str]:
        """Send confirmation email after successful password reset"""
        subject = f"{self.app_name} - Password Reset Successful"
        body = EmailTemplates.PASSWORD_RESET_SUCCESS_TEMPLATE.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            app_name=self.app_name
        )
        
        return self.send_email(to_email, subject, body)
    
    def send_token_email(self, email: str, username: str, token: str) -> tuple[bool, str]:
        """Send token delivery email (for registration)"""
        subject = f"✅ Your {self.app_name} Login Token"
        body = EmailTemplates.TOKEN_DELIVERY_TEMPLATE.format(
            username=username,
            token=token,
            app_name=self.app_name
        )
        
        return self.send_email(email, subject, body)
    
    def send_welcome_email(self, to_email: str, username: str, token: str = "") -> tuple[bool, str]:
        """Send welcome email to new users with optional token"""
        subject = f"Welcome to {self.app_name}!"
        body = EmailTemplates.WELCOME_TEMPLATE.format(
            username=username,
            email=to_email,
            app_name=self.app_name,
            registration_date=datetime.now().strftime("%Y-%m-%d"),
            token=token or "Not provided"
        )
        
        return self.send_email(to_email, subject, body)
    
    def send_security_alert(self, to_email: str, action: str, 
                          location: str = "Unknown") -> tuple[bool, str]:
        """Send security alert email"""
        subject = f"{self.app_name} - Security Alert"
        body = EmailTemplates.SECURITY_ALERT_TEMPLATE.format(
            action=action,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            location=location,
            app_name=self.app_name
        )
        
        return self.send_email(to_email, subject, body)

# === Utility Functions ===
def show_email_status(success: bool, message: str):
    """Display email status in Streamlit UI"""
    if success:
        st.success(f"✅ {message}")
    else:
        st.error(f"❌ {message}")

def check_email_config_ui():
    """Show email configuration status in Streamlit sidebar"""
    with st.sidebar:
        st.subheader("📧 Email Configuration")
        if EmailConfig.is_configured():
            st.success("✅ Email configured")
        else:
            st.warning("⚠️ Email not configured")
            st.info("Set email environment variables for production deployment")

# === Legacy Functions for Backward Compatibility ===
def send_otp_to_email(email: str, otp: str) -> tuple[bool, str]:
    """Legacy function name - redirects to send_otp_email"""
    sender = EmailSender()
    return sender.send_otp_email(email, otp)

def send_email_legacy(to_email: str = None, subject: str = "Notification", 
                     body: str = "", html_body: Optional[str] = None, 
                     email: str = None) -> bool:
    """Legacy send_email function for backward compatibility"""
    sender = EmailSender()
    recipient_email = to_email or email
    
    if not recipient_email:
        return False
    
    success, _ = sender.send_email(recipient_email, subject, body, html_body)
    return success
def validate_email_format(email: str) -> bool:
    """Basic email format validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_email_sender() -> EmailSender:
    """Get configured email sender instance"""
    return EmailSender()

# === For Testing ===
def test_email_configuration():
    """Test email configuration and sending"""
    sender = EmailSender()
    
    if not EmailConfig.is_configured():
        return False, "Email not configured"
    
    # Send test email to the configured sender email
    config = EmailConfig.get_smtp_config()
    test_email = config['from_email']
    
    success, message = sender.send_email(
        test_email,
        "Test Email Configuration",
        "This is a test email to verify email configuration is working."
    )
    
    return success, message
