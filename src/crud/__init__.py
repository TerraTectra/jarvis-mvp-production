"""CRUD operations for the application."""

from .user import (
    # User operations
    get_user,
    get_user_by_username,
    get_user_by_email,
    get_users,
    create_user,
    update_user,
    delete_user,
    
    # Role operations
    get_role,
    get_role_by_name,
    get_roles,
    create_role,
    update_role,
    delete_role,
    add_role_to_user,
    remove_role_from_user,
    
    # Permission operations
    get_permission,
    get_permission_by_name,
    get_permissions,
    create_permission,
    add_permission_to_role,
    remove_permission_from_role,
)

__all__ = [
    # User operations
    "get_user",
    "get_user_by_username",
    "get_user_by_email",
    "get_users",
    "create_user",
    "update_user",
    "delete_user",
    
    # Role operations
    "get_role",
    "get_role_by_name",
    "get_roles",
    "create_role",
    "update_role",
    "delete_role",
    "add_role_to_user",
    "remove_role_from_user",
    
    # Permission operations
    "get_permission",
    "get_permission_by_name",
    "get_permissions",
    "create_permission",
    "add_permission_to_role",
    "remove_permission_from_role",
]
