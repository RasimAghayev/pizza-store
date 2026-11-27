from rest_framework import exceptions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.api.serializers import CustomerRegistrationSerializer
from apps.customers.services.registration_service import (
    EmailAlreadyRegisteredError,
    RegistrationService,
)


class CustomerRegistrationView(APIView):
    """calls RegistrationService.register() -- see
    apps/customers/services/registration_service.py"""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request, version):
        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            customer = RegistrationService().register(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
            )
        except EmailAlreadyRegisteredError as exc:
            raise exceptions.ValidationError(
                {"email": "This email is already registered."}
            ) from exc

        return Response({"id": customer.pk}, status=201)
