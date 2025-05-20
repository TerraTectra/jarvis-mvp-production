#!/usr/bin/env python3
"""
CI/CD Web Dashboard

Provides a web interface for monitoring and controlling the CI/CD pipeline.
"""

import os
import json
import time
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, HTTPException, Depends, status, Form, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Union
import logging
import json
import datetime
import time
from pathlib import Path
import os
import shutil
import subprocess
from datetime import datetime, timedelta

# Import authentication utilities
from .auth import (
    User, Token, UserInDB, fake_users_db,
    create_access_token, create_refresh_token,
    get_user, authenticate_user, get_current_user,
    get_password_hash, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
)

# Import analytics module
from . import analytics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ci_web_ui')

# Constants
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"

# Create necessary directories
for directory in [STATIC_DIR, TEMPLATES_DIR, LOGS_DIR, DATA_DIR]:
    directory.mkdir(exist_ok=True)

# Initialize FastAPI app with metadata
app = FastAPI(
    title="Jarvis CI/CD Dashboard",
    description="Web interface for Jarvis CI/CD pipeline",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],  # In production, specify only needed methods
    allow_headers=["*"],  # In production, specify only needed headers
)

# List of paths that don't require authentication
PUBLIC_PATHS = {"/login", "/ci/api/health", "/ci/api/auth/token", "/ci/api/auth/refresh"}

@app.middleware("http")
async def check_auth(request: Request, call_next):
    # Skip auth check for public paths
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)
        
    # Check for token in cookies or Authorization header
    access_token = None
    if "access_token" in request.cookies:
        access_token = request.cookies["access_token"].replace("Bearer ", "")
    elif "authorization" in request.headers:
        auth_header = request.headers["authorization"]
        if auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    # If no token, redirect to login
    if not access_token:
        if request.url.path.startswith("/ci/api"):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Not authenticated"}
            )
        return RedirectResponse(url=f"/login?next={request.url}")
    
    # Verify token
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Add user to request state
        request.state.user = get_user(fake_users_db, username=username)
        
    except JWTError:
        if request.url.path.startswith("/ci/api"):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token"}
            )
        return RedirectResponse(url="/login")
    
    # Continue with the request
    response = await call_next(request)
    return response

# Serve static files
@app.get("/static/{file_path:path}")
async def serve_static(file_path: str):
    """Serve static files with proper caching headers."""
    file_location = STATIC_DIR / file_path
    
    if not file_location.exists() or not file_location.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Set cache headers (1 week for static assets)
    headers = {
        "Cache-Control": "public, max-age=604800, immutable"
    }
    
    return FileResponse(file_location, headers=headers)

# Mount static files for development
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/ci/api/auth/token")

# API key header for backward compatibility
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key(api_key_header: str = Depends(api_key_header)) -> str:
    """Validate API key from header."""
    if not api_key_header or api_key_header != os.getenv("UI_ADMIN_TOKEN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate API key",
        )
    return api_key_header

