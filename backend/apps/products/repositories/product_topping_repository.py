from apps.products.models import ProductTopping


class ProductToppingRepository:
    def attach(
        self, *, product_id: int, topping_id: int, is_default_included: bool = False
    ) -> ProductTopping:
        """Attaching an already-attached topping updates its `is_default_included` flag
        instead of raising the unique-constraint IntegrityError -- see model docstring."""
        product_topping, _ = ProductTopping.objects.update_or_create(
            product_id=product_id,
            topping_id=topping_id,
            defaults={"is_default_included": is_default_included},
        )
        return product_topping

    def get(self, *, product_id: int, topping_id: int) -> ProductTopping | None:
        return ProductTopping.objects.filter(product_id=product_id, topping_id=topping_id).first()

    def all_for_product(self, product_id: int):
        return list(ProductTopping.objects.filter(product_id=product_id).select_related("topping"))

    def detach(self, product_topping: ProductTopping) -> None:
        product_topping.delete()
