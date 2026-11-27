from rest_framework import exceptions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.api.serializers import (
    AllergenCreateSerializer,
    AllergenSerializer,
    OptionChoiceCreateSerializer,
    OptionChoiceSerializer,
    OptionGroupCreateSerializer,
    OptionGroupSerializer,
    PriceQuoteRequestSerializer,
    PriceQuoteResponseSerializer,
    ProductCreateSerializer,
    ProductSerializer,
    ProductToppingAttachSerializer,
    ProductToppingSerializer,
    ProductUpdateSerializer,
    ToppingCreateSerializer,
    ToppingSerializer,
    ToppingUpdateSerializer,
)
from apps.products.models import Product
from apps.products.services.catalog_service import (
    AllergenNotFoundError,
    CatalogService,
    ToppingNotFoundError,
)
from apps.products.services.pricing_service import InvalidPriceQuoteError, PricingService
from apps.products.services.product_service import ProductNotFoundError, ProductService

# calls apps.restaurants.services.organization_service.OrganizationNotFoundError -- see
# backend/apps/restaurants/README.md. Surfaced here only to translate it into the standard
# validation_error envelope; products never imports apps.restaurants.models/repositories.
from apps.restaurants.services.organization_service import OrganizationNotFoundError
from shared.permissions.base import TwoStepPermission


class _ScopesToOwningOrganization:
    """Shared scope hooks for Product and every Product-nested resource below -- Product
    carries `organization_id` directly (Issue #181: "store organization_id as a plain field
    on Product"), so no cross-module lookup is needed, unlike Branch's."""

    def scope_organization_id(self, obj: Product) -> int | None:
        return obj.organization_id

    def scope_branch_id(self, obj: Product) -> int | None:
        return None


class _PlatformCatalogScoped:
    """Scope hooks for Topping/Allergen -- both are a shared, platform-wide catalog with no
    organization/branch dimension of their own (Issue #181's model definitions carry no
    such field). Always returning None for both means, per TwoStepPermission's matching
    logic (shared/permissions/base.py), only an unscoped `products.edit` grant (e.g. Super
    Admin) can create/edit/delete a catalog row -- an org-scoped Organization Owner can
    still attach *existing* toppings to their own products via ProductService, a separate,
    Product-scoped check. `obj` is intentionally ignored; passing `None` into
    `check_object_permissions` is safe since TwoStepPermission never dereferences it itself."""

    def scope_organization_id(self, obj: object) -> int | None:
        return None

    def scope_branch_id(self, obj: object) -> int | None:
        return None


class ProductListCreateView(_ScopesToOwningOrganization, APIView):
    """calls ProductService -- see apps/products/services/product_service.py. Read is
    public (AllowAny) -- menu-browsing needs this before login exists, same pattern as
    Restaurant/Branch (Issue #180). Unlike Restaurant/Branch, listing requires an explicit
    `organization_id` filter -- Product is per-tenant menu data, not a handful of
    platform-wide rows, so there is no sensible "every product across every organization"
    public listing."""

    required_permission = "products.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version):
        raw_organization_id = request.query_params.get("organization_id")
        if raw_organization_id is None:
            raise exceptions.ValidationError({"organization_id": "Required."})
        try:
            organization_id = int(raw_organization_id)
        except ValueError as exc:
            raise exceptions.ValidationError({"organization_id": "Must be an integer."}) from exc
        products = ProductService().list_for_organization(organization_id)
        return Response(ProductSerializer(products, many=True).data)

    def post(self, request, version):
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provisional = Product(organization_id=serializer.validated_data["organization_id"])
        self.check_object_permissions(request, provisional)

        try:
            product = ProductService().create(**serializer.validated_data)
        except OrganizationNotFoundError as exc:
            raise exceptions.ValidationError(
                {"organization_id": "Organization not found."}
            ) from exc
        except AllergenNotFoundError as exc:
            raise exceptions.ValidationError(
                {"allergen_ids": "One or more allergens not found."}
            ) from exc
        return Response(ProductSerializer(product).data, status=201)


class ProductDetailView(_ScopesToOwningOrganization, APIView):
    """calls ProductService -- see apps/products/services/product_service.py."""

    required_permission = "products.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk):
        product = ProductService().get_by_id(pk)
        if product is None:
            raise exceptions.NotFound("Product not found.")
        return Response(ProductSerializer(product).data)

    def patch(self, request, version, pk):
        product = self._get_object_for_write(request, pk)
        serializer = ProductUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = ProductService().update(product.pk, **serializer.validated_data)
        except AllergenNotFoundError as exc:
            raise exceptions.ValidationError(
                {"allergen_ids": "One or more allergens not found."}
            ) from exc
        return Response(ProductSerializer(updated).data)

    def delete(self, request, version, pk):
        product = self._get_object_for_write(request, pk)
        ProductService().delete(product.pk)
        return Response(status=204)

    def _get_object_for_write(self, request, pk: int) -> Product:
        product = ProductService().get_by_id(pk)
        if product is None:
            raise exceptions.NotFound("Product not found.")
        self.check_object_permissions(request, product)
        return product


