import pytest

from health.factories import HealthPingFactory
from health.models import HealthPing


@pytest.mark.django_db
def test_health_ping_factory_persists_a_real_row():
    ping = HealthPingFactory()

    assert HealthPing.objects.count() == 1
    assert HealthPing.objects.get(pk=ping.pk).note == ping.note


def test_health_endpoint_returns_ok(client):
    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
