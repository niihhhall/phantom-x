import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.config import settings
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)
from app.core.database import get_db_client

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    workspace_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    client = get_db_client()
    
    # 1. Check if user already exists
    check_user = await client.table("users").select("*").eq("email", body.email).execute()
    if check_user.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
        
    # 2. Create Workspace
    workspace_res = await client.table("workspaces").insert({
        "name": body.workspace_name,
        "plan": "starter"
    }).execute()
    
    if not workspace_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace"
        )
    workspace = workspace_res.data[0]
    
    # 3. Create User with role='owner'
    password_hash = hash_password(body.password)
    user_res = await client.table("users").insert({
        "workspace_id": workspace["id"],
        "email": body.email,
        "password_hash": password_hash,
        "role": "owner"
    }).execute()
    
    if not user_res.data:
        # Rollback workspace if user creation failed
        await client.table("workspaces").delete().eq("id", workspace["id"]).execute()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    user = user_res.data[0]
    
    # 4. Set Workspace owner_id
    await client.table("workspaces").update({
        "owner_id": user["id"]
    }).eq("id", workspace["id"]).execute()
    
    # 5. Generate Access Token
    token_data = {
        "sub": user["id"],
        "workspace_id": workspace["id"],
        "role": "owner",
        "email": user["email"]
    }
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "workspace_id": workspace["id"],
            "role": "owner"
        }
    }

@router.post("/login")
async def login(body: LoginRequest):
    client = get_db_client()
    
    # 1. Fetch user by email
    user_res = await client.table("users").select("*").eq("email", body.email).execute()
    if not user_res.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    user = user_res.data[0]
    
    # 2. Verify password
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
        
    # 3. Generate Access Token
    token_data = {
        "sub": user["id"],
        "workspace_id": user["workspace_id"],
        "role": user["role"],
        "email": user["email"]
    }
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "workspace_id": user["workspace_id"],
            "role": user["role"]
        }
    }

@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
