"""Pydantic models for user-related schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, validator

class Token(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Token data schema."""
    username: Optional[str] = None
    scopes: List[str] = []

class UserBase(BaseModel):
    """Base user schema."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)

class UserCreate(UserBase):
    """Schema for user creation."""
    password: str = Field(..., min_length=8, max_length=100)

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserUpdate(BaseModel):
    """Schema for user updates."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserInDB(UserBase):
    """Schema for user in database."""
    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True

class UserResponse(UserInDB):
    """Schema for user response with roles."""
    roles: List[str] = []
    
    class Config:
        orm_mode = True
        from_attributes = True
        arbitrary_types_allowed = True
    
    @classmethod
    def from_orm(cls, obj):
        # Extract role names from the roles relationship
        if hasattr(obj, 'roles'):
            obj.roles = [role.name for role in obj.roles] if obj.roles else []
        return super().from_orm(obj)

class RoleBase(BaseModel):
    """Base role schema."""
    name: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    description: Optional[str] = None
    is_default: bool = False

class RoleCreate(RoleBase):
    """Schema for role creation."""
    pass

class RoleUpdate(BaseModel):
    """Schema for role updates."""
    description: Optional[str] = None
    is_default: Optional[bool] = None

class RoleInDB(RoleBase):
    """Schema for role in database."""
    id: int
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class PermissionBase(BaseModel):
    """Base permission schema."""
    name: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-z_]+$')
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    """Schema for permission creation."""
    role_id: int

class PermissionInDB(PermissionBase):
    """Schema for permission in database."""
    id: int
    role_id: int
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @validator('new_password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v
