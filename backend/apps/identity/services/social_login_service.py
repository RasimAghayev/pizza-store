from types import SimpleNamespace

from allauth.core.context import request_context
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter, get_adapter
from allauth.socialaccount.helpers import complete_social_login
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import RequestFactory

# calls apps.customers.services.registration_service.RegistrationService.provision_customer()
# -- see backend/apps/customers/README.md's "inbound calls" section. The direction
# (identity -> customers) mirrors the existing LoginView/RefreshView/LogoutView pattern:
# identity owns authentication, customers owns the customer-facing profile it provisions on
# a user's first-ever login (ADR 0004).
from apps.customers.services.registration_service import RegistrationService
from apps.identity.models import User
from apps.identity.repositories.user_repository import UserRepository
from apps.identity.services.session_service import SessionService, TokenPair

_PROVIDER_IDS = frozenset({"google", "apple", "facebook"})


class UnknownProviderError(Exception):
    """Raised for a provider_id outside {google, apple, facebook}."""


class InvalidProviderTokenError(Exception):
    """Raised when the provider itself rejects the token (expired, wrong audience, bad
    signature, ...) -- see each provider's own verify_token() in django-allauth."""


class AccountExistsUnlinkedError(Exception):
    """Raised when a social identity's verified email matches an existing identity.User that
    has no SocialAccount link yet. Per Issue #178's Security Requirements, this must never be
    silently connected/merged: the provider-claimed email is not something we can trust as
    proof of ownership of the existing account, so an attacker who controls (or has access
    to) a victim's social identity with a matching email could otherwise take over the
    victim's existing platform account. The caller must surface this as a distinct,
    actionable error instead of a generic failure."""

    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"An account already exists for {email} and is not linked.")


class PizzaStoreSocialAccountAdapter(DefaultSocialAccountAdapter):
    """settings.SOCIALACCOUNT_ADAPTER (Issue #178) -- the only behavior this project needs
    to override from django-allauth's defaults. Every other default (populate_user/save_user)
    already works correctly against identity.User's minimal, username-less shape once
    settings.ACCOUNT_USER_MODEL_USERNAME_FIELD = None (confirmed by reading
    allauth.account.internal.userkit.user_field: it is a documented no-op for a field that
    does not exist on the model, not an assumption)."""

    def pre_social_login(self, request, sociallogin) -> None:
        if sociallogin.is_existing:
            return
        verified_email = next((ea.email for ea in sociallogin.email_addresses if ea.verified), None)
        if verified_email is None:
            return
        if UserRepository().get_by_email(verified_email) is not None:
            raise AccountExistsUnlinkedError(verified_email)


def _build_isolated_request():
    """A disposable HttpRequest, never exposed to the real client and never routed through
    Django's middleware stack, that django-allauth's (non-headless) login internals can
    freely attach a session/user to -- see SocialLoginService.complete_login's own docstring
    for why this isolation exists. `allauth.core.context.request_context` is re-entered
    around every call into allauth so that any allauth-internal code reading the
    `allauth.core.context.request` context-local (rather than the `request` argument it was
    explicitly passed) also sees this disposable request, not the real one AccountMiddleware
    bound for the actual client request/response cycle."""
    request = RequestFactory().post("/")
    request.session = SessionStore()
    request.user = AnonymousUser()
    request.allauth = SimpleNamespace()
    return request


def _resolve_provider(provider_id: str, request):
    """calls allauth.socialaccount.adapter.DefaultSocialAccountAdapter.get_provider() -- the
    same provider-resolution path django-allauth's own views use, so this project's
    SOCIALACCOUNT_PROVIDERS settings-backed app configuration is honored identically."""
    return get_adapter(request).get_provider(request, provider_id)


class SocialLoginService:
    def __init__(
        self,
        session_service: SessionService | None = None,
        registration_service: RegistrationService | None = None,
    ) -> None:
        self._session_service = session_service or SessionService()
        self._registration_service = registration_service or RegistrationService()

    def complete_login(
        self,
        *,
        provider_id: str,
        token: dict,
        device_label: str = "",
        ip_address: str | None = None,
    ) -> TokenPair:
        if provider_id not in _PROVIDER_IDS:
            raise UnknownProviderError(provider_id)

        request = _build_isolated_request()
        with request_context(request):
            try:
                provider = _resolve_provider(provider_id, request)
                sociallogin = provider.verify_token(request, token)
            except DjangoValidationError as exc:
                raise InvalidProviderTokenError(provider_id) from exc
            except ImproperlyConfigured as exc:
                raise UnknownProviderError(provider_id) from exc

            try:
                complete_social_login(request, sociallogin)
            except ImmediateHttpResponse as exc:
                # The only built-in flow that can reach this with AUTO_SIGNUP=True and
                # ACCOUNT_ALLOW_SIGNUPS left at its default (True) is prevent_enumeration's
                # ImmediateHttpResponse, itself only reachable when PREVENT_ENUMERATION is
                # "strict" (not this project's default) -- kept as a defensive translation
                # rather than letting an internal allauth response type escape this service.
                raise InvalidProviderTokenError(provider_id) from exc

        user: User = sociallogin.user
        if user.pk is None:
            raise InvalidProviderTokenError(provider_id)

        # Idempotent (see RegistrationService.provision_customer's own docstring) -- called
        # unconditionally on every login, not just a brand-new social signup, since a second
        # login with the same social identity must reach this same no-op-if-already-
        # provisioned path, not a separate "is this the first login" branch to keep in sync.
        self._registration_service.provision_customer(user)

        return self._session_service.issue_tokens_for(
            user, device_label=device_label, ip_address=ip_address
        )
