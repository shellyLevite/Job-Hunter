from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import settings

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory user store (replace with persistent DB in later phases)
_USERS = {}


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=30))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/register", response_model=UserRead)
def register(user: UserCreate):
    if user.email in _USERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    _USERS[user.email] = {
        "email": user.email,
        "hashed_password": _hash_password(user.password),
        "created_at": datetime.utcnow(),
    }

    return {"email": user.email}


@router.post("/login", response_model=Token)
def login(user: UserCreate):
    stored = _USERS.get(user.email)
    if not stored or not _verify_password(user.password, stored["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = _create_access_token({"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
