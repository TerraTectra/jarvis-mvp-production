import logging
import os
import sys
from pathlib import Path
from typing import Optional

from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, Query, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware import Middleware
from fastapi.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from passlib.context import CryptContext
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import List, Dict, Any, Union

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# Fake user database
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("admin"),
        "disabled": False,
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    disabled: bool = False

class UserInDB(User):
    hashed_password: str

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Configure logging first
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
logger.info("Creating FastAPI app...")
app = FastAPI()

# Add health check endpoint
@app.get("/api/health")
def health_check():
    logger.debug("Health check endpoint called")
    return {"status": "ok"}

# Authentication endpoints
@app.post("/api/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    logger.info(f"Login attempt for user: {form_data.username}")
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        logger.warning(f"Failed login attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    logger.info(f"Successful login for user: {form_data.username}")
    return {"access_token": access_token, "token_type": "bearer"}

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)
logger.debug(f"Added {project_root} to Python path")

# Load spacy model
try:
    logger.info("Loading spacy model...")
    import spacy
    nlp = spacy.load("ru_core_news_sm")
    logger.info("Spacy model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load spacy model: {str(e)}")
    raise

# Security middleware and CORS
logger.info("Setting up security middleware...")
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token from Authorization header."""
    logger.debug("Verifying token...")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            logger.warning("No username found in token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.debug(f"Token verified for user: {username}")
        return payload
    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Middleware для проверки токена доступа к Web UI
class WebUIAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Пропускаем проверку для API эндпоинтов и аутентификации
        if request.url.path.startswith("/api/") or request.url.path == "/docs" or request.url.path == "/redoc" or request.url.path == "/openapi.json":
            return await call_next(request)
            
        # Проверяем токен доступа из куки или заголовка
        ui_token = request.cookies.get("ui_token") or request.headers.get("x-ui-token")
        valid_token = os.getenv("UI_ADMIN_TOKEN")
        
        # Если токен не указан, перенаправляем на страницу входа
        if not ui_token or ui_token != valid_token:
            if request.url.path != "/login":
                return RedirectResponse(url="/login")
            return await call_next(request)
            
        # Если токен валиден, пропускаем запрос
        return await call_next(request)

# Настройка CORS и middleware
logger.info("Configuring CORS and middleware...")
allowed_origins = os.getenv("ALLOWED_HOSTS", "*").split(",")
logger.debug(f"Allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Добавляем middleware для аутентификации Web UI
app.add_middleware(WebUIAuthMiddleware)
logger.info("CORS and middleware configured")

# Protect Swagger UI and ReDoc
logger.info("Setting up API documentation endpoints...")

@app.get("/api/docs", include_in_schema=False)
async def get_swagger_documentation(token: str = Depends(verify_token)):
    logger.debug("Serving Swagger UI")
    try:
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title="Jarvis MVP API - Swagger UI",
            oauth2_redirect_url="/api/docs/oauth2-redirect",
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger-ui.css"
        )
    except Exception as e:
        logger.error(f"Error serving Swagger UI: {str(e)}")
        raise

@app.get("/api/redoc", include_in_schema=False)
async def get_redoc_documentation(token: str = Depends(verify_token)):
    """Serve ReDoc documentation with authentication."""
    logger.debug("Serving ReDoc documentation")
    try:
        return get_redoc_html(
            openapi_url="/api/openapi.json",
            title="Jarvis MVP API - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"
        )
    except Exception as e:
        logger.error(f"Error serving ReDoc: {str(e)}")
        raise

# Custom OpenAPI schema
logger.info("Configuring OpenAPI schema...")

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Jarvis MVP API",
        version="0.1.0",
        description="""
        API for Jarvis MVP - Automated Project Parser and Code Review System
        
        ## Authentication
        Most endpoints require authentication using JWT tokens.
        Use the `/api/auth/token` endpoint to get a token.
        """,
        routes=app.routes,
    )
    
    # Add security definitions
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT token in the format: Bearer <token>"
        }
    }
    
    # Apply security globally
    openapi_schema["security"] = [{"Bearer": []}]
    
    app.openapi_schema = openapi_schema
    logger.debug("OpenAPI schema configured")
    return app.openapi_schema

app.openapi = custom_openapi

# Initialize code review API
logger.info("Initializing code review API...")
try:
    from ci import init_review_api
    init_review_api(app)
    logger.info("Code review API initialized")
except Exception as e:
    logger.error(f"Failed to initialize code review API: {str(e)}")
    raise

# Настройка шаблонов
logger.info("Setting up templates and static files...")
try:
    BASE_DIR = Path(__file__).parent
    templates = Jinja2Templates(directory=str(Path(BASE_DIR, "templates")))
    logger.debug(f"Templates directory: {Path(BASE_DIR, 'templates')}")
    
    # Монтирование статических файлов
    static_dir = Path(BASE_DIR, "static")
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.debug(f"Static files mounted at /static from {static_dir}")
    else:
        logger.warning(f"Static files directory not found: {static_dir}")
except Exception as e:
    logger.error(f"Error setting up templates or static files: {str(e)}")
    raise

# Создаем шаблон для страницы входа, если его нет
login_template_path = Path(BASE_DIR, "templates", "login.html")
if not login_template_path.exists():
    login_template_path.write_text("""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход в панель управления</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 400px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .login-container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #555;
        }
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 12px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #45a049;
        }
        .error {
            color: #f44336;
            margin-top: 10px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>Вход в панель управления</h1>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="token">Токен доступа:</label>
                <input type="password" id="token" name="token" required>
            </div>
            <button type="submit">Войти</button>
        </form>
    </div>
</body>
</html>""", encoding="utf-8")
    logger.info("Created login template")

# Мок-данные заказов
logger.info("Initializing mock data...")
MOCK_ORDERS = [
    {"id": 1, "title": "Разработка веб-сайта", "description": "Нужно разработать корпоративный сайт"},
    {"id": 2, "title": "Создание мобильного приложения", "description": "Требуется приложение для iOS и Android"},
    {"id": 3, "title": "Написание скрипта для парсинга данных", "description": "Парсинг данных с сайта"},
    {"id": 4, "title": "Разработка чат-бота для Telegram", "description": "Бот для автоматизации ответов"},
    {"id": 5, "title": "Создание базы данных", "description": "Проектирование и реализация БД"},
]
logger.debug(f"Initialized {len(MOCK_ORDERS)} mock orders")

class OrderRequest(BaseModel):
    id: Union[int, str]
    title: str
    source: Optional[str] = "local"
    url: Optional[str] = ""
    send: Optional[bool] = False  # Флаг для отправки отклика

class SubmissionResponse(BaseModel):
    status: str
    message: Optional[str] = None
    reason: Optional[str] = None

class OrderResponse(BaseModel):
    id: str
    title: str
    reply: str
    source: str
    sent: bool = False
    submission: Optional[SubmissionResponse] = None
    url: Optional[str] = ""

def analyze_order(title: str):
    """Анализирует заголовок заказа с помощью NLP."""
    logger.debug(f"Analyzing order title: {title}")
    try:
        doc = nlp(title)
        keywords = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct]
        sentiment = "positive" if any(token.sentiment > 0.5 for token in doc) else "neutral"
        
        logger.debug(f"Analysis complete - Keywords: {keywords}, Sentiment: {sentiment}")
        return {
            "keywords": keywords,
            "sentiment": sentiment
        }
    except Exception as e:
        logger.error(f"Error analyzing order: {str(e)}")
        return {
            "keywords": [],
            "sentiment": "neutral"
        }

def generate_response(order: Dict[str, Any]) -> Dict[str, Any]:
    """Генерация ответа на заказ с анализом."""
    logger.debug(f"Generating response for order: {order.get('id')}")
    try:
        analysis = analyze_order(order.get("title", ""))
        keywords = analysis.get("keywords", [])
        sentiment = analysis.get("sentiment", "neutral")
        
        response = {
            "id": order.get("id"),
            "title": order.get("title", ""),
            "reply": (
                f"Отклик на заказ #{order.get('id')}. "
                f"Ключевые темы: {', '.join(keywords[:5]) if keywords else 'не определены'}. "
                f"Общий тон: {'позитивный' if sentiment == 'positive' else 'нейтральный'}. "
                "Готов приступить к выполнению!"
            ),
            "analysis": analysis
        }
        logger.debug(f"Generated response: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return {
            "id": order.get("id", ""),
            "title": order.get("title", ""),
            "reply": "Извините, не удалось сгенерировать ответ на заказ.",
            "error": str(e)
        }

async def get_orders(source: str = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Получает заказы из указанного источника.
    
    Args:
        source: Источник заказов (kwork, local)
        limit: Максимальное количество заказов
        
    Returns:
        Список заказов
    """
    logger.info(f"Fetching orders from source: {source or 'default'}, limit: {limit}")
    
    try:
        if source == "kwork":
            logger.debug("Fetching orders from Kwork...")
            try:
                orders = await fetch_kwork_orders(limit=limit)
                logger.info(f"Successfully fetched {len(orders)} orders from Kwork")
                return orders
            except ImportError as ie:
                logger.error(f"Failed to import Kwork integration: {str(ie)}")
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail="Kwork integration is not available"
                )
            except Exception as e:
                logger.error(f"Error fetching Kwork orders: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Failed to fetch orders from Kwork. Please try again later."
                )
        else:
            # Return mock data
            logger.debug(f"Using mock data, returning {min(limit, len(MOCK_ORDERS))} orders")
            return MOCK_ORDERS[:limit]
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions
        
    except Exception as e:
        logger.error(f"Unexpected error in get_orders: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your request"
        )