class ProductOptionGroupsView(_ScopesToOwningOrganization, APIView):
    """calls ProductService.{add_option_group,option_groups_for} -- see
    apps/products/services/product_service.py. Read is public; only adding a group
    requires the product's own `products.edit` scope."""

    required_permission = "products.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk):
        product = self._require_product(pk)
        groups = ProductService().option_groups_for(product.pk)
        return Response(OptionGroupSerializer(groups, many=True).data)

    def post(self, request, version, pk):
        product = self._require_product(pk)
        self.check_object_permissions(request, product)
        serializer = OptionGroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = ProductService().add_option_group(
            product_id=product.pk, **serializer.validated_data
        )
        return Response(OptionGroupSerializer(group).data, status=201)

    @staticmethod
    def _require_product(pk: int) -> Product:
        product = ProductService().get_by_id(pk)
        if product is None:
            raise exceptions.NotFound("Product not found.")
        return product


class OptionGroupChoicesView(_ScopesToOwningOrganization, APIView):
    """calls ProductService.{add_option_choice,option_choices_for} -- see
    apps/products/services/product_service.py."""

    required_permission = "products.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk, group_id):
        self._require_group(pk, group_id)
        choices = ProductService().option_choices_for(group_id)
        return Response(OptionChoiceSerializer(choices, many=True).data)

    def post(self, request, version, pk, group_id):
        product = self._require_product(pk)
        self.check_object_permissions(request, product)
        self._require_group(pk, group_id)
        serializer = OptionChoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        choice = ProductService().add_option_choice(
            option_group_id=group_id, **serializer.validated_data
        )
        return Response(OptionChoiceSerializer(choice).data, status=201)

    @staticmethod
    def _require_product(pk: int) -> Product:
        product = ProductService().get_by_id(pk)
        if product is None:
            raise exceptions.NotFound("Product not found.")
        return product

    @staticmethod
    def _require_group(pk: int, group_id: int):
        group = ProductService().get_option_group(group_id)
        if group is None or group.product_id != pk:
            raise exceptions.NotFound("Option group not found.")
        return group


class ProductToppingsView(_ScopesToOwningOrganization, APIView):
    """calls ProductService.{attach_topping,toppings_for} -- see
    apps/products/services/product_service.py. Read is public; attaching an *existing*
    catalog topping to a product requires only the product's own `products.edit` scope --
    managing the shared catalog itself is a separate, unscoped-only check (see
    `_PlatformCatalogScoped` on ToppingListCreateView/ToppingDetailView)."""

    required_permission = "products.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk):
        product = self._require_product(pk)
        product_toppings = ProductService().toppings_for(product.pk)
        return Response(ProductToppingSerializer(product_toppings, many=True).data)

    def post(self, request, version, pk):
        product = self._require_product(pk)
        self.check_object_permissions(request, product)
        serializer = ProductToppingAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product_topping = ProductService().attach_topping(
                product_id=product.pk, **serializer.validated_data
            )
        except ToppingNotFoundError as exc:
            raise exceptions.ValidationError({"topping_id": "Topping not found."}) from exc
        return Response(ProductToppingSerializer(product_topping).data, status=201)

    @staticmethod
    def _require_product(pk: int) -> Product:
        product = ProductService().get_by_id(pk)
        if product is None:
            raise exceptions.NotFound("Product not found.")
        return product


class ProductToppingDetailView(_ScopesToOwningOrganization, APIView):
    """calls ProductService.detach_topping -- see apps/products/services/product_service.py."""

    required_permission = "products.edit"
    permission_classes = [TwoStepPermission]

    def delete(self, request, version, pk, topping_id):
        product = ProductService().get_by_id(pk)
        if product is None:
            raise exceptions.NotFound("Product not found.")
        self.check_object_permissions(request, product)
        try:
            ProductService().detach_topping(product_id=pk, topping_id=topping_id)
        except ToppingNotFoundError as exc:
            raise exceptions.NotFound("Topping is not attached to this product.") from exc
        return Response(status=204)


class ProductAllergensView(APIView):
    """calls ProductService.allergens_for -- see apps/products/services/product_service.py.
    Public (AllowAny), read-only -- allergen data is safety-relevant customer information,
    not a staff-managed field in its own right (allergens are set via Product/Topping's own
    create/update payloads, see `allergen_ids` on their write serializers)."""

    permission_classes = [AllowAny]

    def get(self, request, version, pk):
        try:
            allergens = ProductService().allergens_for(pk)
        except ProductNotFoundError as exc:
            raise exceptions.NotFound("Product not found.") from exc
        return Response(AllergenSerializer(allergens, many=True).data)


