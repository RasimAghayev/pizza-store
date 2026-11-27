from types import SimpleNamespace

import pytest

from apps.identity.services.social_login_service import (
    AccountExistsUnlinkedError,
    PizzaStoreSocialAccountAdapter,
    SocialLoginService,
    UnknownProviderError,
)
from apps.identity.tests.factories import UserFactory


def _sociallogin(*, is_existing, email_addresses):
    return SimpleNamespace(is_existing=is_existing, email_addresses=email_addresses)


def _email_address(email, verified):
    return SimpleNamespace(email=email, verified=verified)


@pytest.mark.django_db
def test_pre_social_login_is_a_no_op_for_an_existing_social_account():
    user = UserFactory()
    sociallogin = _sociallogin(is_existing=True, email_addresses=[_email_address(user.email, True)])

    PizzaStoreSocialAccountAdapter().pre_social_login(None, sociallogin)


@pytest.mark.django_db
def test_pre_social_login_is_a_no_op_without_a_verified_email():
    """An unverified provider-claimed email is never trustworthy enough to even check for a
    collision -- doing so would turn this endpoint into an email-existence oracle for any
    provider that never verifies (e.g. Facebook's classic Graph API response)."""
    user = UserFactory()
    sociallogin = _sociallogin(
        is_existing=False, email_addresses=[_email_address(user.email, False)]
    )

    PizzaStoreSocialAccountAdapter().pre_social_login(None, sociallogin)


@pytest.mark.django_db
def test_pre_social_login_raises_for_a_verified_email_matching_an_unlinked_account():
    user = UserFactory()
    sociallogin = _sociallogin(
        is_existing=False, email_addresses=[_email_address(user.email, True)]
    )

    with pytest.raises(AccountExistsUnlinkedError):
        PizzaStoreSocialAccountAdapter().pre_social_login(None, sociallogin)


@pytest.mark.django_db
def test_pre_social_login_is_a_no_op_for_a_brand_new_verified_email():
    sociallogin = _sociallogin(
        is_existing=False, email_addresses=[_email_address("brand-new@example.com", True)]
    )

    PizzaStoreSocialAccountAdapter().pre_social_login(None, sociallogin)


def test_complete_login_rejects_an_unknown_provider():
    with pytest.raises(UnknownProviderError):
        SocialLoginService().complete_login(provider_id="not-a-real-provider", token={})
