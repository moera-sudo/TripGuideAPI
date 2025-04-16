from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pathlib import Path
from config.appsettings import Settings
import logging

logger = logging.getLogger(__name__)

class EmailService:
    _client: FastMail = None

    @staticmethod
    def _get_mail_client() -> FastMail:
        """Ленивая инициализация FastMail клиента"""
        if EmailService._client is None:
            config = ConnectionConfig(
                MAIL_USERNAME=Settings.MAIL_USERNAME,
                MAIL_PASSWORD=Settings.MAIL_PASSWORD,
                MAIL_FROM=Settings.MAIL_FROM,
                MAIL_PORT=Settings.MAIL_PORT,
                MAIL_SERVER=Settings.MAIL_SERVER,
                MAIL_FROM_NAME=Settings.MAIL_FROM_NAME,
                MAIL_STARTTLS=True,
                MAIL_SSL_TLS=False,
                USE_CREDENTIALS=True,
                VALIDATE_CERTS=True,
                TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates"
            )
            EmailService._client = FastMail(config)
        return EmailService._client

    @staticmethod
    async def send_verification_email(email: str, code: str) -> bool:
        """Отправка email для подтверждения аккаунта"""
        return await EmailService._send_email(
            subject="Подтверждение аккаунта",
            email=email,
            template_name="email_verification.html",
            body={
                "title": "Подтверждение аккаунта",
                "verification_code": code,
                "expires_in_minutes": Settings.VERIFICATION_CODE_EXPIRE_MINUTES,
                "account_verification": True
            }
        )

    @staticmethod
    async def send_password_recovery_email(email: str, code: str) -> bool:
        """Отправка email для восстановления пароля"""
        return await EmailService._send_email(
            subject="Восстановление пароля",
            email=email,
            template_name="password_recovery.html",
            body={
                "title": "Восстановление пароля",
                "verification_code": code,
                "expires_in_minutes": Settings.VERIFICATION_CODE_EXPIRE_MINUTES,
                "password_recovery": True
            }
        )

    @staticmethod
    async def _send_email(subject: str, email: str, template_name: str, body: dict) -> bool:
        """Базовая логика отправки"""
        try:
            message = MessageSchema(
                subject=subject,
                recipients=[email],
                template_body=body,
                subtype="html"
            )

            await EmailService._get_mail_client().send_message(message, template_name=template_name)
            logger.info(f"Email sent successfully to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {e}")
            return False