def verify_token(token: str) -> None:
    """Verify JWT token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

# Models
class PipelineRun(BaseModel):
    id: str
    status: str
    start_time: str
    end_time: Optional[str] = None
    branch: Optional[str] = None
    commit: Optional[str] = None
    steps: List[Dict[str, Any]] = []

# Helper functions
def get_system_info() -> Dict[str, Any]:
    """Get system information."""
    total, used, free = shutil.disk_usage("/")
    
    # Get container status (simplified example)
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}|{{.Status}}"],
            capture_output=True, text=True
        )
        containers = [
            {"name": line.split("|")[0], "status": line.split("|")[1]}
            for line in result.stdout.strip().split("\n") if line
        ]
    except Exception as e:
        containers = [{"name": "Error", "status": str(e)}]
    
    return {
        "disk_total_gb": total // (2**30),
        "disk_used_gb": used // (2**30),
        "disk_free_gb": free // (2**30),
        "containers": containers,
        "timestamp": datetime.now().isoformat()
    }

def get_pipeline_runs(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent pipeline runs from logs."""
    try:
        log_files = sorted(LOGS_DIR.glob("*.log"), key=os.path.getmtime, reverse=True)
        runs = []
        
        for log_file in log_files[:limit]:
            run_id = log_file.stem
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    last_line = ""
                    for line in f:
                        if line.strip():
                            last_line = line.strip()
                
                # Parse log file (simplified)
                status = "success" if "completed successfully" in last_line.lower() else "failed"
                runs.append({
                    "id": run_id,
                    "status": status,
                    "start_time": datetime.fromtimestamp(log_file.stat().st_ctime).isoformat(),
                    "log_file": log_file.name
                })
            except Exception as e:
                print(f"Error reading log file {log_file}: {e}")
        
        return runs
    except Exception as e:
        print(f"Error getting pipeline runs: {e}")
        return []

# Auth endpoints
@app.post("/ci/api/auth/token", response_model=Token)
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 compatible token login, get an access token for future requests"""
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes}
    )
    
    refresh_token_expires = datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        data={"sub": user.username}
    )
    
    # Set HTTP-only cookies for better security
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token
    }

@app.post("/ci/api/auth/refresh", response_model=Token)
async def refresh_access_token(request: Request):
    """Refresh access token using refresh token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = {"sub": username}
    except JWTError:
        raise credentials_exception
    
    user = get_user(fake_users_db, username=token_data["sub"])
    if user is None:
        raise credentials_exception
    
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/ci/api/auth/logout")
async def logout(response: Response):
    """Logout user by clearing auth cookies"""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Successfully logged out"}

# Favicon handler
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve the favicon."""
    favicon_path = STATIC_DIR / "img" / "favicon.ico"
    if not favicon_path.exists():
        favicon_path = STATIC_DIR / "favicon.ico"
    
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return Response(status_code=204)  # No content

# Root endpoint - redirect to login
@app.get("/")
async def root():
    """Redirect root to login page."""
    return RedirectResponse(url="/login")

# Health check endpoint (no auth required)
@app.get("/ci/api/health")
async def health_check():
    """Health check endpoint that doesn't require authentication."""
    return {"status": "ok", "timestamp": datetime.datetime.now().isoformat()}

