"""JWT auth utilities shared across routes."""

from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from api.config import settings
from api.database import get_db
from api.db_models import User

security = HTTPBearer(auto_error=True)

_BCRYPT_MAX_BYTES = 72


def _prep(password: str) -> bytes:
    # bcrypt silently truncates > 72 bytes; enforce it up-front so a hash and
    # its verify are always over the same bytes.
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prep(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prep(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, extra: Optional[dict] = None) -> str:
    payload = {"sub": subject, "iat": datetime.utcnow()}
    if extra:
        payload.update(extra)
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token subject")

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive or missing")
    return user


def require_role(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if roles and user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permission")
        return user

    return _dep
