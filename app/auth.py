import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
import os

SECRET_KEY = os.getenv("SECRET_KEY", "RandevuCum-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


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

