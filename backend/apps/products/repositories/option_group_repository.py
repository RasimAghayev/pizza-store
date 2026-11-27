from apps.products.models import OptionGroup


class OptionGroupRepository:
    def create(
        self, *, product_id: int, kind: str, is_required: bool = True, allows_multiple: bool = False
    ) -> OptionGroup:
        return OptionGroup.objects.create(
            product_id=product_id,
            kind=kind,
            is_required=is_required,
            allows_multiple=allows_multiple,
        )

    def get_by_id(self, option_group_id: int) -> OptionGroup | None:
        return OptionGroup.objects.filter(pk=option_group_id).first()

    def all_for_product(self, product_id: int):
        return list(OptionGroup.objects.filter(product_id=product_id))

    def delete(self, option_group: OptionGroup) -> None:
        option_group.delete()
