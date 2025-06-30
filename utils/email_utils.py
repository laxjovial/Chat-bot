# utils/email_utils.py

import smtplib
from email.message import EmailMessage
import yaml
import os

# === Config ===
CONFIG_FILE = "data/smtp_config.yml"

DEFAULT_SENDER = "no-reply@example.com"
DEFAULT_SUBJECT = "Notification"

# === Load SMTP config ===
def load_smtp_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f)
    return {}


# === Send email ===
def send_email(to_email: str, subject: str = DEFAULT_SUBJECT, body: str = "") -> bool:
    config = load_smtp_config()

    if not config:
        print(f"[Mock Email] To: {to_email} | Subject: {subject}\n{body}\n")
        return False

    try:
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port", 587)
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        sender = config.get("from_email", DEFAULT_SENDER)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        msg.set_content(body)

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True

    except Exception as e:
        print(f"[Email Failed] {e}")
        return False


# === CLI Test ===
if __name__ == "__main__":
    send_email("you@example.com", "Test Email", "This is a test message.")
