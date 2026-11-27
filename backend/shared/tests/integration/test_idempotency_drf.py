import pytest
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.identity.tests.factories import UserFactory
from shared.idempotency.drf import IdempotentActionMixin

SCOPE = "test.drf-scope"


class _ProofView(IdempotentActionMixin, APIView):
    call_count = 0

    def post(self, request, *args, **kwargs):
        def handler():
            type(self).call_count += 1
            return 201, {"created": type(self).call_count}

        return self.perform_idempotent(scope=SCOPE, handler=handler)


@pytest.fixture(autouse=True)
def _reset_call_count():
    _ProofView.call_count = 0


def _authenticated_post(body, user, idempotency_key=None):
    factory = APIRequestFactory()
    headers = {}
    if idempotency_key is not None:
        headers["HTTP_IDEMPOTENCY_KEY"] = idempotency_key
    request = factory.post("/proof/", body, format="json", **headers)
    force_authenticate(request, user=user)
    return request


@pytest.mark.django_db
def test_missing_header_runs_the_handler_normally_every_time():
    user = UserFactory()
    first = _ProofView.as_view()(_authenticated_post({"a": 1}, user))
    second = _ProofView.as_view()(_authenticated_post({"a": 1}, user))

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data != second.data  # no dedup at all without the header
    assert _ProofView.call_count == 2


@pytest.mark.django_db
def test_a_duplicate_request_with_the_same_key_and_body_replays_without_rerunning_handler():
    user = UserFactory()
    first = _ProofView.as_view()(_authenticated_post({"a": 1}, user, idempotency_key="abc-123"))
    second = _ProofView.as_view()(_authenticated_post({"a": 1}, user, idempotency_key="abc-123"))

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.data == first.data
    assert _ProofView.call_count == 1


@pytest.mark.django_db
def test_reusing_the_same_key_with_a_different_body_returns_409_conflict():
    user = UserFactory()
    first = _ProofView.as_view()(_authenticated_post({"a": 1}, user, idempotency_key="abc-456"))
    second = _ProofView.as_view()(_authenticated_post({"a": 2}, user, idempotency_key="abc-456"))

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.data["error"]["code"] == "conflict"


@pytest.mark.django_db
def test_a_different_user_reusing_someone_elses_key_is_forbidden_not_replayed():
    owner_request = APIRequestFactory().post(
        "/proof/", {"a": 1}, format="json", HTTP_IDEMPOTENCY_KEY="abc-789"
    )
    force_authenticate(owner_request, user=UserFactory())
    first = _ProofView.as_view()(owner_request)
    assert first.status_code == 201

    other_request = APIRequestFactory().post(
        "/proof/", {"a": 1}, format="json", HTTP_IDEMPOTENCY_KEY="abc-789"
    )
    force_authenticate(other_request, user=UserFactory())
    second = _ProofView.as_view()(other_request)

    assert second.status_code == 403
    assert second.data["error"]["code"] == "permission_denied"
    assert "abc-789" not in second.data["error"]["message"]
