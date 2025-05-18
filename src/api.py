from fastapi import FastAPI, Request, HTTPException, Form, Depends, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import asyncio
from pathlib import Path
import logging

from integrations.kwork import fetch_kwork_orders
from utils import generate_reply, analyze_order

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI()

# Настройка шаблонов
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Мок-данные заказов
MOCK_ORDERS = [
    {"id": 1, "title": "Need Python developer for automation"},
    {"id": 2, "title": "Web scraping with BeautifulSoup"},
    {"id": 3, "title": "Telegram bot in Python"},
    {"id": 4, "title": "Landing page HTML/CSS"},
    {"id": 5, "title": "Data analysis with Python"},
]

# Pydantic модели
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



# Мок-данные заказов
MOCK_ORDERS = [
    {"id": 1, "title": "Need Python developer for automation"},
    {"id": 2, "title": "Web scraping with BeautifulSoup"},
    {"id": 3, "title": "Telegram bot in Python"},
    {"id": 4, "title": "Landing page HTML/CSS"},
    {"id": 5, "title": "Data analysis with Python"},
]

def analyze_order(title: str) -> List[str]:
    """Анализ заголовка заказа"""
    doc = nlp(title)
    return [token.lemma_ for token in doc 
            if token.pos_ in ["NOUN", "PROPN", "ADJ"]
            and not token.is_stop]

def generate_response(order: Dict[str, Any]) -> Dict[str, Any]:
    """Генерация ответа на заказ"""
    keywords = analyze_order(order["title"])
    return {
        "id": order["id"],
        "title": order["title"],
        "reply": f"Отклик на заказ #{order['id']}. "
                f"Ключевые слова: {', '.join(keywords)}. "
                "Готов приступить к выполнению!"
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
    if source == "kwork":
        try:
            return await fetch_kwork_orders(limit)
        except Exception as e:
            logger.error(f"Ошибка при получении заказов с Kwork: {e}")
            return []
    else:
        # Возвращаем моковые данные
        return MOCK_ORDERS[:limit] if limit < len(MOCK_ORDERS) else MOCK_ORDERS

@app.get("/orders", response_model=List[OrderResponse])
async def get_orders_endpoint(
    source: Optional[str] = Query(
        None,
        description="Источник заказов (kwork, local)",
        example="kwork"
    ),
    limit: int = Query(
        10,
        description="Максимальное количество заказов",
        ge=1,
        le=50
    )
):
    """
    Получить список заказов с автоответами.
    
    - **source**: Источник заказов (kwork, local)
    - **limit**: Максимальное количество заказов (по умолчанию 10, максимум 50)
    """
    orders = await get_orders(source, limit)
    return [generate_reply(order) for order in orders]

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

@app.get("/api")
async def api_info():
    return {"message": "Jarvis MVP API работает. Используйте /orders или /reply"}

@app.post("/reply", response_model=OrderResponse)
async def generate_reply_endpoint(order: OrderRequest):
    """
    Сгенерировать ответ на заказ и отправить его, если требуется.
    
    - **id**: ID заказа
    - **title**: Заголовок заказа
    - **source**: Источник заказа (опционально)
    - **url**: Ссылка на заказ (опционально)
    - **send**: Отправить отклик (по умолчанию False)
    """
    from integrations.kwork_submission import submit_kwork_reply
    
    # Генерируем ответ
    response_data = generate_reply(order.dict())
    
    # Если нужно отправить и это Kwork
    if order.send and order.source == "kwork":
        try:
            submission_result = await submit_kwork_reply(
                order_id=str(order.id),
                message=response_data["reply"]
            )
            
            # Обновляем ответ данными об отправке
            response_data["sent"] = submission_result["status"] == "ok"
            response_data["submission"] = {
                "status": submission_result["status"],
                "message": submission_result.get("message"),
                "reason": submission_result.get("reason")
            }
            
            logger.info(f"Отклик на заказ {order.id} {'успешно отправлен' if response_data['sent'] else 'не отправлен'}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке отклика: {e}")
            response_data["sent"] = False
            response_data["submission"] = {
                "status": "error",
                "reason": str(e)
            }
    
    return response_data
