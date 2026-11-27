from apps.menu.models import MenuCategory


class MenuCategoryRepository:
    def create(self, *, organization_id: int, name: str, display_order: int = 0) -> MenuCategory:
        return MenuCategory.objects.create(
            organization_id=organization_id, name=name, display_order=display_order
        )

    def get_by_id(self, category_id: int) -> MenuCategory | None:
        return MenuCategory.objects.filter(pk=category_id).first()

    def all_for_organization(self, organization_id: int) -> list[MenuCategory]:
        return list(MenuCategory.objects.filter(organization_id=organization_id))

    def update(self, category: MenuCategory, **fields: object) -> MenuCategory:
        for name, value in fields.items():
            setattr(category, name, value)
        category.save(update_fields=list(fields.keys()))
        return category

    def delete(self, category: MenuCategory) -> None:
        category.delete()
