from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from supabase import Client

from app.core.config import settings
from app.db import crud
from app.db.session import get_supabase

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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


def get_current_user(
    token: str = Depends(oauth2_scheme),
    client: Client = Depends(get_supabase),
) -> UserRead:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_email(client, email)
    if user is None:
        raise credentials_exception
    return UserRead(email=user["email"])


@router.post("/register", response_model=UserRead)
def register(user: UserCreate, client: Client = Depends(get_supabase)):
    if crud.get_user_by_email(client, user.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed_password = _hash_password(user.password)
    created = crud.create_user(client, email=user.email, hashed_password=hashed_password)
    return {"email": created["email"]}


@router.post("/login", response_model=Token)
def login(user: UserCreate, client: Client = Depends(get_supabase)):
    stored = crud.get_user_by_email(client, user.email)
    if not stored or not _verify_password(user.password, stored["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = _create_access_token({"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
