import datetime
from typing import Annotated, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.config import settings
from app.core.database import get_db_client

import bcrypt
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hashed version."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: datetime.timedelta = None) -> str:
    """Generate JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=int(settings.JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """Decode and verify access token, raising 401 on failure/expiration."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        workspace_id: str = payload.get("workspace_id")
        role: str = payload.get("role")
        if user_id is None or workspace_id is None or role is None:
            raise credentials_exception
        return {"user_id": user_id, "workspace_id": workspace_id, "role": role, "email": payload.get("email")}
    except JWTError:
        raise credentials_exception

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    """Security dependency to fetch the current authenticated user from database."""
    token_data = verify_token(token)
    client = get_db_client()
    
    # Query Supabase users table
    res = await client.table("users").select("*").eq("id", token_data["user_id"]).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = res.data[0]
    return {
        "id": user["id"],
        "email": user["email"],
        "workspace_id": user["workspace_id"],
        "role": user["role"]
    }

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: Annotated[dict, Depends(get_current_user)]):
        if current_user["role"] not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this role"
            )
        return current_user

def require_role(roles: List[str]):
    """Role verification dependency factory."""
    return RoleChecker(roles)

def encrypt_cookie(cookie: str) -> str:
    """Symmetrically encrypt the cookie value using Fernet with JWT_SECRET."""
    import base64
    from cryptography.fernet import Fernet
    # Fernet key must be exactly 32 bytes and base64-encoded
    key_source = settings.JWT_SECRET.encode().ljust(32)[:32]
    key = base64.urlsafe_b64encode(key_source)
    f = Fernet(key)
    return f.encrypt(cookie.encode()).decode()

def decrypt_cookie(encrypted_cookie: str) -> str:
    """Decrypt the cookie value using Fernet."""
    import base64
    from cryptography.fernet import Fernet
    key_source = settings.JWT_SECRET.encode().ljust(32)[:32]
    key = base64.urlsafe_b64encode(key_source)
    f = Fernet(key)
    return f.decrypt(encrypted_cookie.encode()).decode()
