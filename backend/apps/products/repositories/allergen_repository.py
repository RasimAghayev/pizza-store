from apps.products.models import Allergen


class AllergenRepository:
    def create(self, *, name: str) -> Allergen:
        return Allergen.objects.create(name=name)

    def get_by_id(self, allergen_id: int) -> Allergen | None:
        return Allergen.objects.filter(pk=allergen_id).first()

    def all(self):
        return list(Allergen.objects.all())

    def filter_by_ids(self, allergen_ids) -> list[Allergen]:
        return list(Allergen.objects.filter(pk__in=allergen_ids))

    def set_for_product(self, product, allergen_ids) -> None:
        product.allergens.set(allergen_ids)

    def set_for_topping(self, topping, allergen_ids) -> None:
        topping.allergens.set(allergen_ids)

    def for_product_union_default_toppings(self, product) -> list[Allergen]:
        """A product's allergen list unions its own allergens and its *default-included*
        toppings' allergens only -- Issue #181's Test Requirement wording is deliberately
        narrower than "all attached toppings": an optional add-on topping's allergen is
        the customer's own choice to add, so it is excluded from the product's own
        allergen profile."""
        default_topping_ids = product.product_toppings.filter(is_default_included=True).values_list(
            "topping_id", flat=True
        )
        own = set(product.allergens.all())
        from_toppings = set(Allergen.objects.filter(toppings__id__in=default_topping_ids))
        return sorted(own | from_toppings, key=lambda allergen: allergen.name)

    def delete(self, allergen: Allergen) -> None:
        allergen.delete()
