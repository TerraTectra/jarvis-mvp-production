"""CRUD operations for users."""
from typing import Optional, List

from sqlalchemy import select, update, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.user import User, Role, Permission, user_roles
from src.schemas.user import UserCreate, UserUpdate, RoleCreate, RoleUpdate, PermissionCreate

# User operations

async def get_user(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get a user by ID."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .filter(User.id == user_id)
    )
    return result.scalars().first()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get a user by username."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .filter(User.username == username)
    )
    return result.scalars().first()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get a user by email."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .filter(User.email == email)
    )
    return result.scalars().first()

async def get_users(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    search: Optional[str] = None,
) -> List[User]:
    """Get a list of users with optional search and pagination."""
    query = select(User).options(selectinload(User.roles).selectinload(Role.permissions))
    
    if search:
        search_filter = or_(
            User.username.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
            User.full_name.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()

async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """Create a new user."""
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=user_in.password,  # Password should be hashed before this
        full_name=user_in.full_name,
        is_active=user_in.is_active if user_in.is_active is not None else True,
        is_verified=user_in.is_verified if user_in.is_verified is not None else False,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(
    db: AsyncSession, 
    db_user: User, 
    user_in: UserUpdate
) -> User:
    """Update a user."""
    update_data = user_in.dict(exclude_unset=True)
    
    # Handle password update
    if 'password' in update_data and update_data['password']:
        hashed_password = update_data.pop('password')  # Should be hashed before this
        update_data['hashed_password'] = hashed_password
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Delete a user."""
    result = await db.execute(delete(User).filter(User.id == user_id))
    await db.commit()
    return result.rowcount > 0

async def verify_user_email(db: AsyncSession, user_id: int) -> Optional[User]:
    """Mark a user's email as verified."""
    result = await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(is_verified=True)
        .returning(User)
    )
    user = result.scalars().first()
    if user:
        await db.commit()
    return user

# Role operations

async def get_role(db: AsyncSession, role_id: int) -> Optional[Role]:
    """Get a role by ID."""
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .filter(Role.id == role_id)
    )
    return result.scalars().first()

async def get_role_by_name(db: AsyncSession, name: str) -> Optional[Role]:
    """Get a role by name."""
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .filter(Role.name == name)
    )
    return result.scalars().first()

async def get_roles(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    search: Optional[str] = None
) -> List[Role]:
    """Get a list of roles with optional search and pagination."""
    query = select(Role).options(selectinload(Role.permissions))
    
    if search:
        query = query.filter(Role.name.ilike(f"%{search}%"))
    
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()

async def create_role(db: AsyncSession, role_in: RoleCreate) -> Role:
    """Create a new role."""
    db_role = Role(
        name=role_in.name,
        description=role_in.description,
        is_default=role_in.is_default if role_in.is_default is not None else False,
    )
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)
    return db_role

async def update_role(
    db: AsyncSession, 
    db_role: Role, 
    role_in: RoleUpdate
) -> Role:
    """Update a role."""
    update_data = role_in.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_role, field, value)
    
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)
    return db_role

async def delete_role(db: AsyncSession, role_id: int) -> bool:
    """Delete a role."""
    result = await db.execute(delete(Role).where(Role.id == role_id))
    await db.commit()
    return result.rowcount > 0

async def add_role_to_user(
    db: AsyncSession, 
    user_id: int, 
    role_id: int
) -> bool:
    """Add a role to a user."""
    # Check if the relationship already exists
    result = await db.execute(
        select(user_roles)
        .where(user_roles.c.user_id == user_id)
        .where(user_roles.c.role_id == role_id)
    )
    if result.first():
        return False  # Relationship already exists
    
    # Add the relationship
    await db.execute(
        user_roles.insert().values(user_id=user_id, role_id=role_id)
    )
    await db.commit()
    return True

async def remove_role_from_user(
    db: AsyncSession, 
    user_id: int, 
    role_id: int
) -> bool:
    """Remove a role from a user."""
    result = await db.execute(
        user_roles.delete()
        .where(user_roles.c.user_id == user_id)
        .where(user_roles.c.role_id == role_id)
    )
    await db.commit()
    return result.rowcount > 0

# Permission operations

async def get_permission(db: AsyncSession, permission_id: int) -> Optional[Permission]:
    """Get a permission by ID."""
    result = await db.execute(select(Permission).filter(Permission.id == permission_id))
    return result.scalars().first()

async def get_permission_by_name(db: AsyncSession, name: str) -> Optional[Permission]:
    """Get a permission by name."""
    result = await db.execute(select(Permission).filter(Permission.name == name))
    return result.scalars().first()

async def get_permissions(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100,
    search: Optional[str] = None
) -> List[Permission]:
    """Get a list of permissions with optional search and pagination."""
    query = select(Permission)
    
    if search:
        query = query.filter(Permission.name.ilike(f"%{search}%"))
    
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()

async def create_permission(
    db: AsyncSession, 
    permission_in: PermissionCreate
) -> Permission:
    """Create a new permission."""
    db_permission = Permission(
        name=permission_in.name,
        description=permission_in.description,
    )
    db.add(db_permission)
    await db.commit()
    await db.refresh(db_permission)
    return db_permission

async def add_permission_to_role(
    db: AsyncSession, 
    role_id: int, 
    permission_id: int
) -> bool:
    """Add a permission to a role."""
    role = await get_role(db, role_id)
    if not role:
        return False
    
    permission = await get_permission(db, permission_id)
    if not permission:
        return False
    
    if permission in role.permissions:
        return False  # Permission already assigned
    
    role.permissions.append(permission)
    await db.commit()
    return True

async def remove_permission_from_role(
    db: AsyncSession, 
    role_id: int, 
    permission_id: int
) -> bool:
    """Remove a permission from a role."""
    role = await get_role(db, role_id)
    if not role:
        return False
    
    permission = await get_permission(db, permission_id)
    if not permission:
        return False
    
    if permission not in role.permissions:
        return False  # Permission not assigned
    
    role.permissions.remove(permission)
    await db.commit()
    return True
