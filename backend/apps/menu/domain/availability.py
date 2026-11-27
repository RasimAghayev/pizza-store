from datetime import time


def is_available_at(
    *,
    is_available: bool,
    available_from: time | None,
    available_until: time | None,
    at: time,
) -> bool:
    """Pure, Django-import-free (ADR 0004) -- mirrors
    `apps.branches.domain.opening_hours.is_open_at`'s style. `available_from`/
    `available_until` left null means "no window restriction, always available whenever the
    branch is open"; set, the window is half-open (`available_from` inclusive,
    `available_until` exclusive) and does not wrap past midnight -- an item whose window
    would cross midnight is out of scope for this Task, documented in `README.md` rather than
    silently assumed to wrap."""

    if not is_available:
        return False
    if available_from is None or available_until is None:
        return True
    return available_from <= at < available_until