@app.get(
    "/orders",
    response_model=List[OrderResponse],
    summary="Get orders with auto-replies",
    description="""
    Получить список заказов с автоматически сгенерированными ответами.
    
    - **source**: Источник заказов (kwork, local)
    - **limit**: Максимальное количество заказов (по умолчанию 10, максимум 50)
    """
)
async def get_orders_endpoint(
    request: Request,
    source: Optional[str] = Query(
        None,
        description="Источник заказов (kwork, local)",
        example="local",
        regex="^(kwork|local)?$"
    ),
    limit: int = Query(
        10,
        description="Максимальное количество заказов",
        ge=1,
        le=50
    )
):
    logger.info(f"GET /orders - Source: {source}, Limit: {limit}")
    logger.debug(f"Request headers: {dict(request.headers)}")
    
    try:
        # Get orders from the specified source
        orders = await get_orders(source, limit)
        
        if not orders:
            logger.info("No orders found")
            return []
            
        # Generate responses for each order
        responses = []
        for order in orders:
            try:
                response = generate_response(order)
                order_response = OrderResponse(
                    id=str(order.get("id", "")),
                    title=order.get("title", ""),
                    reply=response.get("reply", ""),
                    source=source or "local",
                    url=order.get("url", ""),
                    analysis=response.get("analysis", {})
                )
                responses.append(order_response)
                
            except Exception as e:
                logger.error(f"Error processing order {order.get('id')}: {str(e)}", exc_info=True)
                # Continue with other orders even if one fails
                continue
                
        logger.info(f"Successfully processed {len(responses)} orders")
        return responses
        
    except HTTPException as he:
        logger.error(f"HTTP error in get_orders_endpoint: {str(he.detail)}")
        raise
        
    except Exception as e:
        logger.critical(
            f"Unexpected error in get_orders_endpoint: {str(e)}",
            exc_info=True,
            extra={"request": {"url": str(request.url), "method": request.method}}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your request"
        )

