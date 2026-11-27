import logging

from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# No real notification provider has been chosen yet (architecture risk register's "Likely
# Technical Debt #2") -- this is the one shared, framework-level primitive both
# apps.customers.services.notification_gateway.LoggingNotificationGateway (Issue #177) and
# apps.identity.services.password_recovery_service.PasswordRecoveryService call, so identity
# never has to call into customers (ADR 0004 establishes customers depends on identity, never
# the reverse -- see apps/customers/services/registration_service.py). Email actually leaves
# the process through Django's own `send_mail`, whose EMAIL_BACKEND is the console backend
# (config/settings.py) in every environment today -- this is the one sanctioned place a real
# OTP/reset-token value may appear in plaintext output (Issue #177 Security Requirements).


def send_console_email(*, to_email: str, subject: str, body: str) -> None:
    # from_email=None -> Django's EmailMessage falls back to settings.DEFAULT_FROM_EMAIL.
    send_mail(subject, body, None, [to_email], fail_silently=False)


def log_sms(*, to_phone: str, body: str) -> None:
    """No real SMS provider exists yet -- a documented known limitation, not a bug (see
    apps/customers/README.md). Logs at INFO so a code is still visible for manual
    verification in dev/CI, mirroring send_console_email's role for the email channel."""
    logger.info("SMS to %s: %s", to_phone, body)
