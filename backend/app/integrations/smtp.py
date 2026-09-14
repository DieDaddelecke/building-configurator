"""Mailversand über SMTP. Anbieter offen (Spez. E2); lokal Mailpit."""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate

from app.config import Settings

TIMEOUT_SECONDS = 30


def send(settings: Settings, *, to: str, subject: str, body: str, message_id_key: str) -> str:
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    domain = settings.mail_from.rsplit("@", 1)[-1].rstrip(">") or "emprise.local"
    # Stabile Message-ID je Job: Empfänger erkennen eine Wiederholung als dieselbe Mail
    message["Message-ID"] = f"<{message_id_key}@{domain}>"
    message.set_content(body)

    smtp_class = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS) as smtp:
        if settings.smtp_starttls and not settings.smtp_ssl:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(message)
    return str(message["Message-ID"])
