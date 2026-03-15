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
# Configure passlib to skip bcrypt bug detection (workaround for passlib/bcrypt compatibility issue)
import os
os.environ['PASSLIB_BUG_DETECT_2G'] = '0'

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b"  # Use bcrypt identify 2b
)

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
    """Verify password against hash - truncate to 72 bytes for bcrypt compatibility"""
    # bcrypt has a 72-byte limit
    password_bytes = plain_password.encode('utf-8')[:72]
    return pwd_context.verify(password_bytes.decode('utf-8', errors='ignore'), hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password - truncate to 72 bytes for bcrypt compatibility"""
    # bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = password.encode('utf-8')[:72]
    return pwd_context.hash(password_bytes.decode('utf-8', errors='ignore'))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    import time
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.auth.access_token_expire_hours)

    # Use integer timestamp for exp claim (required by JWT spec)
    to_encode.update({"exp": int(time.time()) + settings.auth.access_token_expire_hours * 3600})
    encoded_jwt = jwt.encode(to_encode, settings.auth.secret_key, algorithm=settings.auth.algorithm)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, settings.auth.secret_key, algorithms=[settings.auth.algorithm])
        return payload
    except JWTError as e:
        logger.warning(f"[auth] JWT decode failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"[auth] JWT decode error: {e}")
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

    # Check and create user sandbox if not exists
    from src.api.sandboxes import load_sandboxes
    sandboxes = load_sandboxes()
    user_sandbox = None

    for sb in sandboxes.values():
        if sb.get("user_id") == user_data["id"]:
            user_sandbox = sb
            break

    if not user_sandbox:
        # Auto-create sandbox for user
        try:
            from src.services.sandbox_service import get_sandbox_service
            import uuid
            service = get_sandbox_service()
            info = service.create_sandbox(
                sandbox_id=str(uuid.uuid4()),
                user_id=user_data["id"],
                name=user_data["username"],
                username=user_data["username"]
            )
            user_sandbox = info.to_dict()
            logger.info(f"[auth] Auto-created sandbox for user: {user.username}")
        except Exception as e:
            logger.warning(f"[auth] Failed to create sandbox for user {user.username}: {e}")

    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user_data["id"],
            username=user_data["username"],
            created_at=user_data["created_at"]
        )
    )


@router.get("/auth/me")
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """Get current user info - wrapped in {user: ...} for frontend compatibility"""
    return {"user": current_user}


@router.post("/auth/logout")
async def logout(current_user: UserResponse = Depends(get_current_user)):
    """Logout (client should discard token)"""
    return {"message": "Logged out successfully"}


@router.get("/auth/status")
async def auth_status():
    """Check auth status"""
    return {"status": "ok", "needsSetup": False}


# ============ User Endpoints (for claudecodeui compatibility) ============

@router.get("/user/onboarding-status")
async def get_onboarding_status(current_user: UserResponse = Depends(get_current_user)):
    """Get user onboarding status"""
    return {"hasCompletedOnboarding": True}


@router.post("/user/complete-onboarding")
async def complete_onboarding(current_user: UserResponse = Depends(get_current_user)):
    """Mark onboarding as complete"""
    return {"hasCompletedOnboarding": True}


@router.get("/user/git-config")
async def get_git_config(current_user: UserResponse = Depends(get_current_user)):
    """Get user git config (placeholder)"""
    return {"name": "", "email": "", "username": ""}


@router.post("/user/git-config")
async def set_git_config(current_user: UserResponse = Depends(get_current_user)):
    """Set user git config (placeholder)"""
    return {"name": "", "email": "", "username": ""}


# ============ MCP Utils Endpoints (for claudecodeui compatibility) ============

@router.get("/mcp-utils/taskmaster-server")
async def get_taskmaster_status(current_user: UserResponse = Depends(get_current_user)):
    """Get TaskMaster MCP server status (placeholder)"""
    return {"installed": False, "running": False}


@router.get("/taskmaster/installation-status")
async def get_taskmaster_installation_status():
    """Get TaskMaster installation status (no auth required)"""
    return {"installed": False}
