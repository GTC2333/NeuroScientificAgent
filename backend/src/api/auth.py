"""
Auth API - User registration, login, JWT tokens
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger("MAS.Auth")
router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()


# ============ Models ============

class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ============ Database Helpers ============

def get_db_path() -> Path:
    """Get path to users database"""
    return Path(__file__).parent.parent.parent / "data" / "users.json"


def load_users() -> dict:
    """Load users from JSON file"""
    db_path = get_db_path()
    if not db_path.exists():
        return {}
    with open(db_path, "r") as f:
        return json.load(f)


def save_users(users: dict):
    """Save users to JSON file"""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, "w") as f:
        json.dump(users, f, indent=2)


# ============ Auth Helpers ============

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.access_token_expire_hours)

    to_encode.update({"exp": expire.isoformat()})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserResponse:
    """Get current authenticated user from token"""
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    users = load_users()
    user_data = users.get(username)
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return UserResponse(
        id=user_data["id"],
        username=user_data["username"],
        created_at=user_data["created_at"]
    )


# ============ Routes ============

@router.post("/auth/register", response_model=TokenResponse)
async def register(user: UserCreate):
    """Register a new user"""
    import uuid

    users = load_users()

    # Check if user exists
    if user.username in users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Create user
    user_id = str(uuid.uuid4())
    users[user.username] = {
        "id": user_id,
        "username": user.username,
        "password_hash": get_password_hash(user.password),
        "created_at": datetime.utcnow().isoformat()
    }

    save_users(users)

    # Create token
    access_token = create_access_token(data={"sub": user.username})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user_id,
            username=user.username,
            created_at=users[user.username]["created_at"]
        )
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(user: UserLogin):
    """Login and get access token"""
    users = load_users()

    # Find user
    user_data = users.get(user.username)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # Verify password
    if not verify_password(user.password, user_data["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # Create token
    access_token = create_access_token(data={"sub": user.username})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user_data["id"],
            username=user_data["username"],
            created_at=user_data["created_at"]
        )
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user info"""
    return current_user


@router.post("/auth/logout")
async def logout(current_user: UserResponse = Depends(get_current_user)):
    """Logout (client should discard token)"""
    return {"message": "Logged out successfully"}


@router.get("/auth/status")
async def auth_status():
    """Check auth status"""
    return {"status": "ok", "needsSetup": False}
