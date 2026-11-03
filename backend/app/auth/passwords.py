"""bcrypt password hashing. Passwords and hashes are never logged."""
from __future__ import annotations

import bcrypt


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:  # e.g. password longer than 72 bytes, or a malformed hash
        return False