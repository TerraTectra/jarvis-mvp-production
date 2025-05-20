"""
Code Review API for the CI/CD system.

This module provides HTTP endpoints for triggering code reviews
and retrieving review results.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union
import os
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timedelta
import asyncio

from .review_engine import CodeReviewer, format_report_for_telegram, save_report

# Try to import telegram notifier, but make it optional
try:
    from .telegram_notifier import send_telegram_notification
except ImportError:
    send_telegram_notification = None
    
from .auth import (
    User,
    Token,
    TokenData,
    UserInDB,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_current_active_user,
    RoleChecker,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH
)

# Role-based access control
admin_required = RoleChecker(["admin"])
review_read_required = RoleChecker(["review:read"])
review_write_required = RoleChecker(["review:write"])

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('code_review_api')

router = APIRouter(prefix="/api/review", tags=["code-review"])
oauth_router = APIRouter(prefix="/api/auth", tags=["authentication"])

# In-memory storage for review results (in production, use a database)
review_results: Dict[str, Dict[str, Any]] = {}
DATA_DIR = Path(__file__).parent / 'data' / 'reviews'
DATA_DIR.mkdir(parents=True, exist_ok=True)

class LoginRequest(BaseModel):
    """Request model for user login."""
    username: str = Field(..., description="Username for authentication")
    password: str = Field(..., description="Password for authentication")


class TokenResponse(Token):
    """Response model for authentication token."""
    pass

class RefreshTokenRequest(BaseModel):
    """Request model for refreshing tokens."""
    refresh_token: str = Field(..., description="Refresh token to get a new access token")


class ReviewRequest(BaseModel):
    """Request model for triggering a code review."""
    repo_path: str = Field(..., description="Path to the repository to review")
    branch: Optional[str] = Field("main", description="Branch to review (default: main)")
    commit_hash: Optional[str] = Field(None, description="Specific commit hash to review")
    notify: bool = Field(True, description="Whether to send notifications for this review")

class ReviewResponse(BaseModel):
    """Response model for review status."""
    review_id: str
    status: str
    message: str
    timestamp: str
    report_url: Optional[str] = None

async def run_code_review(review_id: str, repo_path: str, notify: bool = True):
    """Run code review in the background and store results."""
    try:
        # Update status to in-progress
        review_results[review_id] = {
            'status': 'in_progress',
            'started_at': datetime.utcnow().isoformat(),
            'repo_path': repo_path
        }
        
        # Run the code review
        reviewer = CodeReviewer(repo_path)
        report = await asyncio.to_thread(reviewer.run_all_checks)
        
        # Save the report
        report_file = DATA_DIR / f"{review_id}.json"
        save_report(report, str(report_file))
        
        # Update results
        review_results[review_id].update({
            'status': 'completed',
            'completed_at': datetime.utcnow().isoformat(),
            'report_file': str(report_file),
            'summary': report.get('summary', {})
        })
        
        # Send notification if requested and Telegram notifier is available
        if notify and send_telegram_notification is not None:
            try:
                telegram_message = format_report_for_telegram(report)
                send_telegram_notification(telegram_message)
            except Exception as e:
                logger.error(f"Failed to send Telegram notification: {e}")
        elif notify:
            logger.warning("Telegram notifications are not available. Install required dependencies to enable notifications.")
        
        logger.info(f"Completed code review {review_id}")
        
    except Exception as e:
        logger.error(f"Error in code review {review_id}: {e}")
        if review_id in review_results:
            review_results[review_id].update({
                'status': 'failed',
                'error': str(e),
                'completed_at': datetime.utcnow().isoformat()
            })

@oauth_router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    OAuth2 compatible token login, get access and refresh tokens for future requests
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Login attempt for user: {form_data.username}")
    
    try:
        user = authenticate_user(fake_users_db, form_data.username, form_data.password)
        if not user:
            logger.warning(f"Authentication failed for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"User {user.username} authenticated successfully")
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "scopes": user.scopes},
        )
        
        # Create refresh token
        refresh_token = create_refresh_token(
            data={"sub": user.username}
        )
        
        logger.info(f"Tokens generated for user: {user.username}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    except Exception as e:
        logger.error(f"Error during authentication: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during authentication"
        )

@oauth_router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: RefreshTokenRequest
):
    """
    Refresh an access token using a refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the refresh token
        payload = jwt.decode(
            request.refresh_token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM]
        )
        
        # Verify token type
        if payload.get("type") != TOKEN_TYPE_REFRESH:
            raise credentials_exception
            
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
            
        # Get user from database
        user = get_user(fake_users_db, username)
        if user is None:
            raise credentials_exception
            
        # Create new tokens
        access_token = create_access_token(
            data={"sub": user.username, "scopes": user.scopes}
        )
        refresh_token = create_refresh_token(
            data={"sub": user.username}
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
        
    except JWTError:
        raise credentials_exception


@router.post("/trigger", response_model=ReviewResponse)
async def trigger_code_review(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(review_write_required)
) -> ReviewResponse:
    """Trigger a new code review."""
    # Validate repository path
    repo_path = Path(request.repo_path)
    if not repo_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository path not found: {request.repo_path}"
        )
    
    # Generate a unique ID for this review
    review_id = str(uuid.uuid4())
    
    # Start the review in the background
    background_tasks.add_task(
        run_code_review,
        review_id=review_id,
        repo_path=str(repo_path.absolute()),
        notify=request.notify
    )
    
    # Return immediate response
    return ReviewResponse(
        review_id=review_id,
        status="started",
        message="Code review has been queued",
        timestamp=datetime.utcnow().isoformat(),
        report_url=f"/ci/api/review/{review_id}"
    )

