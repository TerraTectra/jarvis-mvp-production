"""
Утилиты для работы с заказами и генерации ответов.
"""

from typing import List, Dict, Any
import spacy

# Загрузка модели при импорте
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Если модель не загружена, загружаем её
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

__all__ = ['generate_reply', 'analyze_order']

def analyze_order(title: str) -> List[str]:
    """
    Анализирует заголовок заказа и извлекает ключевые слова.
    
    Args:
        title: Заголовок заказа
        
    Returns:
        Список ключевых слов
    """
    doc = nlp(title)
    return [
        token.lemma_ for token in doc 
        if token.pos_ in ["NOUN", "PROPN", "ADJ"]
        and not token.is_stop
    ][:5]  # Ограничиваем количество ключевых слов

def generate_reply(order: Dict[str, Any]) -> Dict[str, str]:
    """
    Генерирует ответ на заказ на основе его данных.
    
    Args:
        order: Словарь с данными заказа
        
    Returns:
        Словарь с ответом
    """
    keywords = analyze_order(order.get("title", ""))
    return {
        "id": str(order.get("id", "")),
        "title": order.get("title", ""),
        "reply": (
            f"Отклик на заказ #{order.get('id', '')}. "
            f"Ключевые слова: {', '.join(keywords)}. "
            "Готов приступить к выполнению!"
        ),
        "source": order.get("source", "local"),
        "url": order.get("url", "")
    }
