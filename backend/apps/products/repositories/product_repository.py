from apps.products.models import Product


class ProductRepository:
    def create(
        self,
        *,
        organization_id: int,
        name: str,
        description: str,
        base_price,
        is_active: bool = True
    ) -> Product:
        return Product.objects.create(
            organization_id=organization_id,
            name=name,
            description=description,
            base_price=base_price,
            is_active=is_active,
        )

    def get_by_id(self, product_id: int) -> Product | None:
        return Product.objects.filter(pk=product_id).first()

    def all_for_organization(self, organization_id: int):
        return list(Product.objects.filter(organization_id=organization_id))

    def update(self, product: Product, **fields) -> Product:
        for name, value in fields.items():
            setattr(product, name, value)
        product.save(update_fields=list(fields.keys()))
        return product

    def delete(self, product: Product) -> None:
        product.delete()
