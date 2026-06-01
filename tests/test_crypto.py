"""
Penélope — Tests: Crypto Utilities
Validates hashing, salt generation, and session token functions.
"""

import pytest

from penelope.utils.crypto import (
    generate_salt,
    hash_passphrase,
    verify_passphrase,
    generate_session_token,
    generate_device_id,
)


class TestSaltGeneration:
    """Salt generation tests."""

    def test_salt_default_length(self):
        salt = generate_salt()
        assert len(salt) == 64  # 32 bytes → 64 hex chars

    def test_salt_custom_length(self):
        salt = generate_salt(length=16)
        assert len(salt) == 32  # 16 bytes → 32 hex chars

    def test_salt_is_unique(self):
        s1 = generate_salt()
        s2 = generate_salt()
        assert s1 != s2

    def test_salt_is_hex(self):
        salt = generate_salt()
        int(salt, 16)  # should not raise


class TestHashPassphrase:
    """Passphrase hashing tests."""

    def test_hash_deterministic(self):
        salt = "fixed_salt"
        h1 = hash_passphrase("minha senha", salt)
        h2 = hash_passphrase("minha senha", salt)
        assert h1 == h2

    def test_hash_is_hex(self):
        h = hash_passphrase("test", "salt")
        assert len(h) == 64  # SHA-256 output
        int(h, 16)

    def test_hash_case_insensitive(self):
        salt = "salt"
        h1 = hash_passphrase("Minha Senha", salt)
        h2 = hash_passphrase("minha senha", salt)
        assert h1 == h2

    def test_hash_strips_whitespace(self):
        salt = "salt"
        h1 = hash_passphrase("  senha  ", salt)
        h2 = hash_passphrase("senha", salt)
        assert h1 == h2

    def test_different_salts_different_hashes(self):
        h1 = hash_passphrase("same", "salt1")
        h2 = hash_passphrase("same", "salt2")
        assert h1 != h2

    def test_different_passphrases_different_hashes(self):
        salt = "salt"
        h1 = hash_passphrase("alpha", salt)
        h2 = hash_passphrase("beta", salt)
        assert h1 != h2


class TestVerifyPassphrase:
    """Passphrase verification tests."""

    def test_verify_correct(self):
        salt = generate_salt()
        h = hash_passphrase("minha frase", salt)
        assert verify_passphrase("minha frase", salt, h) is True

    def test_verify_wrong(self):
        salt = generate_salt()
        h = hash_passphrase("correta", salt)
        assert verify_passphrase("errada", salt, h) is False

    def test_verify_case_insensitive(self):
        salt = generate_salt()
        h = hash_passphrase("Frase Certa", salt)
        assert verify_passphrase("frase certa", salt, h) is True


class TestSessionToken:
    """Session token generation."""

    def test_token_not_empty(self):
        token = generate_session_token()
        assert len(token) > 0

    def test_tokens_are_unique(self):
        t1 = generate_session_token()
        t2 = generate_session_token()
        assert t1 != t2

    def test_token_is_url_safe(self):
        token = generate_session_token()
        # URL-safe base64 only contains these characters
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', token)


class TestDeviceId:
    """Device ID generation."""

    def test_device_id_length(self):
        did = generate_device_id()
        assert len(did) == 24

    def test_device_ids_unique(self):
        d1 = generate_device_id()
        d2 = generate_device_id()
        assert d1 != d2
