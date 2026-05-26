"""
Penélope — Cryptographic Utilities
SHA-256 hashing, salt generation, session tokens.
"""

import hashlib
import os
import secrets
import time
from typing import Tuple


def generate_salt(length: int = 32) -> str:
    """
    Generate a cryptographically secure random salt.

    Args:
        length: Number of random bytes (hex-encoded, so output is 2x length).

    Returns:
        Hex-encoded salt string.
    """
    return os.urandom(length).hex()


def hash_passphrase(passphrase: str, salt: str) -> str:
    """
    Hash a passphrase using SHA-256 with a salt.

    The passphrase is normalized (stripped and lowercased) before hashing
    to allow for minor variations in speech-to-text output.

    Args:
        passphrase: The spoken passphrase (plain text).
        salt: Hex-encoded salt string.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    normalized = passphrase.strip().lower()
    salted = f"{salt}:{normalized}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def verify_passphrase(passphrase: str, salt: str, stored_hash: str) -> bool:
    """
    Verify a passphrase against a stored hash.

    Args:
        passphrase: The spoken passphrase to verify.
        salt: The salt used during original hashing.
        stored_hash: The stored hash to compare against.

    Returns:
        True if the passphrase matches, False otherwise.
    """
    computed_hash = hash_passphrase(passphrase, salt)
    # Constant-time comparison to prevent timing attacks
    return secrets.compare_digest(computed_hash, stored_hash)


def generate_session_token(length: int = 48) -> str:
    """
    Generate a cryptographically secure session token.

    Args:
        length: Number of random bytes for the token.

    Returns:
        URL-safe base64-encoded token string.
    """
    return secrets.token_urlsafe(length)


def generate_device_id() -> str:
    """
    Generate a unique device identifier.

    Returns:
        A unique hex string based on random bytes and timestamp.
    """
    raw = f"{secrets.token_hex(16)}:{time.time_ns()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
