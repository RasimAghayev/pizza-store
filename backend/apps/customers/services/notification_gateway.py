from typing import Protocol

from shared.notifications.console_gateway import log_sms, send_console_email


class NotificationGateway(Protocol):
    def send_email_otp(self, email: str, code: str) -> None: ...

    def send_sms_otp(self, phone: str, code: str) -> None: ...


class LoggingNotificationGateway:
    """Only implementation until a real email/SMS provider is chosen as its own,
    explicitly-scoped Task (architecture risk register's "Likely Technical Debt #2" --
    mirrors the risk register's accepted precedent for the Payment Gateway Abstraction).
    Email is real-ish: it goes out through Django's console email backend via
    shared/notifications/console_gateway.py. SMS has no real provider at all yet, so it only
    logs -- a documented known limitation (see apps/customers/README.md), not a bug."""

    def send_email_otp(self, email: str, code: str) -> None:
        send_console_email(
            to_email=email,
            subject="Your Pizza Store verification code",
            body=f"Your verification code is {code}. It expires in 5 minutes.",
        )

    def send_sms_otp(self, phone: str, code: str) -> None:
        log_sms(to_phone=phone, body=f"Your verification code is {code}. It expires in 5 minutes.")
