import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User


SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def seed_admin(db: AsyncSession) -> None:
    """Create default admin user if not exists."""
    existing = await get_user_by_username(db, "admin")
    if existing:
        # Make sure existing admin has admin role
        if existing.role != "admin":
            existing.role = "admin"
            existing.status = "active"
            await db.commit()
        return
    admin = User(
        id=uuid.uuid4(),
        username="admin",
        password_hash=hash_password("123456"),
        role="admin",
        status="active",
        is_active=True,
        full_name="超级管理员",
    )
    db.add(admin)
    await db.commit()


async def log_user_activity(
    db: AsyncSession,
    user_id: uuid.UUID,
    action: str,
    target: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
) -> None:
    """Append an activity log entry. Best-effort, swallow errors."""
    try:
        from app.models.user import UserActivityLog
        log = UserActivityLog(
            user_id=user_id,
            action=action,
            target=target,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(log)
        await db.commit()
    except Exception:
        await db.rollback()
