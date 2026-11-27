import threading

import pytest
from django.db import connection

from apps.identity.tests.factories import UserFactory
from shared.idempotency.models import IdempotencyKey
from shared.idempotency.service import (
    IdempotencyConflictError,
    IdempotencyKeyOwnershipError,
    IdempotencyService,
)

SCOPE = "test.scope"


@pytest.mark.django_db
def test_first_call_runs_the_handler_and_stores_the_result():
    user = UserFactory()
    calls = []

    def handler():
        calls.append(1)
        return 201, {"id": 1}

    result = IdempotencyService().run_once(
        key="key-1", scope=SCOPE, user_id=user.id, request_payload={"a": 1}, handler=handler
    )

    assert result.status == 201
    assert result.body == {"id": 1}
    assert result.replayed is False
    assert len(calls) == 1
    assert IdempotencyKey.objects.filter(key="key-1", scope=SCOPE).exists()


@pytest.mark.django_db
def test_a_replay_with_an_identical_body_returns_the_cached_result_without_rerunning_handler():
    user = UserFactory()
    calls = []

    def handler():
        calls.append(1)
        return 201, {"id": 1}

    service = IdempotencyService()
    first = service.run_once(
        key="key-2", scope=SCOPE, user_id=user.id, request_payload={"a": 1}, handler=handler
    )
    second = service.run_once(
        key="key-2", scope=SCOPE, user_id=user.id, request_payload={"a": 1}, handler=handler
    )

    assert first.replayed is False
    assert second.replayed is True
    assert second.status == first.status
    assert second.body == first.body
    assert len(calls) == 1  # handler never ran a second time


@pytest.mark.django_db
def test_a_replay_with_a_different_body_for_the_same_key_raises_conflict():
    user = UserFactory()
    service = IdempotencyService()
    service.run_once(
        key="key-3",
        scope=SCOPE,
        user_id=user.id,
        request_payload={"a": 1},
        handler=lambda: (201, {"id": 1}),
    )

    with pytest.raises(IdempotencyConflictError):
        service.run_once(
            key="key-3",
            scope=SCOPE,
            user_id=user.id,
            request_payload={"a": 2},
            handler=lambda: (201, {"id": 2}),
        )


@pytest.mark.django_db
def test_the_same_key_value_in_a_different_scope_does_not_collide():
    user = UserFactory()
    service = IdempotencyService()
    first = service.run_once(
        key="shared-key",
        scope="scope.one",
        user_id=user.id,
        request_payload={"a": 1},
        handler=lambda: (201, {"id": 1}),
    )
    second = service.run_once(
        key="shared-key",
        scope="scope.two",
        user_id=user.id,
        request_payload={"a": 1},
        handler=lambda: (201, {"id": 2}),
    )

    assert first.replayed is False
    assert second.replayed is False
    assert first.body != second.body


@pytest.mark.django_db
def test_a_different_user_reusing_the_same_key_and_scope_is_denied():
    owner = UserFactory()
    other_user = UserFactory()
    service = IdempotencyService()
    service.run_once(
        key="key-4",
        scope=SCOPE,
        user_id=owner.id,
        request_payload={"a": 1},
        handler=lambda: (201, {"id": 1}),
    )

    with pytest.raises(IdempotencyKeyOwnershipError):
        service.run_once(
            key="key-4",
            scope=SCOPE,
            user_id=other_user.id,
            request_payload={"a": 1},
            handler=lambda: (201, {"id": 1}),
        )


@pytest.mark.django_db
def test_when_the_handler_raises_nothing_is_cached_and_the_exception_propagates():
    user = UserFactory()

    def failing_handler():
        raise RuntimeError("transient failure")

    with pytest.raises(RuntimeError):
        IdempotencyService().run_once(
            key="key-5",
            scope=SCOPE,
            user_id=user.id,
            request_payload={"a": 1},
            handler=failing_handler,
        )

    assert not IdempotencyKey.objects.filter(key="key-5", scope=SCOPE).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_for_the_same_key_never_return_two_different_responses():
    """Two real threads (separate DB connections) both pass the initial `_find() is None`
    check before either commits, then both attempt the create -- exactly one wins, the other
    hits the unique constraint and must replay the winner's response rather than raising or
    returning its own, different result."""
    user = UserFactory()
    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []

    def handler():
        barrier.wait(timeout=5)  # widen the race window so both threads overlap
        return 201, {"id": threading.get_ident()}

    def worker():
        try:
            result = IdempotencyService().run_once(
                key="key-6",
                scope=SCOPE,
                user_id=user.id,
                request_payload={"a": 1},
                handler=handler,
            )
            results.append(result)
        except Exception as exc:  # noqa: BLE001 -- captured for the main thread to assert on
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert len(results) == 2
    assert results[0].body == results[1].body
    assert {result.replayed for result in results} == {False, True}
