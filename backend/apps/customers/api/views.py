from rest_framework import exceptions
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.api.serializers import (
    AddressCreateSerializer,
    AddressSerializer,
    AddressUpdateSerializer,
    CustomerRegistrationSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
)
from apps.customers.services.address_service import AddressNotFoundError, AddressService
from apps.customers.services.profile_service import (
    ConsentRequiredError,
    CustomerNotFoundError,
    ProfileService,
)
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


class ProfileView(APIView):
    """calls ProfileService -- see apps/customers/services/profile_service.py.
    Ownership-only: a request always reads/writes the Customer row for `request.user`,
    never a client-supplied id -- no RBAC scope needed, unlike the staff-facing modules'
    `TwoStepPermission` (Issue #179)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, version):
        return Response(ProfileSerializer(self._get_customer(request)).data)

    def patch(self, request, version):
        self._get_customer(request)
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = ProfileService().update_profile(request.user.pk, **serializer.validated_data)
        except ConsentRequiredError as exc:
            raise exceptions.ValidationError(
                {"date_of_birth": "Consent must be recorded before setting date of birth."}
            ) from exc
        return Response(ProfileSerializer(updated).data)

    def _get_customer(self, request):
        try:
            return ProfileService().get_profile(request.user.pk)
        except CustomerNotFoundError as exc:
            raise exceptions.NotFound("Customer profile not found.") from exc


class ProfileConsentView(APIView):
    """calls ProfileService.record_consent() -- see
    apps/customers/services/profile_service.py. A dedicated action rather than folding
    consent into ProfileView.patch: consent is a one-way, auditable event
    (`consent_personal_data_at`), not an ordinary profile field edit."""

    permission_classes = [IsAuthenticated]

    def post(self, request, version):
        try:
            customer = ProfileService().record_consent(request.user.pk)
        except CustomerNotFoundError as exc:
            raise exceptions.NotFound("Customer profile not found.") from exc
        return Response(ProfileSerializer(customer).data)


class AddressListCreateView(APIView):
    """calls AddressService -- see apps/customers/services/address_service.py."""

    permission_classes = [IsAuthenticated]

    def get(self, request, version):
        addresses = AddressService().list_for_customer(request.user.pk)
        return Response(AddressSerializer(addresses, many=True).data)

    def post(self, request, version):
        serializer = AddressCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            address = AddressService().create(user_id=request.user.pk, **serializer.validated_data)
        except CustomerNotFoundError as exc:
            raise exceptions.NotFound("Customer profile not found.") from exc
        return Response(AddressSerializer(address).data, status=201)


class AddressDetailView(APIView):
    """calls AddressService -- see apps/customers/services/address_service.py. Every
    lookup is scoped to `request.user`'s own Customer row; a valid id owned by a different
    customer returns 404, never 403, so a request can't distinguish "not yours" from
    "doesn't exist" (Issue #179 Security Requirements)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, version, pk):
        return Response(AddressSerializer(self._get_owned(request, pk)).data)

    def patch(self, request, version, pk):
        self._get_owned(request, pk)
        serializer = AddressUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = AddressService().update(
            user_id=request.user.pk, address_id=pk, **serializer.validated_data
        )
        return Response(AddressSerializer(updated).data)

    def delete(self, request, version, pk):
        self._get_owned(request, pk)
        AddressService().delete(user_id=request.user.pk, address_id=pk)
        return Response(status=204)

    def _get_owned(self, request, pk: int):
        try:
            return AddressService().get_owned(user_id=request.user.pk, address_id=pk)
        except AddressNotFoundError as exc:
            raise exceptions.NotFound("Address not found.") from exc
