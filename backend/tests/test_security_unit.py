"""Database-free tests of the credential primitives."""

import os

import pytest

PASSWORD = "测试Password!"
PASSWORD_VECTOR = (
    "scrypt$00112233445566778899aabbccddeeff$"
    "19e44eab516f31becb83a0b562aaf7e50b85611dab07359472b43040367c1d8c"
)


@pytest.fixture
def security(monkeypatch):
    if "DATABASE_URL" not in os.environ:
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://127.0.0.1/unused")
    from app import main

    return main


def test_scrypt_password_vector(security):
    assert security.password_matches(PASSWORD, PASSWORD_VECTOR)


def test_scrypt_password_match_is_exact(security):
    assert not security.password_matches(f"{PASSWORD} ", PASSWORD_VECTOR)


def test_session_digest_is_sha256(security):
    assert security.digest("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
