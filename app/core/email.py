"""
app/core/email.py

SMTP email sender using Python stdlib only.
No paid services. Sends via Celery task so API never blocks.

WHY stdlib smtplib?
Zero dependencies. Works with Gmail, Outlook, Mailgun SMTP,
any standard SMTP server. In production swap smtp creds in .env.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_message(to_email: str, subject: str, html_body: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.email_from}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    return msg


def send_email_sync(to_email: str, subject: str, html_body: str) -> bool:
    """
    Blocking SMTP send. Always call from a Celery task, never from an async route.
    Returns True on success, False on failure (never raises — tasks handle retries).
    """
    if not settings.email_enabled:
        logger.info("email_skipped_disabled", to=to_email, subject=subject)
        return True

    try:
        msg = _build_message(to_email, subject, html_body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_from, to_email, msg.as_string())
        logger.info("email_sent", to=to_email, subject=subject)
        return True
    except Exception as exc:
        logger.error("email_failed", to=to_email, subject=subject, error=str(exc))
        return False


# ── Email templates ──────────────────────────────────────────

def render_transcription_complete(
    full_name: str | None,
    job_id: str,
    duration_seconds: float | None,
    word_count: int,
) -> tuple[str, str]:
    """Returns (subject, html_body)."""
    name = full_name or "there"
    duration = f"{round(duration_seconds / 60, 1)} minutes" if duration_seconds else "unknown"

    subject = "Your transcription is ready"
    html = f"""
    <html><body style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Transcription Complete</h2>
        <p>Hi {name},</p>
        <p>Your audio has been successfully transcribed.</p>
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Job ID</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{job_id}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Duration</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{duration}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Words</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{word_count:,}</td>
            </tr>
        </table>
        <p style="margin-top: 24px;">Log in to view and download your transcript.</p>
        <p style="color: #999; font-size: 12px;">STT Platform</p>
    </body></html>
    """
    return subject, html


def render_transcription_failed(
    full_name: str | None,
    job_id: str,
    error_message: str | None,
) -> tuple[str, str]:
    name = full_name or "there"
    error = error_message or "An unexpected error occurred."

    subject = "Transcription failed"
    html = f"""
    <html><body style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Transcription Failed</h2>
        <p>Hi {name},</p>
        <p>Unfortunately your transcription job could not be completed.</p>
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Job ID</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{job_id}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>Error</strong></td>
                <td style="padding: 8px; border: 1px solid #ddd;">{error}</td>
            </tr>
        </table>
        <p style="margin-top: 24px;">Please try uploading your file again.</p>
        <p style="color: #999; font-size: 12px;">STT Platform</p>
    </body></html>
    """
    return subject, html