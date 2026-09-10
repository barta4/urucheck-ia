import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from config import settings
from database import database

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    if "jti" not in to_encode:
        to_encode["jti"] = uuid.uuid4().hex
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def revoke_token(token: str) -> bool:
    """Add token's jti to revoked_tokens table to prevent reuse"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        exp_ts = payload.get("exp")
        if not jti:
            return False
        expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if exp_ts else datetime.now(timezone.utc) + timedelta(days=1)
        await database.execute(
            """
            INSERT INTO revoked_tokens (jti, expires_at)
            VALUES (:jti, :exp)
            ON CONFLICT (jti) DO NOTHING
            """,
            {"jti": jti, "exp": expires_at}
        )
        return True
    except Exception:
        return False


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        jti: Optional[str] = payload.get("jti")
        if jti:
            revoked = await database.fetch_one(
                "SELECT jti FROM revoked_tokens WHERE jti = :jti",
                {"jti": jti}
            )
            if revoked:
                raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await database.fetch_one(
        """SELECT id, company_id, name, email, role, active,
                  is_super_admin, expo_push_token, device_id
           FROM employees WHERE id = :id AND active = true""",
        {"id": user_id}
    )
    if user is None:
        raise credentials_exception
    return dict(user)

def get_company_id(user: dict) -> str:
    """Extract company_id from user dict (must be attached to JWT or queried)"""
    return user.get("company_id")

async def get_current_admin(current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol administrador")
    return current_user

async def get_current_super_admin(current_user=Depends(get_current_user)):
    if not current_user.get("is_super_admin", False):
        raise HTTPException(status_code=403, detail="Se requiere rol super-administrador de la plataforma")
    return current_user