# Login page
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page."""
    return templates.TemplateResponse("login.html", {"request": request})

# Main dashboard (requires authentication)
@app.get("/ci/ui", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    current_user: User = Depends(get_current_user)
):
    """Serve the main dashboard."""
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "now": datetime.datetime.now(),
            "user": current_user
        }
    )

@app.get("/ci/ui/analytics", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request, 
    current_user: User = Depends(get_current_user)
):
    """Serve the analytics dashboard."""
    return templates.TemplateResponse(
        "analytics.html", 
        {
            "request": request, 
            "now": datetime.datetime.now(),
            "user": current_user
        }
    )

@app.get("/ci/ui/logs/{log_file}")
async def get_log_file(
    log_file: str,
    _: str = Depends(get_api_key)
):
    """Download a log file."""
    log_path = LOGS_DIR / log_file
    if not log_path.exists() or not log_path.is_file():
        raise HTTPException(status_code=404, detail="Log file not found")
    
    return FileResponse(
        path=log_path,
        filename=log_file,
        media_type='text/plain'
    )

@app.post("/ci/ui/run")
async def run_pipeline(
    steps: str = Form("--all"),
    _: str = Depends(get_api_key)
):
    """Manually trigger the pipeline with specified steps."""
    try:
        # In a real implementation, this would trigger the actual pipeline
        # For now, we'll simulate it
        run_id = f"run_{int(time.time())}"
        log_file = LOGS_DIR / f"{run_id}.log"
        
        with open(log_file, 'w') as f:
            f.write(f"Pipeline started at {datetime.now().isoformat()}\n")
            f.write(f"Running steps: {steps}\n")
            
            # Simulate pipeline steps
            if "--all" in steps or "--setup" in steps:
                f.write("[INFO] Running setup...\n")
                time.sleep(1)
                
            if "--all" in steps or "--lint" in steps:
                f.write("[INFO] Running linting...\n")
                time.sleep(2)
                
            if "--all" in steps or "--test" in steps:
                f.write("[INFO] Running tests...\n")
                time.sleep(3)
                
            f.write("[SUCCESS] Pipeline completed successfully\n")
        
        return {
            "status": "success",
            "run_id": run_id,
            "message": f"Pipeline started with steps: {steps}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Create template files if they don't exist
TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jarvis CI/CD Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
</head>
<body class="bg-gray-100">
    <div class="min-h-screen">
        <!-- Header -->
        <header class="bg-blue-600 text-white shadow-lg">
            <div class="container mx-auto px-4 py-4 flex justify-between items-center">
                <h1 class="text-2xl font-bold">Jarvis CI/CD Dashboard</h1>
                <div class="text-sm">
                    <span class="bg-blue-500 px-2 py-1 rounded">
                        <i class="fas fa-circle text-green-400 mr-1"></i>
                        Connected
                    </span>
                    <span class="ml-2">{{ current_time }}</span>
                </div>
            </div>
        </header>

        <main class="container mx-auto px-4 py-6">
            <!-- System Info -->
            <div class="bg-white rounded-lg shadow-md p-6 mb-6">
                <h2 class="text-xl font-semibold mb-4 flex items-center">
                    <i class="fas fa-tachometer-alt mr-2"></i>
                    System Information
                </h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="bg-gray-50 p-4 rounded">
                        <h3 class="font-medium text-gray-700">Disk Usage</h3>
                        <div class="mt-2">
                            <div class="w-full bg-gray-200 rounded-full h-2.5">
                                {% set used_percent = ((system_info.disk_used_gb / system_info.disk_total_gb) * 100)|int %}
                                <div class="bg-blue-600 h-2.5 rounded-full" style="width: {{ used_percent }}%"></div>
                            </div>
                            <div class="flex justify-between text-sm text-gray-600 mt-1">
                                <span>{{ system_info.disk_used_gb }} GB used</span>
                                <span>{{ system_info.disk_free_gb }} GB free</span>
                            </div>
                            <div class="text-xs text-gray-500 mt-1">Total: {{ system_info.disk_total_gb }} GB</div>
                        </div>
                    </div>
                    <div class="bg-gray-50 p-4 rounded">
                        <h3 class="font-medium text-gray-700">Containers</h3>
                        <div class="mt-2 space-y-2">
                            {% for container in system_info.containers %}
                            <div class="flex items-center">
                                <span class="w-2 h-2 rounded-full bg-green-500 mr-2"></span>
                                <span class="text-sm">{{ container.name }}</span>
                                <span class="text-xs text-gray-500 ml-auto">{{ container.status|truncate(20) }}</span>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                    <div class="bg-gray-50 p-4 rounded">
                        <h3 class="font-medium text-gray-700">Quick Actions</h3>
                        <div class="mt-2 space-y-2">
                            <form id="runPipelineForm" class="space-y-2">
                                <div class="space-y-1">
                                    <label class="flex items-center">
                                        <input type="checkbox" name="steps" value="--setup" class="rounded text-blue-600" checked>
                                        <span class="ml-2 text-sm">Setup</span>
                                    </label>
                                    <label class="flex items-center">
                                        <input type="checkbox" name="steps" value="--lint" class="rounded text-blue-600" checked>
                                        <span class="ml-2 text-sm">Lint</span>
                                    </label>
                                    <label class="flex items-center">
                                        <input type="checkbox" name="steps" value="--test" class="rounded text-blue-600" checked>
                                        <span class="ml-2 text-sm">Test</span>
                                    </label>
                                </div>
                                <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-md text-sm font-medium transition-colors">
                                    <i class="fas fa-play mr-1"></i> Run Pipeline
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Pipeline Runs -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-semibold flex items-center">
                        <i class="fas fa-history mr-2"></i>
                        Recent Pipeline Runs
                    </h2>
                    <span class="text-sm text-gray-500">Showing last {{ pipeline_runs|length }} runs</span>
                </div>
                
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Run ID</th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Start Time</th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                                <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            {% for run in pipeline_runs %}
                            <tr>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-mono">{{ run.id }}</td>
                                <td class="px-6 py-4 whitespace-nowrap">
                                    {% if run.status == 'success' %}
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                        Success
                                    </span>
                                    {% else %}
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                                        Failed
                                    </span>
                                    {% endif %}
                                </td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ run.start_time }}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">--:--:--</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                    <a href="/ci/ui/logs/{{ run.log_file }}" class="text-blue-600 hover:text-blue-900 mr-3">
                                        <i class="fas fa-file-alt"></i> View Log
                                    </a>
                                    <a href="#" class="text-blue-600 hover:text-blue-900">
                                        <i class="fas fa-redo"></i> Rerun
                                    </a>
                                </td>
                            </tr>
                            {% else %}
                            <tr>
                                <td colspan="5" class="px-6 py-4 text-center text-sm text-gray-500">
                                    No pipeline runs found
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </main>

        <footer class="bg-white border-t border-gray-200 mt-8">
            <div class="container mx-auto px-4 py-4 text-center text-sm text-gray-500">
                <p>Jarvis CI/CD Dashboard &copy; {{ now.year }}. All rights reserved.</p>
            </div>
        </footer>
    </div>

    <script>
        // Handle form submission
        document.getElementById('runPipelineForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const steps = Array.from(formData.getAll('steps'));
            
            try {
                const response = await fetch('/ci/ui/run', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-Admin-Token': localStorage.getItem('adminToken') || ''
                    },
                    body: `steps=${encodeURIComponent(steps.join(' '))}`
                });
                
                const result = await response.json();
                if (response.ok) {
                    alert(`Pipeline started: ${result.run_id}`);
                    window.location.reload();
                } else {
                    throw new Error(result.detail || 'Failed to start pipeline');
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        });

        // Store the API token from the URL if present
        const urlParams = new URLSearchParams(window.location.search);
        const token = urlParams.get('token');
        if (token) {
            localStorage.setItem('adminToken', token);
        }
    </script>
</body>
</html>
"""

