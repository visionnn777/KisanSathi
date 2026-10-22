"""Small, dependency-free helpers for farmer ownership PINs.

PINs are never stored in plaintext. This is a hackathon-grade shared-secret mechanism,
not a substitute for phone OTP verification or a full identity system.
"""
from __future__ import annotations

import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16


def hash_owner_pin(pin: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_owner_pin(pin: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algorithm, iterations_text, salt_hex, expected_hex = stored.split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        if len(salt) < 16 or len(expected) != 32:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


_COMMON_PINS = {
    "password", "passw0rd", "password1", "qwertyui", "qwerty12", "qwerty123", "iloveyou",
    "abcd1234", "abc12345", "12341234", "11112222", "12121212", "11223344", "kisan123",
    "kisan1234", "farmer12", "farmer123", "admin123", "letmein1", "00000000", "india123",
}


def _is_run(text: str) -> bool:
    """True for 12345678, 87654321, abcdefgh and similar straight runs."""
    if len(text) < 4:
        return False
    steps = {ord(b) - ord(a) for a, b in zip(text, text[1:])}
    return steps in ({1}, {-1})


def pin_problem(pin: str, phone: str | None = None) -> str | None:
    """Return a reason if a farmer PIN is too easy to guess, otherwise None."""
    value = (pin or "").strip()
    lowered = value.lower()
    if len(set(lowered)) < 3:
        return "Choose a PIN with at least 3 different characters."
    if lowered in _COMMON_PINS or _is_run(lowered):
        return "This PIN is too easy to guess. Avoid 12345678, abcdefgh or common words."
    digits = "".join(ch for ch in value if ch.isdigit())
    if phone and len(digits) >= 6 and digits in phone:
        return "Do not use your mobile number as the PIN."
    return None
