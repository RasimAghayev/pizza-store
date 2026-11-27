from datetime import time

from apps.menu.models import MenuItem


class MenuItemRepository:
    def create(
        self,
        *,
        branch_id: int,
        product_id: int,
        category_id: int,
        is_available: bool = True,
        available_from: time | None = None,
        available_until: time | None = None,
        display_order: int = 0,
    ) -> MenuItem:
        return MenuItem.objects.create(
            branch_id=branch_id,
            product_id=product_id,
            category_id=category_id,
            is_available=is_available,
            available_from=available_from,
            available_until=available_until,
            display_order=display_order,
        )

    def get_by_id(self, menu_item_id: int) -> MenuItem | None:
        return MenuItem.objects.filter(pk=menu_item_id).first()

    def all_for_branch(self, branch_id: int) -> list[MenuItem]:
        return list(MenuItem.objects.filter(branch_id=branch_id))

    def exists_for_branch_and_product(self, branch_id: int, product_id: int) -> bool:
        return MenuItem.objects.filter(branch_id=branch_id, product_id=product_id).exists()

    def update(self, menu_item: MenuItem, **fields: object) -> MenuItem:
        for name, value in fields.items():
            setattr(menu_item, name, value)
        menu_item.save(update_fields=list(fields.keys()))
        return menu_item

    def delete(self, menu_item: MenuItem) -> None:
        menu_item.delete()
