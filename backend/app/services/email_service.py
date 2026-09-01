import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.core.config import settings

logger = logging.getLogger("sutra.email_service")


class EmailService:
    """
    Service responsible for sending email notifications (OTP verification, password reset).
    Supports production SMTP delivery as well as an in-memory / console test delivery mode.
    """

    # In-memory record for test suite inspection
    _test_inbox: list[dict[str, Any]] = []

    @classmethod
    def clear_test_inbox(cls) -> None:
        cls._test_inbox.clear()

    @classmethod
    def get_test_inbox(cls) -> list[dict[str, Any]]:
        return list(cls._test_inbox)

    @classmethod
    def get_last_sent(cls, email: str | None = None) -> dict[str, Any] | None:
        if not cls._test_inbox:
            return None
        if email is None:
            return cls._test_inbox[-1]
        for item in reversed(cls._test_inbox):
            if item.get("to") == email:
                return item
        return None

    @classmethod
    def send_verification_otp(cls, email: str, otp: str) -> bool:
        """
        Send a 6-digit email verification OTP to the user.
        """
        subject = f"{settings.app_name} - Verify your email address"
        body_text = (
            f"Welcome to {settings.app_name}!\n\n"
            f"Your 6-digit email verification code is: {otp}\n\n"
            f"This code will expire in {settings.otp_expire_minutes} minutes.\n"
            f"If you did not create a {settings.app_name} account, please ignore this email."
        )
        body_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; background-color: #0b0f19; color: #e2e8f0; border-radius: 12px; border: 1px solid #1e293b;">
            <div style="margin-bottom: 24px; font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">
                SUTRA
            </div>
            <h2 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0 0 12px 0;">Verify your email address</h2>
            <p style="font-size: 14px; line-height: 22px; color: #94a3b8; margin: 0 0 24px 0;">
                Thank you for joining {settings.app_name}. Use the 6-digit verification code below to complete your registration:
            </p>
            <div style="background-color: #131d31; border: 1px solid #2a3a5a; border-radius: 8px; padding: 18px; text-align: center; margin: 0 0 24px 0;">
                <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #60a5fa; font-family: monospace;">{otp}</span>
            </div>
            <p style="font-size: 12px; line-height: 18px; color: #64748b; margin: 0 0 8px 0;">
                This code is valid for <strong>{settings.otp_expire_minutes} minutes</strong> and can only be used once.
            </p>
            <p style="font-size: 12px; line-height: 18px; color: #64748b; margin: 0;">
                If you did not request this, please ignore this email.
            </p>
        </div>
        """

        return cls._deliver(
            to_email=email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            email_type="verification_otp",
            metadata={"otp": otp},
        )

    @classmethod
    def send_password_reset(cls, email: str, reset_url: str) -> bool:
        """
        Send a password reset link to the user.
        """
        subject = f"{settings.app_name} - Reset your password"
        body_text = (
            f"Hello,\n\n"
            f"We received a request to reset your password for your {settings.app_name} account.\n\n"
            f"Click the link below to set a new password:\n"
            f"{reset_url}\n\n"
            f"This link will expire in {settings.password_reset_expire_minutes} minutes.\n"
            f"If you did not request a password reset, you can safely ignore this email."
        )
        body_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px; background-color: #0b0f19; color: #e2e8f0; border-radius: 12px; border: 1px solid #1e293b;">
            <div style="margin-bottom: 24px; font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">
                SUTRA
            </div>
            <h2 style="font-size: 18px; font-weight: 600; color: #f8fafc; margin: 0 0 12px 0;">Reset your password</h2>
            <p style="font-size: 14px; line-height: 22px; color: #94a3b8; margin: 0 0 24px 0;">
                We received a request to reset the password for your account associated with <strong>{email}</strong>. Click the button below to choose a new password:
            </p>
            <div style="text-align: center; margin: 0 0 24px 0;">
                <a href="{reset_url}" style="display: inline-block; background-color: #3b82f6; color: #ffffff; font-size: 14px; font-weight: 600; text-decoration: none; padding: 12px 28px; border-radius: 8px;">
                    Reset Password
                </a>
            </div>
            <p style="font-size: 12px; line-height: 18px; color: #64748b; margin: 0 0 8px 0;">
                This link will expire in <strong>{settings.password_reset_expire_minutes} minutes</strong>.
            </p>
            <p style="font-size: 12px; line-height: 18px; color: #64748b; margin: 0;">
                If you did not request a password reset, you can safely ignore this email.
            </p>
        </div>
        """

        return cls._deliver(
            to_email=email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            email_type="password_reset",
            metadata={"reset_url": reset_url},
        )

    @classmethod
    def _deliver(
        cls,
        to_email: str,
        subject: str,
        body_text: str,
        email_type: str,
        body_html: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Deliver the email via SMTP if configured, or record in test inbox / logger.
        """
        # Always record in test inbox for test verification
        cls._test_inbox.append({
            "to": to_email,
            "subject": subject,
            "body": body_text,
            "type": email_type,
            "metadata": metadata or {},
        })

        if not settings.smtp_host:
            # Development / Mock mode
            logger.info("Email [%s] dispatched to %s (Mock Mode: SMTP not configured)", email_type, to_email)
            return True

        # Production SMTP delivery
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = f"{settings.app_name} <{settings.email_sender}>"
            msg["To"] = to_email
            msg.set_content(body_text)
            if body_html:
                msg.add_alternative(body_html, subtype="html")

            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
            server.quit()
            logger.info("Email [%s] delivered via SMTP to %s", email_type, to_email)
            return True
        except Exception as exc:
            logger.error("Failed to send email [%s] to %s via SMTP: %s", email_type, to_email, str(exc))
            return False
