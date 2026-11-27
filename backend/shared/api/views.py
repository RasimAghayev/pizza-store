from rest_framework.response import Response
from rest_framework.views import APIView


class PingView(APIView):
    """Conventions-proof endpoint only (Issue #128): exercises URL-path versioning, the
    OpenAPI schema generator, and the error envelope against a real route. Not a product
    endpoint -- later modules do not depend on it. Distinct from health.views.health, the
    Compose-level liveness probe, which stays outside API versioning."""

    def get(self, request, version):
        return Response({"message": "pong"})