# Create template directory and file if they don't exist
TEMPLATES_DIR.mkdir(exist_ok=True)
template_file = TEMPLATES_DIR / "dashboard.html"
if not template_file.exists():
    with open(template_file, 'w', encoding='utf-8') as f:
        f.write(TEMPLATE_HTML)

# Create a simple CSS file
CSS_CONTENT = """
/* Custom styles for the CI/CD Dashboard */
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* Status badges */
.status-badge {
    @apply inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium;
}

.status-badge.success {
    @apply bg-green-100 text-green-800;
}

.status-badge.failed {
    @apply bg-red-100 text-red-800;
}

.status-badge.running {
    @apply bg-blue-100 text-blue-800;
}

/* Log viewer */
.log-viewer {
    @apply font-mono text-sm bg-gray-900 text-green-400 p-4 rounded overflow-auto;
    max-height: 400px;
}

/* Animation for loading */
@keyframes spin {
    to { transform: rotate(360deg); }
}

.animate-spin {
    animation: spin 1s linear infinite;
}
"""

# Create static directory and CSS file if they don't exist
(STATIC_DIR / "css").mkdir(parents=True, exist_ok=True)
css_file = STATIC_DIR / "css" / "styles.css"
if not css_file.exists():
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(CSS_CONTENT)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WEBHOOK_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