class PriceQuoteView(APIView):
    """calls PricingService.quote -- see apps/products/services/pricing_service.py. Public
    (AllowAny): a customer needs to see the price of a build before being forced to log in,
    same visibility as the rest of the public menu-browsing surface. This is what Phase
    11's cart/checkout will call, named explicitly in Issue #181's Implementation Prompt."""

    permission_classes = [AllowAny]

    def post(self, request, version, pk):
        if ProductService().get_by_id(pk) is None:
            raise exceptions.NotFound("Product not found.")

        serializer = PriceQuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        other_half = validated.pop("other_half", None)
        quantity = validated.pop("quantity")

        try:
            if other_half is not None:
                price = PricingService().quote(
                    half_and_half=(
                        {
                            "product_id": pk,
                            "option_choice_ids": validated["option_choice_ids"],
                            "topping_ids": validated["topping_ids"],
                        },
                        other_half,
                    ),
                    quantity=quantity,
                )
            else:
                price = PricingService().quote(
                    product_id=pk,
                    option_choice_ids=validated["option_choice_ids"],
                    topping_ids=validated["topping_ids"],
                    quantity=quantity,
                )
        except InvalidPriceQuoteError as exc:
            # A fixed, generic message -- never the raw exception text (CodeQL: "information
            # exposure through an exception") -- consistent with every other translated
            # domain error in this file, none of which forward `str(exc)` to the client.
            raise exceptions.ValidationError(
                {"non_field_errors": "Invalid price quote selection."}
            ) from exc
        return Response(PriceQuoteResponseSerializer({"price": price}).data)


class ToppingListCreateView(_PlatformCatalogScoped, APIView):
    """calls CatalogService -- see apps/products/services/catalog_service.py. Read is
    public; write requires an unscoped `products.edit` grant (see `_PlatformCatalogScoped`)."""

    required_permission = "products.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version):
        return Response(ToppingSerializer(CatalogService().list_toppings(), many=True).data)

    def post(self, request, version):
        self.check_object_permissions(request, None)
        serializer = ToppingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            topping = CatalogService().create_topping(**serializer.validated_data)
        except AllergenNotFoundError as exc:
            raise exceptions.ValidationError(
                {"allergen_ids": "One or more allergens not found."}
            ) from exc
        return Response(ToppingSerializer(topping).data, status=201)


class ToppingDetailView(_PlatformCatalogScoped, APIView):
    """calls CatalogService -- see apps/products/services/catalog_service.py."""

    required_permission = "products.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk):
        topping = CatalogService().get_topping(pk)
        if topping is None:
            raise exceptions.NotFound("Topping not found.")
        return Response(ToppingSerializer(topping).data)

    def patch(self, request, version, pk):
        self.check_object_permissions(request, None)
        serializer = ToppingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = CatalogService().update_topping(pk, **serializer.validated_data)
        except ToppingNotFoundError as exc:
            raise exceptions.NotFound("Topping not found.") from exc
        except AllergenNotFoundError as exc:
            raise exceptions.ValidationError(
                {"allergen_ids": "One or more allergens not found."}
            ) from exc
        return Response(ToppingSerializer(updated).data)

    def delete(self, request, version, pk):
        self.check_object_permissions(request, None)
        try:
            CatalogService().delete_topping(pk)
        except ToppingNotFoundError as exc:
            raise exceptions.NotFound("Topping not found.") from exc
        return Response(status=204)


class AllergenListCreateView(_PlatformCatalogScoped, APIView):
    """calls CatalogService -- see apps/products/services/catalog_service.py."""

    required_permission = "products.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version):
        return Response(AllergenSerializer(CatalogService().list_allergens(), many=True).data)

    def post(self, request, version):
        self.check_object_permissions(request, None)
        serializer = AllergenCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allergen = CatalogService().create_allergen(**serializer.validated_data)
        return Response(AllergenSerializer(allergen).data, status=201)


class AllergenDetailView(_PlatformCatalogScoped, APIView):
    """calls CatalogService -- see apps/products/services/catalog_service.py."""

    required_permission = "products.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk):
        allergen = CatalogService().get_allergen(pk)
        if allergen is None:
            raise exceptions.NotFound("Allergen not found.")
        return Response(AllergenSerializer(allergen).data)

    def delete(self, request, version, pk):
        self.check_object_permissions(request, None)
        try:
            CatalogService().delete_allergen(pk)
        except AllergenNotFoundError as exc:
            raise exceptions.NotFound("Allergen not found.") from exc
        return Response(status=204)
