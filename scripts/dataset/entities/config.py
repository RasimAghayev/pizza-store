from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from faker import Faker

# Fixed, not datetime.now(): the dataset window's end must never drift between runs,
# or the same --seed would stop producing byte-identical output on a different day.
WINDOW_END = datetime(2026, 11, 26, tzinfo=timezone.utc)
WINDOW_MONTHS = 24
WINDOW_START = WINDOW_END.replace(year=WINDOW_END.year - 2)

DEFAULT_SEED = 20261126


@dataclass(frozen=True)
class DatasetConfig:
    seed: int
    branch_count: int
    product_count: int
    pizza_variant_count: int
    staff_count: int
    courier_count: int
    customer_count: int
    order_count: int

    @property
    def window_start(self) -> datetime:
        return WINDOW_START

    @property
    def window_end(self) -> datetime:
        return WINDOW_END

    @property
    def window_days(self) -> int:
        return (self.window_end - self.window_start).days


def smoke_config(seed: int = DEFAULT_SEED) -> DatasetConfig:
    return DatasetConfig(
        seed=seed,
        branch_count=2,
        product_count=20,
        pizza_variant_count=6,
        staff_count=10,
        courier_count=6,
        customer_count=200,
        order_count=500,
    )


def full_config(seed: int = DEFAULT_SEED) -> DatasetConfig:
    """Meets/exceeds every master-prompt §10 volume threshold with headroom."""
    return DatasetConfig(
        seed=seed,
        branch_count=10,
        product_count=110,
        pizza_variant_count=32,
        staff_count=110,
        courier_count=55,
        customer_count=20_500,
        order_count=101_000,
    )


SCALE_PRESETS = {
    "smoke": smoke_config,
    "full": full_config,
}


class Context:
    """Shared RNG + Faker instance, seeded once and threaded through every generator
    so the same --seed always produces the same sequence of calls in the same order."""

    def __init__(self, config: DatasetConfig) -> None:
        self.config = config
        self.random = random.Random(config.seed)
        self.faker = Faker()
        self.faker.seed_instance(config.seed)
