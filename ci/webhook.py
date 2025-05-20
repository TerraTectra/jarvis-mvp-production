#!/usr/bin/env python3
"""
FastAPI Webhook Handler for CI/CD Pipeline

This module provides a webhook endpoint for GitHub/GitLab to trigger CI/CD pipelines.
"""

import os
import hmac
import hashlib
import subprocess
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, Header, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ci_webhook')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ci_webhook')

# Create base FastAPI app
app = FastAPI(
    title="Jarvis CI/CD Dashboard",
    description="Web interface and webhook handler for CI/CD pipelines",
    version="1.0.0"
)

# Mount static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# Create directories if they don't exist
for directory in [STATIC_DIR, TEMPLATES_DIR]:
    os.makedirs(directory, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

class WebhookPayload(BaseModel):
    """Base model for webhook payloads."""
    repository: Optional[Dict[str, Any]] = None
    ref: Optional[str] = None
    object_kind: Optional[str] = None  # GitLab
    object_attributes: Optional[Dict[str, Any]] = None  # GitLab MR
    action: Optional[str] = None  # GitHub actions

# Get configuration from environment variables
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '').encode('utf-8')
MAIN_BRANCH = os.getenv('MAIN_BRANCH', 'main')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Path to the pipeline script
PIPELINE_SCRIPT = os.path.join(os.path.dirname(__file__), 'run_pipeline.py')

