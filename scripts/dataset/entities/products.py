from __future__ import annotations

from typing import Any

from .config import Context

NON_PIZZA_CATEGORIES = ["drink", "side", "dessert"]
PIZZA_SIZES = ["SMALL", "MEDIUM", "LARGE", "XL"]
PIZZA_CRUSTS = ["THIN", "CLASSIC", "STUFFED", "GLUTEN_FREE"]
PIZZA_TOPPINGS = [
    "Margherita",
    "Pepperoni",
    "BBQ Chicken",
    "Four Cheese",
    "Veggie Supreme",
    "Hawaiian",
    "Meat Feast",
    "Mushroom Truffle",
    "Spicy Diavola",
    "Mediterranean",
]

PRICE_RANGE_MINOR = {
    "drink": (200, 800),
    "side": (400, 1200),
    "dessert": (500, 1400),
    "pizza_variant": (1200, 3500),
}


def generate_products(ctx: Context) -> list[dict[str, Any]]:
    rng = ctx.random
    products: list[dict[str, Any]] = []
    product_id = 1

    non_pizza_count = ctx.config.product_count
    for _ in range(non_pizza_count):
        category = rng.choice(NON_PIZZA_CATEGORIES)
        low, high = PRICE_RANGE_MINOR[category]
        products.append(
            {
                "product_id": product_id,
                "category": category,
                "name": ctx.faker.unique.word().capitalize() + f" {category}",
                "base_price_minor": rng.randrange(low, high, 50),
                "is_active": True,
            }
        )
        product_id += 1

    for _ in range(ctx.config.pizza_variant_count):
        low, high = PRICE_RANGE_MINOR["pizza_variant"]
        topping = rng.choice(PIZZA_TOPPINGS)
        size = rng.choice(PIZZA_SIZES)
        crust = rng.choice(PIZZA_CRUSTS)
        products.append(
            {
                "product_id": product_id,
                "category": "pizza_variant",
                "name": f"{topping} ({size}, {crust.replace('_', ' ').title()} crust)",
                "size": size,
                "crust": crust,
                "base_price_minor": rng.randrange(low, high, 50),
                "is_active": True,
            }
        )
        product_id += 1

    return products
