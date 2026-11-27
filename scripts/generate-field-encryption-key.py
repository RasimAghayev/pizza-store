#!/usr/bin/env python3
"""Fernet field-level encryption key generator (ADR 0006, Issue #179).

Writes a raw Fernet key (32 url-safe base64-encoded bytes) -- unencrypted because the Compose
secrets-file mount (0444, root-owned inside the container) is the protection boundary, the
same convention every other Compose secret in this repository already follows.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.fernet import Fernet

DEFAULT_OUTPUT = Path("infrastructure/compose/secrets/field_encryption_key.txt")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite --output if it already exists (refuses by default to avoid "
        "silently making every previously-encrypted row unreadable).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.output.exists() and not args.force:
        print(f"{args.output} already exists; pass --force to overwrite.")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(Fernet.generate_key())
    print(f"Wrote a new field-encryption key to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
