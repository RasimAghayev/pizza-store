#!/usr/bin/env python3
"""RS256 JWT signing keypair generator (ADR 0006, Issue #129).

Writes a PEM-encoded, unencrypted RSA private key -- unencrypted because the Compose
secrets-file mount (0444, root-owned inside the container) is the protection boundary, the
same convention every other Compose secret in this repository already follows. The public
key is never stored separately; backend/apps/identity derives it at process start via
`private_key.public_key()`.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

DEFAULT_OUTPUT = Path("infrastructure/compose/secrets/jwt_private_key.txt")
KEY_SIZE = 2048


def generate_pem_private_key() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite --output if it already exists (refuses by default to avoid "
        "silently invalidating every refresh token signed under the current key).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.output.exists() and not args.force:
        print(f"{args.output} already exists; pass --force to overwrite.")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(generate_pem_private_key())
    print(f"Wrote a new RS256 private key to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
