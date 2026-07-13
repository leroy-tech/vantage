"""
Notifications: sends price-drop alerts via email (SMTP) and/or Telegram.

Configuration comes from environment variables (see .env.example), with an
optional per-user override stored in the preferences table — so in a
multi-user setup (e.g. several hostel-mates), each person can get alerts
sent to their own email/Telegram chat.

Per-user override keys (set via ShoppingAssistant.remember or db.set_preference):
    notify_email              -> overrides ALERT_EMAIL_TO for this user
    notify_telegram_chat_id   -> overrides TELEGRAM_CHAT_ID for this user

If neither env vars nor per-user preferences are set for a channel, that
channel is simply skipped (no crash) — this makes the feature fully
optional and safe to leave unconfigured.
"""

import smtplib
from email.mime.text import MIMEText
import requests

import db
from config import get_secret

SMTP_HOST = get_secret("SMTP_HOST")
SMTP_PORT = int(get_secret("SMTP_PORT", "587"))
SMTP_USER = get_secret("SMTP_USER")
SMTP_PASSWORD = get_secret("SMTP_PASSWORD")
DEFAULT_ALERT_EMAIL_TO = get_secret("ALERT_EMAIL_TO")

TELEGRAM_BOT_TOKEN = get_secret("TELEGRAM_BOT_TOKEN")
DEFAULT_TELEGRAM_CHAT_ID = get_secret("TELEGRAM_CHAT_ID")


def send_email(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    """Sends a plain-text email via SMTP. Returns (success, message)."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, to_email]):
        return False, "Email not configured (missing SMTP settings or recipient)."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        return True, f"Email sent to {to_email}"
    except Exception as e:
        return False, f"Email failed: {e}"


def send_telegram(chat_id: str, message: str) -> tuple[bool, str]:
    """Sends a message via the Telegram Bot API. Returns (success, message)."""
    if not all([TELEGRAM_BOT_TOKEN, chat_id]):
        return False, "Telegram not configured (missing bot token or chat id)."

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url, json={"chat_id": chat_id, "text": message}, timeout=10
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, "Telegram message sent"
        return False, f"Telegram API error: {resp.text}"
    except Exception as e:
        return False, f"Telegram failed: {e}"


def notify_price_alert(user_id: str, product_name: str, message: str) -> list[dict]:
    """
    Sends a price-drop alert to whichever channels are configured for this
    user (per-user preference first, falling back to env-var defaults).

    Returns a list of {"channel": ..., "success": ..., "detail": ...} so
    callers can log/display what actually happened.
    """
    prefs = db.get_preferences(user_id)
    email_to = prefs.get("notify_email", DEFAULT_ALERT_EMAIL_TO)
    telegram_chat_id = prefs.get("notify_telegram_chat_id", DEFAULT_TELEGRAM_CHAT_ID)

    subject = f"Price alert: {product_name}"
    full_message = f"{product_name}\n\n{message}"

    results = []

    if email_to:
        success, detail = send_email(email_to, subject, full_message)
        results.append({"channel": "email", "success": success, "detail": detail})

    if telegram_chat_id:
        success, detail = send_telegram(telegram_chat_id, full_message)
        results.append({"channel": "telegram", "success": success, "detail": detail})

    if not results:
        results.append({
            "channel": "none",
            "success": False,
            "detail": "No notification channel configured for this user.",
        })

    return results
