from django.test import override_settings
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from shared.api.exception_handler import api_exception_handler


class _ProofSerializer(serializers.Serializer):
    quantity = serializers.IntegerField()


class _ProofView(APIView):
    def post(self, request):
        serializer = _ProofSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


def test_a_malformed_request_returns_the_error_envelope():
    request = APIRequestFactory().post("/proof/", {"quantity": "not-a-number"}, format="json")

    response = _ProofView.as_view()(request)

    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
    assert "quantity" in response.data["error"]["details"]


@override_settings(DEBUG=False)
def test_an_unhandled_exception_does_not_leak_internals_when_debug_is_false():
    secret = "super-secret-internal-detail-12345"

    response = api_exception_handler(ValueError(secret), {})

    assert response.status_code == 500
    assert response.data["error"]["code"] == "internal_error"
    assert secret not in response.data["error"]["message"]
    assert response.data["error"]["details"] == {}