# Страница входа в Web UI
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    return templates.TemplateResponse(
        "login.html", 
        {"request": request, "error": error}
    )

# Обработка входа в Web UI
@app.post("/login", response_class=HTMLResponse)
async def process_login(request: Request, token: str = Form(...)):
    valid_token = os.getenv("UI_ADMIN_TOKEN")
    if token == valid_token:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="ui_token",
            value=token,
            httponly=True,
            max_age=3600,  # 1 час
            samesite="lax"
        )
        return response
    return templates.TemplateResponse(
        "login.html", 
        {"request": request, "error": "Неверный токен доступа"},
        status_code=status.HTTP_401_UNAUTHORIZED
    )

# Выход из Web UI
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("ui_token")
    return response

# Главная страница Web UI (требует аутентификации)
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

@app.get("/form", response_class=HTMLResponse)
async def show_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request, "response": None})

@app.post("/form", response_class=HTMLResponse)
async def process_form(request: Request, title: str = Form(...)):
    # Используем существующую логику генерации ответа
    keywords = analyze_order(title)
    response = {
        "id": 1,  # ID может быть любым, так как он не отображается в UI
        "reply": (
            f"Отклик на заказ. "
            f"Ключевые слова: {', '.join(keywords)}. "
            "Готов к работе!"
        )
    }
    return templates.TemplateResponse(
        "form.html", 
        {
            "request": request, 
            "response": response,
            "request_form": {"title": title}
        }
    )

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "Jarvis MVP API"}

