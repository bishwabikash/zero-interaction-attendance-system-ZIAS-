from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from api.auth import create_access_token, decode_token, hash_password, verify_password
from api.config import settings


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


def _forge(key, algorithm, expires_in):
    exp = datetime.now(timezone.utc) + expires_in
    return jwt.encode({"sub": "alice", "exp": exp}, key, algorithm=algorithm)


@pytest.mark.parametrize(
    "token",
    [
        _forge(settings.JWT_SECRET_KEY, "HS256", timedelta(minutes=-1)),
        _forge("y" * 48, "HS256", timedelta(minutes=5)),
        _forge(None, "none", timedelta(minutes=5)),
    ],
    ids=["expired", "wrong-key", "unsigned-alg-none"],
)
def test_jwt_forged_or_expired_rejected(token):
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401
