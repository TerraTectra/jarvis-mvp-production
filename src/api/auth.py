"""Authentication endpoints."""
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from sqlalchemy import select, Table, MetaData
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import (
    verify_password,
    get_password_hash,
    generate_password_reset_token,
    verify_password_reset_token,
    generate_email_verification_token,
    verify_email_token,
)
from src.crud.user import get_user, get_user_by_username, get_user_by_email, create_user, update_user, verify_user_email as verify_user_email_crud
from src.database.session import get_db
from src.models.user import User, Role, user_roles
from src.schemas.user import (
    Token,
    UserCreate,
    UserInDB,
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from src.api.dependencies import get_current_user, oauth2_scheme

router = APIRouter(tags=["auth"])

# Configuration
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

@router.post("/token", response_model=Token)
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 compatible token login, get an access token for future requests."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login time
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Generate tokens
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": form_data.scopes},
        expires_delta=access_token_expires,
    )
    
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        data={"sub": user.username},
        expires_delta=refresh_token_expires,
    )
    
    # Set HTTP-only cookies for better security
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=os.getenv("ENVIRONMENT") == "production",
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="lax",
        secure=os.getenv("ENVIRONMENT") == "production",
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(
            refresh_token,
            os.getenv("SECRET_KEY"),
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
        )
        
        if payload.get("type") != "refresh":
            raise credentials_exception
            
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
            
    except jwt.JWTError:
        raise credentials_exception
    
    user = await get_user(db, username=username)
    if user is None:
        raise credentials_exception
    
    # Generate new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes},
        expires_delta=access_token_expires,
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserResponse)
async def register_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user."""
    try:
        # Check if username or email already exists
        existing_user = await get_user_by_username(db, user_in.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )
        
        existing_email = await get_user_by_email(db, user_in.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Create new user without roles first
        hashed_password = get_password_hash(user_in.password)
        db_user = User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=hashed_password,
            full_name=user_in.full_name,
            is_active=True,
            is_verified=False,
        )
        
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        
        # Get default role
        result = await db.execute(select(Role).filter(Role.is_default == True))
        default_role = result.scalars().first()
        
        if default_role:
            # Add role using the association table directly
            stmt = user_roles.insert().values(user_id=db_user.id, role_id=default_role.id)
            await db.execute(stmt)
            await db.commit()
        
        # Get the user with roles
        db_user = await get_user(db, db_user.id)
        
        # Convert to response model
        response_data = {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "full_name": db_user.full_name,
            "is_active": db_user.is_active,
            "is_verified": db_user.is_verified,
            "created_at": db_user.created_at,
            "updated_at": db_user.updated_at,
            "last_login": db_user.last_login,
            "roles": [role.name for role in db_user.roles] if hasattr(db_user, 'roles') else []
        }
        
        return UserResponse(**response_data)
        
    except HTTPException as he:
        await db.rollback()
        raise he
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )

@router.get("/verify-email/{token}", response_model=dict)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify user's email address."""
    email = verify_email_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    
    user = await get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if user.is_verified:
        return {"message": "Email already verified"}
    
    await verify_user_email_crud(db, user_id=user.id)
    return {"message": "Email successfully verified"}

@router.post("/request-password-reset")
async def request_password_reset(
    email_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request password reset."""
    user = await get_user_by_email(db, email_data.email)
    if user:
        # Generate password reset token
        reset_token = generate_password_reset_token(email_data.email)
        reset_url = f"{os.getenv('FRONTEND_URL')}/reset-password?token={reset_token}"
        
        # TODO: Send password reset email
        print(f"Password reset URL: {reset_url}")
    
    # Always return success to prevent user enumeration
    return {"message": "If your email is registered, you will receive a password reset link"}

@router.post("/reset-password")
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Reset user's password."""
    email = verify_password_reset_token(reset_data.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    
    user = await get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Update password
    user.hashed_password = get_password_hash(reset_data.new_password)
    await db.commit()
    
    return {"message": "Password updated successfully"}

@router.post("/logout")
async def logout(response: Response):
    """Log out the current user by clearing cookies."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Successfully logged out"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_user),
):
    """Get current user information."""
    return current_user

# Helper functions
async def authenticate_user(db: AsyncSession, username: str, password: str):
    """Authenticate a user."""
    user = await get_user(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create an access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    })
    
    return jwt.encode(
        to_encode, 
        os.getenv("SECRET_KEY"),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256")
    )

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    })
    
    return jwt.encode(
        to_encode, 
        os.getenv("SECRET_KEY"),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256")
    )
