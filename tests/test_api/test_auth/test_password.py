"""
Tests: Password hashing and verification — hash_password, verify_password
Covers UT-16 ~ UT-23
"""

import pytest
from ai_novels.api.auth.password import hash_password, verify_password


class TestHashPassword:
    def test_normal_hashing(self):
        h = hash_password("TestPass123")
        assert isinstance(h, str)
        assert len(h) == 60
        assert h.startswith("$2b$")

    def test_empty_password(self):
        with pytest.raises(ValueError, match="at least 6"):
            hash_password("")

    def test_too_short(self):
        with pytest.raises(ValueError, match="at least 6"):
            hash_password("ab")

    def test_too_long(self):
        with pytest.raises(ValueError, match="at most 128"):
            hash_password("a" * 129)

    def test_unicode_password(self):
        h = hash_password("密码123!@#")
        assert h.startswith("$2b$")
        assert verify_password("密码123!@#", h) is True

    def test_different_salts(self):
        h1 = hash_password("SamePass")
        h2 = hash_password("SamePass")
        assert h1 != h2  # bcrypt gensalt ensures different hashes

    def test_special_characters(self):
        h = hash_password("P@$$w0rd!\"'[]{}|\\")
        assert verify_password("P@$$w0rd!\"'[]{}|\\", h) is True

    def test_numeric_password(self):
        h = hash_password("1234567890")
        assert verify_password("1234567890", h) is True


class TestVerifyPassword:
    def test_matching(self):
        h = hash_password("ValidPass1")
        assert verify_password("ValidPass1", h) is True

    def test_not_matching(self):
        h = hash_password("RealPass1")
        assert verify_password("WrongPass", h) is False

    def test_empty_password_arg(self):
        h = hash_password("RealPass1")
        assert verify_password("", h) is False

    def test_empty_hash_arg(self):
        assert verify_password("RealPass1", "") is False

    def test_both_empty(self):
        assert verify_password("", "") is False

    def test_invalid_hash_format(self):
        assert verify_password("pass", "not-a-bcrypt-hash") is False

    def test_none_as_hash(self):
        assert verify_password("pass", None) is False  # type: ignore

    def test_integer_input(self):
        assert verify_password(12345, "hash") is False  # type: ignore
