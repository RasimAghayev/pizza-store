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


SMOKE_FRACTION = 0.01  # master prompt §10: "a small fixed fraction (e.g. 1%)"
LOAD_MULTIPLIER = 5  # master prompt §10: "a multiple of the integration volumes (e.g. 10x)";
# 5x keeps a full local/PR-evidence run tractable (~10-15 min) while still being clearly
# larger than "integration" for performance/load testing -- it is never run in routine CI.


def _scaled(base: int, fraction: float, floor: int) -> int:
    return max(round(base * fraction), floor)


def integration_config(seed: int = DEFAULT_SEED) -> DatasetConfig:
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


def smoke_config(seed: int = DEFAULT_SEED) -> DatasetConfig:
    """1% of the integration volumes, floored to a handful per entity -- fast enough for
    a local dev loop and for routine CI runs on every PR touching scripts/dataset/**."""
    integration = integration_config(seed=seed)
    return DatasetConfig(
        seed=seed,
        branch_count=_scaled(integration.branch_count, SMOKE_FRACTION, floor=2),
        product_count=_scaled(integration.product_count, SMOKE_FRACTION, floor=10),
        pizza_variant_count=_scaled(integration.pizza_variant_count, SMOKE_FRACTION, floor=4),
        staff_count=_scaled(integration.staff_count, SMOKE_FRACTION, floor=5),
        courier_count=_scaled(integration.courier_count, SMOKE_FRACTION, floor=3),
        customer_count=_scaled(integration.customer_count, SMOKE_FRACTION, floor=50),
        order_count=_scaled(integration.order_count, SMOKE_FRACTION, floor=100),
    )


def load_config(seed: int = DEFAULT_SEED) -> DatasetConfig:
    """A multiple of the integration volumes, for on-demand performance/load testing only
    -- never run as part of routine CI (master prompt §10: "must not overload CI")."""
    integration = integration_config(seed=seed)
    return DatasetConfig(
        seed=seed,
        branch_count=integration.branch_count * LOAD_MULTIPLIER,
        product_count=integration.product_count * LOAD_MULTIPLIER,
        pizza_variant_count=integration.pizza_variant_count * LOAD_MULTIPLIER,
        staff_count=integration.staff_count * LOAD_MULTIPLIER,
        courier_count=integration.courier_count * LOAD_MULTIPLIER,
        customer_count=integration.customer_count * LOAD_MULTIPLIER,
        order_count=integration.order_count * LOAD_MULTIPLIER,
    )


SCALE_PRESETS = {
    "smoke": smoke_config,
    "integration": integration_config,
    "load": load_config,
}


class Context:
    """Shared RNG + Faker instance, seeded once and threaded through every generator
    so the same --seed always produces the same sequence of calls in the same order."""

    def __init__(self, config: DatasetConfig) -> None:
        self.config = config
        self.random = random.Random(config.seed)
        self.faker = Faker()
        self.faker.seed_instance(config.seed)