def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature."""
    if not WEBHOOK_SECRET:
        logger.warning("No WEBHOOK_SECRET set, skipping signature verification")
        return True
        
    if not signature:
        logger.error("Missing X-Hub-Signature-256 header")
        return False
        
    try:
        # GitHub sends the signature as 'sha256=...'
        if signature.startswith('sha256='):
            signature = signature[7:]
            
        # Create a new HMAC object with the secret
        mac = hmac.new(WEBHOOK_SECRET, msg=payload, digestmod=hashlib.sha256)
        
        # Compare the computed hash with the provided signature
        return hmac.compare_digest(mac.hexdigest(), signature)
    except Exception as e:
        logger.error(f"Error verifying signature: {e}")
        return False

def verify_gitlab_token(token: str) -> bool:
    """Verify GitLab webhook token."""
    if not WEBHOOK_SECRET:
        logger.warning("No WEBHOOK_SECRET set, skipping token verification")
        return True
        
    return hmac.compare_digest(WEBHOOK_SECRET, token.encode('utf-8'))

async def get_telegram_notifier() -> Optional[TelegramNotifier]:
    """Create and return a TelegramNotifier instance if configured.
    
    Returns:
        Optional[TelegramNotifier]: Configured TelegramNotifier or None if not configured
    """
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    enabled = os.getenv('CI_TELEGRAM_NOTIFY', 'false').lower() == 'true'
    
    if not enabled:
        logger.info("Telegram notifications are disabled (CI_TELEGRAM_NOTIFY=false)")
        return None
        
    if not token or not chat_id:
        logger.warning("Telegram bot token or chat ID not configured")
        return None
        
    return TelegramNotifier(token, chat_id, enabled)

async def send_telegram_notification(message: str) -> bool:
    """Send a notification to Telegram."""
    notifier = await get_telegram_notifier()
    if notifier:
        try:
            await notifier.send(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
    return False

def log_pipeline_event(event_type: str, payload: dict, status: str = "started"):
    """Log pipeline events to a file for the web UI."""
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "pipeline_events.log")
        with open(log_file, "a") as f:
            f.write(f"{datetime.datetime.utcnow().isoformat()} | {event_type} | {status} | {json.dumps(payload)}\n")
    except Exception as e:
        logger.error(f"Failed to log pipeline event: {e}")

def run_pipeline(args: str = "") -> bool:
    """Run the CI/CD pipeline with the given arguments."""
    try:
        cmd = ['python3', PIPELINE_SCRIPT]
        if args:
            cmd.extend(args.split())
            
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Run in background to avoid blocking
        subprocess.Popen(
            cmd,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return True
    except Exception as e:
        logger.error(f"Failed to run pipeline: {e}")
        return False

@app.get("/ci/ui")
async def web_ui(request: Request):
    """Serve the web UI dashboard."""
    # This is a simple redirect to the actual web UI
    # In a real implementation, you would serve a proper HTML page
    return {"message": "Web UI is available at /ci/dashboard"}

@app.post("/ci/webhook")
async def handle_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),  # GitHub
    x_gitlab_token: Optional[str] = Header(None),       # GitLab
    x_gitlab_event: Optional[str] = Header(None)        # GitLab
):
    """Handle incoming webhook requests from GitHub/GitLab."""
    # Get the raw request body
    try:
        body = await request.body()
        payload = await request.json()
    except Exception as e:
        logger.error(f"Error parsing request: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")
    
    # Check if this is a GitHub or GitLab webhook
    is_github = x_hub_signature_256 is not None
    is_gitlab = x_gitlab_token is not None and x_gitlab_event is not None
    
    # Verify the request
    if is_github:
        if not verify_github_signature(body, x_hub_signature_256):
            logger.error("GitHub signature verification failed")
            raise HTTPException(status_code=403, detail="Invalid signature")
        logger.info("GitHub webhook verified successfully")
    elif is_gitlab:
        if not verify_gitlab_token(x_gitlab_token):
            logger.error("GitLab token verification failed")
            raise HTTPException(status_code=403, detail="Invalid token")
        logger.info("GitLab webhook verified successfully")
    else:
        logger.error("Missing required headers for GitHub/GitLab webhook")
        raise HTTPException(status_code=400, detail="Missing required headers")
    
    # Extract repository information
    repo_name = "unknown"
    event_type = "unknown"
    
    try:
        if is_github:
            # GitHub payload structure
            repo_name = payload.get('repository', {}).get('full_name', 'unknown')
            event_type = request.headers.get('X-GitHub-Event', 'unknown')
            
            if event_type == 'push':
                ref = payload.get('ref', '')
                if ref.endswith(f'refs/heads/{MAIN_BRANCH}'):
                    message = f"🔔 [CI] Получен вебхук от {repo_name} (push в {MAIN_BRANCH}), запускаю полный пайплайн…"
                    await send_telegram_notification(message)
                    log_pipeline_event("push", {"repo": repo_name, "branch": MAIN_BRANCH, "ref": ref})
                    run_pipeline("--all")
                else:
                    branch = ref.split('/')[-1]
                    logger.info(f"Push to non-main branch {branch}, ignoring")
                    return {"status": "ignored", "reason": f"Not main branch ({branch} != {MAIN_BRANCH})"}
                    
            elif event_type == 'pull_request' and payload.get('action') == 'opened':
                pr_number = payload.get('number', 'unknown')
                pr_title = payload.get('pull_request', {}).get('title', 'No title')
                message = f"🔔 [CI] Получен вебхук от {repo_name} (новый PR #{pr_number}: {pr_title}), запускаю проверки…"
                await send_telegram_notification(message)
                log_pipeline_event("pull_request", {
                    "repo": repo_name, 
                    "pr_number": pr_number,
                    "title": pr_title,
                    "action": "opened"
                })
                run_pipeline("--setup --lint --test")
            
        elif is_gitlab:
            # GitLab payload structure
            repo_name = payload.get('project', {}).get('path_with_namespace', 'unknown')
            event_type = x_gitlab_event
            
            if event_type == 'Push Hook':
                ref = payload.get('ref', '')
                if ref.endswith(f'refs/heads/{MAIN_BRANCH}'):
                    message = f"🔔 [CI] Получен вебхук от {repo_name} (push в {MAIN_BRANCH}), запускаю полный пайплайн…"
                    await send_telegram_notification(message)
                    log_pipeline_event("push", {"repo": repo_name, "branch": MAIN_BRANCH, "ref": ref})
                    run_pipeline("--all")
                else:
                    branch = ref.split('/')[-1]
                    logger.info(f"Push to non-main branch {branch}, ignoring")
                    return {"status": "ignored", "reason": "Not main branch"}
                    
            elif event_type == 'Merge Request Hook' and payload.get('object_attributes', {}).get('action') == 'open':
                mr_id = payload.get('object_attributes', {}).get('iid', 'unknown')
                mr_title = payload.get('object_attributes', {}).get('title', 'No title')
                message = f"🔔 [CI] Получен вебхук от {repo_name} (новый MR !{mr_id}: {mr_title}), запускаю проверки…"
                await send_telegram_notification(message)
                log_pipeline_event("merge_request", {
                    "repo": repo_name, 
                    "mr_id": mr_id,
                    "title": mr_title,
                    "action": "opened"
                })
                run_pipeline("--setup --lint --test")
        
        logger.info(f"Processed {event_type} event for {repo_name}")
        return {"status": "success", "event": event_type, "repository": repo_name}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        await send_telegram_notification(f"❌ [CI] Ошибка при обработке вебхука: {str(e)[:200]}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('WEBHOOK_PORT', '8000'))
    uvicorn.run(app, host="0.0.0.0", port=port)
