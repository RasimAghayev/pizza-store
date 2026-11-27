from apps.products.models import Topping


class ToppingRepository:
    def create(self, *, name: str, price_delta, sku_reference: str | None = None) -> Topping:
        return Topping.objects.create(
            name=name, price_delta=price_delta, sku_reference=sku_reference
        )

    def get_by_id(self, topping_id: int) -> Topping | None:
        return Topping.objects.filter(pk=topping_id).first()

    def all(self):
        return list(Topping.objects.all())

    def filter_by_ids(self, topping_ids) -> list[Topping]:
        return list(Topping.objects.filter(pk__in=topping_ids))

    def update(self, topping: Topping, **fields) -> Topping:
        for name, value in fields.items():
            setattr(topping, name, value)
        topping.save(update_fields=list(fields.keys()))
        return topping

    def delete(self, topping: Topping) -> None:
        topping.delete()
