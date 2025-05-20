"""Security utilities for the application."""
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional, Union

from jose import jwt
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate a password hash."""
    return pwd_context.hash(password)

def generate_password_reset_token(email: str) -> str:
    """Generate a password reset token."""
    delta = timedelta(hours=24)  # Token expires in 24 hours
    now = datetime.utcnow()
    expires = now + delta
    exp = int(expires.timestamp())
    
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email, "type": "password_reset"},
        os.getenv("SECRET_KEY"),
        algorithm="HS256",
    )
    return encoded_jwt

def verify_password_reset_token(token: str) -> Optional[str]:
    """Verify a password reset token and return the email if valid."""
    try:
        decoded_token = jwt.decode(
            token, os.getenv("SECRET_KEY"), algorithms=["HS256"]
        )
        if decoded_token["type"] != "password_reset":
            return None
        return decoded_token["sub"]
    except jwt.JWTError:
        return None

def generate_email_verification_token(email: str) -> str:
    """Generate an email verification token."""
    delta = timedelta(days=7)  # Token expires in 7 days
    now = datetime.utcnow()
    expires = now + delta
    exp = int(expires.timestamp())
    
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email, "type": "email_verification"},
        os.getenv("SECRET_KEY"),
        algorithm="HS256",
    )
    return encoded_jwt

def verify_email_token(token: str) -> Optional[str]:
    """Verify an email verification token and return the email if valid."""
    try:
        decoded_token = jwt.decode(
            token, os.getenv("SECRET_KEY"), algorithms=["HS256"]
        )
        if decoded_token["type"] != "email_verification":
            return None
        return decoded_token["sub"]
    except jwt.JWTError:
        return None

def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_urlsafe(32)
