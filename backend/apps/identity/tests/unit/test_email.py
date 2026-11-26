import pytest

from apps.identity.domain.email import Email, InvalidEmailError


def test_email_normalizes_case_and_whitespace():
    email = Email("  User@Example.com ")

    assert email.value == "user@example.com"


def test_email_equality_and_hash_are_value_based():
    assert Email("same@example.com") == Email("SAME@example.com ")
    assert hash(Email("same@example.com")) == hash(Email("SAME@example.com "))


@pytest.mark.parametrize("raw", ["not-an-email", "missing-domain@", "@missing-local.com", ""])
def test_email_rejects_invalid_format(raw):
    with pytest.raises(InvalidEmailError):
        Email(raw)