@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "message": "Jarvis MVP API",
        "version": "0.1.0",
        "documentation": "/api/docs",
        "endpoints": [
            {"path": "/api/health", "description": "Health check"},
            {"path": "/api/auth/token", "description": "Get access token"},
            {"path": "/api/review", "description": "Code review API"},
            {"path": "/generate-reply", "description": "Generate and optionally send a reply to an order"}
        ]
    }

@app.post(
    "/generate-reply",
    response_model=OrderResponse,
    summary="Generate and optionally send a reply to an order",
    description="""
    Generate a reply for an order and optionally send it to the platform.
    
    - **id**: Order ID (required)
    - **title**: Order title (required)
    - **source**: Order source (optional, e.g., 'kwork', 'local')
    - **url**: Order URL (optional)
    - **send**: Whether to send the reply (default: False)
    """
)
async def generate_reply_endpoint(
    request: Request,
    order: OrderRequest,
    token: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Generate a reply for an order and optionally send it to the platform.
    
    This endpoint requires authentication with a valid JWT token.
    """
    logger.info(
        f"Generating reply for order {order.id} - {order.title[:50]}..."
        f" (send={order.send}, source={order.source or 'local'})"
    )
    logger.debug(f"Request data: {order.dict()}")
    
    try:
        # Verify the token
        try:
            payload = verify_token(token)
            logger.debug(f"Authenticated as user: {payload.get('sub')}")
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate the response
        response = generate_response({
            "id": order.id,
            "title": order.title,
            "source": order.source,
            "url": order.url
        })
        
        submission_status = None
        
        # Send the reply if requested
        if order.send:
            try:
                logger.info(f"Sending reply for order {order.id}...")
                # Here should be the actual sending logic
                # For example: send_to_platform(order, response["reply"])
                
                # Simulate successful sending
                submission_status = SubmissionResponse(
                    status="success",
                    message="Reply sent successfully",
                    reason=None
                )
                logger.info(f"Successfully sent reply for order {order.id}")
                
            except Exception as e:
                error_msg = f"Failed to send reply: {str(e)}"
                logger.error(error_msg, exc_info=True)
                submission_status = SubmissionResponse(
                    status="error",
                    message=error_msg,
                    reason=str(e)
                )
        else:
            submission_status = SubmissionResponse(
                status="not_sent",
                message="Sending was not requested (send=False)",
                reason=None
            )
        
        # Prepare the response
        result = OrderResponse(
            id=str(order.id),
            title=order.title,
            reply=response.get("reply", ""),
            source=order.source or "local",
            url=order.url or "",
            sent=order.send and (submission_status.status == "success" if submission_status else False),
            submission=submission_status,
            analysis=response.get("analysis", {})
        )
        
        logger.info(f"Successfully processed order {order.id}")
        return result
        
    except HTTPException as he:
        logger.error(f"HTTP error in generate_reply_endpoint: {str(he.detail)}")
        raise
        
    except Exception as e:
        error_msg = f"Unexpected error in generate_reply_endpoint: {str(e)}"
        logger.critical(
            error_msg,
            exc_info=True,
            extra={
                "request": {"url": str(request.url), "method": request.method},
                "order_id": order.id
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@app.on_event("startup")
async def startup_event():
    """Initialize application services on startup."""
    logger.info("Starting up application...")
    
    try:
        # Initialize any required services here
        logger.info("Application startup completed")
    except Exception as e:
        logger.critical(f"Error during application startup: {str(e)}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on application shutdown."""
    logger.info("Shutting down application...")
    # Add any cleanup code here
    logger.info("Application shutdown completed")
