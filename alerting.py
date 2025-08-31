import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def send_alert(message: str, severity: str = "ERROR"):
    """
    Sends an alert via email and webhook.
    """
    # Send email alert
    send_email_alert(message, severity)

    # Send webhook alert
    send_webhook_alert(message, severity)

def send_email_alert(message: str, severity: str):
    """
    Sends an email alert using SMTP2GO.
    """
    contact_email = os.getenv('CONTACT_EMAIL')
    sender_email = os.getenv('SENDER_EMAIL')
    api_key = os.getenv('SMTP2GO_API_KEY')

    if not all([contact_email, sender_email, api_key]):
        return

    email_payload = {
        "sender": sender_email,
        "to": [contact_email],
        "subject": f"Bibliome Alert: {severity}",
        "text_body": message,
    }

    headers = {
        'Content-Type': 'application/json',
        'X-Smtp2go-Api-Key': api_key,
        'accept': 'application/json'
    }

    try:
        with httpx.Client() as client:
            client.post(
                'https://api.smtp2go.com/v3/email/send',
                json=email_payload,
                headers=headers,
                timeout=30.0
            )
    except Exception:
        pass

def send_webhook_alert(message: str, severity: str):
    """
    Sends a webhook alert.
    """
    webhook_url = os.getenv('WEBHOOK_URL')

    if not webhook_url:
        return

    payload = {
        "content": f"**{severity}**: {message}"
    }

    try:
        with httpx.Client() as client:
            client.post(webhook_url, json=payload)
    except Exception:
        pass
