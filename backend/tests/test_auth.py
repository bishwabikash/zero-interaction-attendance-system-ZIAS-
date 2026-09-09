import pytest
from fastapi import HTTPException

from api.auth import create_access_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    token = create_access_token("alice", extra={"role": "admin"})
    payload = decode_token(token)
    assert payload["sub"] == "alice"
    assert payload["role"] == "admin"


def test_jwt_invalid_rejected():
    with pytest.raises(HTTPException) as exc:
        decode_token("not-a-real-token")
    assert exc.value.status_code == 401
