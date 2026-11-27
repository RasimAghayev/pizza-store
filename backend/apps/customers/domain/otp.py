import hashlib
import secrets

CODE_LENGTH = 6

# Matches docs/database/redis-caching-and-ttl-policy.md's `otp:{purpose}:{identifier}` row --
# Redis's TTL is the enforcement mechanism for expiry, not just an optimization.
OTP_TTL_SECONDS = 5 * 60


def generate_otp_code() -> str:
    """Cryptographically random, zero-padded 6-digit code -- no Django import, per
    ADR 0004's domain-layer isolation."""
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


def hash_otp_code(code: str) -> str:
    """Only this hash is ever persisted in Redis, same rationale as
    apps/identity/services/token_service.py's refresh-token hashing -- a Redis dump or log
    leak never exposes a usable code."""
    return hashlib.sha256(code.encode()).hexdigest()