@router.get("/status/{review_id}", response_model=Dict[str, Any])
async def get_review_status(
    review_id: str,
    current_user: User = Depends(review_read_required)
) -> Dict[str, Any]:
    """
    Get the status of a code review.
    
    Requires 'review:read' scope.
    """
    if review_id not in review_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found"
        )
    
    result = review_results[review_id]
    
    # If the review is completed, include the summary
    if result['status'] == 'completed':
        with open(result['report_file'], 'r') as f:
            report = json.load(f)
        result['summary'] = report.get('summary', {})
    
    return result

@router.get("/report/{review_id}", response_class=JSONResponse)
async def get_review_report(
    review_id: str, 
    format: str = 'json',
    current_user: User = Depends(review_read_required)
):
    """
    Get the full review report.
    
    Args:
        review_id: The ID of the review to get the report for
        format: The format of the report ('json' or 'html')
        
    Returns:
        The review report in the requested format
        
    Raises:
        HTTPException: If the review is not found or not completed
    """
    if review_id not in review_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found"
        )
    
    result = review_results[review_id]
    
    if result['status'] != 'completed':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Review {review_id} is not completed yet"
        )
    
    with open(result['report_file'], 'r') as f:
        report = json.load(f)
    
    if format.lower() == 'html':
        # Convert to HTML format (simplified for example)
        html_content = f"""
        <html>
            <head><title>Code Review Report - {review_id}</title></head>
            <body>
                <h1>Code Review Report</h1>
                <p>Review ID: {review_id}</p>
                <p>Status: {result['status']}</p>
                <h2>Summary</h2>
                <pre>{json.dumps(report.get('summary', {}), indent=2)}</pre>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=200)
    
    return JSONResponse(content=report, status_code=200)

@router.get("/telegram/{review_id}", response_model=Dict[str, str])
async def get_telegram_summary(
    review_id: str,
    current_user: User = Depends(review_read_required)
) -> Dict[str, str]:
    """
    Get a Telegram-formatted summary of the review.
    
    Requires 'review:read' scope.
    """
    if review_id not in review_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review {review_id} not found"
        )
    
    result = review_results[review_id]
    
    if result['status'] != 'completed':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Review {review_id} is not completed yet"
        )
    
    with open(result['report_file'], 'r') as f:
        report = json.load(f)
    
    # Format the report for Telegram
    message = format_report_for_telegram(report)
    
    return {"message": message}

@router.get("/list", response_model=List[Dict[str, Any]])
async def list_recent_reviews(
    limit: int = 10,
    current_user: User = Depends(review_read_required)
) -> List[Dict[str, Any]]:
    """
    List recent code reviews.
    
    Args:
        limit: Maximum number of reviews to return (default: 10)
        
    Returns:
        List of recent reviews with basic information
        
    Requires 'review:read' scope.
    """
    # Get the most recent reviews
    recent_reviews = sorted(
        review_results.items(),
        key=lambda x: x[1].get('created_at', ''),
        reverse=True
    )[:limit]
    
    # Format the response
    return [
        {
            'review_id': review_id,
            'status': data['status'],
            'repo_path': data['repo_path'],
            'started_at': data.get('started_at'),
            'completed_at': data.get('completed_at')
        }
        for review_id, data in recent_reviews
    ]

def init_review_api(app, prefix: str = ""):
    """
    Initialize the code review API routes.
    
    Args:
        app: The FastAPI application instance
        prefix: URL prefix for all routes (default: "")
    """
    # Include both the main API router and the OAuth2 router
    # We don't add the prefix as it's already included in the routers' prefixes
    app.include_router(router)
    app.include_router(oauth_router)
    
    # Add CORS middleware if not already added
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, replace with specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
