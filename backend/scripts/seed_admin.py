"""Create the first admin user from BOOTSTRAP_ADMIN_* env vars.

Idempotent — run every deploy. If the admin already exists it does nothing
unless RESET_ADMIN_PASSWORD=1, in which case the password is refreshed.
"""

import os
import sys

# Allow running as `python -m scripts.seed_admin` from /app.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.auth import hash_password  # noqa: E402
from api.config import settings  # noqa: E402
from api.database import SessionLocal, engine  # noqa: E402
from api.db_models import Base, User, UserRoleEnum  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)

    username = settings.BOOTSTRAP_ADMIN_USER
    password = settings.BOOTSTRAP_ADMIN_PASSWORD
    if not password:
        print("BOOTSTRAP_ADMIN_PASSWORD is empty — skipping admin seed.")
        return

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if user:
            if os.getenv("RESET_ADMIN_PASSWORD") == "1":
                user.password_hash = hash_password(password)
                db.commit()
                print(f"Reset password for existing admin {username}.")
            else:
                print(f"Admin {username} already exists — nothing to do.")
            return

        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=UserRoleEnum.ADMIN,
                is_active=True,
            )
        )
        db.commit()
        print(f"Created admin {username}.")


if __name__ == "__main__":
    main()
