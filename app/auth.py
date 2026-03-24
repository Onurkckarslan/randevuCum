import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
import os

SECRET_KEY = os.getenv("SECRET_KEY", "RandevuCum-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30
IS_PRODUCTION = os.getenv("ENVIRONMENT") == "production"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        # hashed parametresi veritabanından geldiği için string'dir
        # bcrypt.checkpw() plain text'i bytes'a, hash'i de bytes'a dönüştürmeyi gerektirir
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def create_token(business_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(business_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_business_id(request: Request) -> int | None:
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except JWTError:
        return None


def require_login(request: Request) -> int:
    biz_id = get_current_business_id(request)
    if not biz_id:
        raise HTTPException(status_code=303, headers={"Location": "/giris"})
    return biz_id

