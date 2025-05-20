"""
Selenium-based парсер для Kwork с обходом защиты.
Использует undetected-chromedriver для обхода защиты.
"""
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException,
    StaleElementReferenceException
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_kwork_date(raw_text: str) -> Optional[str]:
    """
    Парсит дату из различных форматов Kwork в ISO-формат (YYYY-MM-DD).
    
    Обрабатывает форматы:
    - "Сегодня" -> текущая дата
    - "Вчера" -> вчерашняя дата
    - "N дней/дня назад" -> дата N дней назад
    - "DD.MM.YYYY" -> стандартный формат даты
    
    Возвращает строку в формате YYYY-MM-DD или None, если не удалось распарсить.
    """
    if not raw_text or not isinstance(raw_text, str):
        return None
        
    text = raw_text.lower().strip()
    
    try:
        if "сегодня" in text:
            return datetime.today().date().isoformat()
        elif "вчера" in text:
            return (datetime.today() - timedelta(days=1)).date().isoformat()
        elif "дня назад" in text or "дней назад" in text:
            days = int(''.join(filter(str.isdigit, text.split()[0])) or 0)
            return (datetime.today() - timedelta(days=days)).date().isoformat()
        else:
            # Пробуем распарсить как дату в формате DD.MM.YYYY
            return datetime.strptime(text, "%d.%m.%Y").date().isoformat()
    except Exception as e:
        logger.debug(f"Не удалось распарсить дату '{raw_text}': {e}")
        return None


class KworkSeleniumParser:
    """Парсер для Kwork с использованием Selenium."""
    
    BASE_URL = "https://kwork.ru/projects"
    
    def __init__(self, headless: bool = True):
        """Инициализация драйвера."""
        self.options = uc.ChromeOptions()
        
        if headless:
            self.options.add_argument("--headless=new")
        
        # Настройки для маскировки под обычный браузер
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_argument("--disable-infobars")
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("--start-maximized")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--disable-notifications")
        self.options.add_argument("--disable-popup-blocking")
        self.options.add_argument("--disable-web-security")
        self.options.add_argument("--disable-extensions")
        
        # User agent для маскировки
        self.options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        self.driver = None
    
    def __enter__(self):
        """Контекстный менеджер для корректного закрытия драйвера."""
        try:
            self.driver = uc.Chrome(options=self.options)
            self.driver.maximize_window()
            return self
        except Exception as e:
            logger.error(f"Ошибка при инициализации Chrome: {e}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Закрытие драйвера при выходе из контекста."""
        if self.driver:
            self.driver.quit()
    
    def parse_project_card(self, element) -> Dict[str, Any]:
        """
        Парсит карточку проекта из HTML-элемента.
        
        Args:
            element: WebElement - элемент карточки проекта
            
        Returns:
            Словарь с данными проекта:
            {
                "title": str or None,
                "url": str or None
            }
        """
        result = {
            "title": None,
            "url": None,
            "category": None,
            "price": None
        }
        
        try:
            # 1. Пробуем найти заголовок как ссылку
            try:
                title_link = element.find_element(By.CSS_SELECTOR, 
                    "a[href*='/projects/']:not([class*='avatar']), "
                    "a[class*='title'], "
                    "h2 a, h3 a, "
                    "div[class*='header'] a"
                )
                result['title'] = title_link.text.strip()
                logger.info(f"🔹 Заголовок найден: {result['title']}")
                
                # Пробуем получить URL из заголовка
                try:
                    result['url'] = title_link.get_attribute('href')
                    if result['url']:
                        logger.info(f"🔗 URL найден в заголовке: {result['url']}")
                        # Если URL относительный, добавляем базовый домен
                        if not result['url'].startswith('http'):
                            result['url'] = 'https://kwork.ru' + result['url']
                            logger.debug(f"🔗 Преобразовали в абсолютный URL: {result['url']}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось извлечь URL из заголовка: {e}")
                
            except NoSuchElementException:
                # 2. Если не нашли как ссылку, пробуем просто заголовок
                try:
                    title_elem = element.find_element(By.CSS_SELECTOR, 
                        "h2, h3, h4, "
                        "div[class*='title'], "
                        "div[class*='name'], "
                        "div[class*='header']"
                    )
                    result['title'] = title_elem.text.strip()
                    logger.info(f"🔹 Заголовок найден (без ссылки): {result['title']}")
                    
                except NoSuchElementException:
                    logger.warning("⚠️ Заголовок не найден в карточке")
            
            # 3. Если URL еще не нашли, пробуем найти его отдельно
            if not result['url']:
                try:
                    url_element = element.find_element(By.CSS_SELECTOR, 
                        "a[href*='/projects/']:not([class*='avatar']), "
                        "a[class*='link']"
                    )
                    result['url'] = url_element.get_attribute('href')
                    if result['url']:
                        logger.info(f"🔗 URL найден отдельно: {result['url']}")
                        if not result['url'].startswith('http'):
                            result['url'] = 'https://kwork.ru' + result['url']
                            logger.debug(f"🔗 Преобразовали в абсолютный URL: {result['url']}")
                except NoSuchElementException:
                    logger.warning("⚠️ URL проекта не найден в карточке")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка при извлечении URL: {e}")
            
            # 4. Пробуем извлечь категорию
            try:
                # Логируем HTML карточки для отладки
                html_content = element.get_attribute('outerHTML')
                logger.debug(f"HTML карточки: {html_content[:500]}...")
                
                # Сохраняем HTML во временный файл для анализа
                import os
                import uuid
                
                # Создаем директорию для логов, если её нет
                os.makedirs('kwork_debug', exist_ok=True)
                
                # Генерируем уникальное имя файла
                filename = f"kwork_debug/card_{str(uuid.uuid4())[:8]}.html"
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"<!-- Title: {result.get('title', 'no-title')} -->\n")
                    f.write(f"<!-- URL: {result.get('url', 'no-url')} -->\n\n")
                    f.write(html_content)
                
                logger.info(f"Сохранен HTML карточки в {filename}")
                
                # Пробуем извлечь категорию из HTML с помощью BeautifulSoup
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Пробуем найти категорию в различных местах
                    category = None
                    
                    # 1. Ищем по классам, которые могут содержать категорию
                    for tag in soup.find_all(class_=True):
                        class_name = ' '.join(tag.get('class', []))
                        if 'category' in class_name.lower() and tag.text.strip():
                            category = tag.text.strip()
                            logger.info(f"Найдена категория через класс '{class_name}': {category}")
                            break
                    
                    # 2. Ищем по тексту, похожему на категорию
                    if not category:
                        for tag in soup.find_all(text=True):
                            text = tag.strip()
                            if (2 < len(text) < 50 and 
                                not any(c.isdigit() for c in text) and 
                                not any(word in text.lower() for word in ['kwork', 'проект', 'заказ', 'показать', 'полностью'])):
                                category = text
                                logger.info(f"Найдена категория по тексту: {category}")
                                break
                    
                    if category:
                        result['category'] = category
                        logger.info(f"🏷️  Категория найдена через BeautifulSoup: {category}")
                        return result
                        
                except Exception as e:
                    logger.warning(f"Ошибка при парсинге HTML с BeautifulSoup: {e}")
                
                # Пробуем разные селекторы для категории (обновленные селекторы)
                category_selectors = [
                    # 1. Приоритетные селекторы для категорий (наиболее точные)
                    "a[href^='/categories/']:not([class*='avatar']):not([class*='link']):not([class*='btn'])",
                    "a[href*='kwork.ru/categories/']:not([class*='avatar']):not([class*='link']):not([class*='btn'])",
                    
                    # 2. Селекторы из верхней части карточки (обычно там категория)
                    "div[class*='wants-card__left'] > a:not([class*='avatar']):first-child",
                    "div[class*='wants-card__left'] > div:first-child:not([class*='avatar'])",
                    "div[class*='wants-card__left'] > span:first-child:not([class*='avatar'])",
                    
                    # 3. Селекторы категорий с атрибутами data-test-id
                    "[data-test-id='category-name']",
                    "[data-test-id='project-category']",
                    
                    # 4. Общие селекторы категорий
                    "div[class*='category']:not([class*='avatar']):not([class*='link'])",
                    "span[class*='category']:not([class*='avatar']):not([class*='link'])",
                    "div[class*='project-category']:not([class*='avatar'])",
                    "div[class*='project-type']:not([class*='avatar'])",
                    "div[class*='service-type']:not([class*='avatar'])",
                    
                    # 5. Селекторы тегов (менее приоритетные)
                    "div[class*='tag']:not([class*='avatar']):not([class*='link'])",
                    "span[class*='tag']:not([class*='avatar']):not([class*='link'])",
                    
                    # 6. Дополнительные селекторы (наименее приоритетные)
                    "div[class*='type']:not([class*='avatar']):not([class*='link'])",
                    "span[class*='type']:not([class*='avatar']):not([class*='link'])",
                    
                    # 7. Ищем по тексту, который не похож на заголовок
                    "div:not([class*='title']):not([class*='header']) > span:only-child",
                    "div:not([class*='title']):not([class*='header']) > div:only-child",
                    
                    # 8. Крайний случай - ищем любой текст в левой части карточки
                    "div[class*='wants-card__left'] > *:first-child:not([class*='avatar'])",
                    
                    # 9. Ищем любые элементы с текстом, которые могут быть категорией
                    "*:not(script):not(style):not(link):not(meta):not(noscript):not(svg)"
                ]
                
                # 10. Пробуем извлечь бюджет
                try:
                    price_selectors = [
                        # Приоритетные селекторы для цены
                        ".project-price",
                        ".price",
                        "[data-test='price']",
                        "[data-test-id='price']",
                        "div[class*='price']",
                        "span[class*='price']",
                        "div[class*='budget']",
                        "span[class*='budget']",
                        "div[class*='cost']",
                        "span[class*='cost']",
                        "div[class*='wants-card__price']",
                        "div[class*='wants-card__budget']",
                        "div[class*='wants-card__cost']",
                        "div[class*='project-card__price']"
                    ]
                    
                    for selector in price_selectors:
                        try:
                            price_elem = element.find_element(By.CSS_SELECTOR, selector)
                            price_text = price_elem.text.strip()
                            
                            if price_text:
                                # Нормализуем текст цены
                                price_text = self._normalize_price(price_text)
                                if price_text:
                                    result['price'] = price_text
                                    logger.info(f"💰 Найдена цена: {price_text}")
                                    break
                                    
                        except NoSuchElementException:
                            continue
                            
                    if not result['price']:
                        logger.warning("⚠️ Бюджет не найден")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка при извлечении цены: {e}")
                
                for selector in category_selectors:
                    try:
                        category_elem = element.find_element(By.CSS_SELECTOR, selector)
                        category_text = category_elem.text.strip()
                        if category_text and 2 < len(category_text) < 100:  # Проверка на разумную длину
                            # Нормализуем текст для сравнения
                            normalized_text = category_text.lower().strip()
                            logger.info(f"Найден текст категории: '{category_text}' (селектор: {selector})")
                            
                            # Список нежелательных текстов
                            skip_words = [
                                'kwork', 'проект', 'заказ', 'показать', 'полностью',
                                'открыть', 'подробнее', 'еще', 'смотреть', 'читать',
                                'развернуть', 'свернуть', 'скрыть', 'показать еще'
                            ]
                            
                            # Пропускаем, если:
                            # 1. Это число (возможно, ID заказа)
                            # 2. Содержит стоп-слова
                            # 3. Совпадает с заголовком
                            # 4. Текст слишком короткий или слишком длинный
                            # 5. Содержит нежелательные слова
                            if (not normalized_text.isdigit() and 
                                len(normalized_text) > 2 and 
                                len(normalized_text) < 50 and
                                not any(word in normalized_text for word in skip_words) and
                                normalized_text != result['title'].lower().strip() and
                                not normalized_text.startswith(('http', 'www'))):
                                
                                result['category'] = category_text
                                logger.info(f"🏷️  Категория найдена: {result['category']}")
                                break
                    except NoSuchElementException:
                        continue
                
                if not result['category']:
                    logger.warning("⚠️ Категория не найдена в карточке")
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при извлечении категории: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при парсинге карточки: {str(e)}", exc_info=True)
            
        return result
    
    def fetch_orders(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Получает список заказов с Kwork.
        
        Args:
            limit: Максимальное количество заказов для получения
            
        Returns:
            Список словарей с информацией о заказах
        """
        if not self.driver:
            logger.error("Драйвер не инициализирован")
            return []
        
        try:
            logger.info(f"Загрузка страницы {self.BASE_URL}")
            self.driver.get(self.BASE_URL)
            
            # Проверяем на капчу
            if self._check_captcha():
                logger.warning("Обнаружена капча. Требуется ручное вмешательство.")
                return []
            
            # Ожидаем загрузки контента
            self._wait_for_content_load()
            
            # Прокручиваем страницу для загрузки дополнительных карточек
            self._scroll_page()
            
            # Находим все карточки проектов
            project_elements = self._find_project_cards()
            
            if not project_elements:
                logger.warning("Не найдено ни одной карточки проекта")
                return []
            
            # Парсим карточки
            projects = []
            for i, element in enumerate(project_elements[:limit], 1):
                try:
                    project = self.parse_project_card(element)
                    if project:
                        projects.append(project)
                        logger.info(f"Успешно распарсена карточка {i}/{min(limit, len(project_elements))}")
                except Exception as e:
                    logger.error(f"Ошибка при парсинге карточки {i}: {e}")
            
            return projects
            
        except Exception as e:
            logger.error(f"Ошибка при получении заказов: {e}")
            return []
    
    def _check_captcha(self) -> bool:
        """Проверяет наличие капчи на странице."""
        try:
            # Проверяем наличие iframe с капчей
            captcha_frame = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='captcha']")
            return len(captcha_frame) > 0
        except:
            return False
    
    def _wait_for_content_load(self, timeout: int = 20):
        """Ожидает загрузки контента на странице."""
        try:
            # Ожидаем появления хотя бы одной карточки проекта
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='card']"))
            )
            logger.info("Контент страницы успешно загружен")
        except TimeoutException:
            logger.warning("Таймаут ожидания загрузки контента")
    
    def _scroll_page(self, scroll_pause_time: float = 1.0):
        """Прокручивает страницу вниз для загрузки дополнительного контента."""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            while True:
                # Прокручиваем вниз
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # Ждем загрузки контента
                time.sleep(scroll_pause_time)
                
                # Вычисляем новую высоту прокрутки и сравниваем с предыдущей
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
                
        except Exception as e:
            logger.warning(f"Ошибка при прокрутке страницы: {e}")
    
    def _normalize_price(self, price_text: str) -> Optional[str]:
        """
        Нормализует текст с ценой, оставляя только цифры и разделители.
        
        Args:
            price_text: Исходный текст с ценой
            
        Returns:
            Нормализованная строка с ценой или None, если цена невалидна
        """
        if not price_text:
            return None
            
        try:
            # Удаляем лишние пробелы и переносы строк
            price_text = ' '.join(price_text.split())
            
            # Удаляем валюту и лишние символы, но сохраняем цифры, пробелы, тире и запятые
            import re
            price_text = re.sub(r'[^\d\s\-,.\u00A0]', '', price_text, flags=re.UNICODE)
            
            # Заменяем множественные пробелы на один
            price_text = re.sub(r'\s+', ' ', price_text).strip()
            
            # Если получили пустую строку после очистки
            if not price_text:
                return None
                
            return price_text
            
        except Exception as e:
            logger.warning(f"Ошибка при нормализации цены '{price_text}': {e}")
            return None
    
    def _find_project_cards(self):
        """Находит карточки проектов на странице."""
        try:
            # Ищем карточки по различным селекторам
            selectors = [
                "div[class*='card']",
                "div[class*='wants-card']",
                "div[class*='project']",
                "div[class*='item']"
            ]
            
            for selector in selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logger.info(f"Найдено {len(elements)} элементов с селектором: {selector}")
                    return elements
            
            logger.warning("Не удалось найти карточки проектов")
            return []
            
        except Exception as e:
            logger.error(f"Ошибка при поиске карточек проектов: {e}")
            return []


def test_parser():
    """Тестирование парсера."""
    try:
        with KworkSeleniumParser(headless=True) as parser:
            projects = parser.fetch_orders(limit=3)
            
            print("\n" + "=" * 50)
            print(f"Успешно получено заказов: {len(projects)}")
            print("=" * 50 + "\n")
            
            for i, project in enumerate(projects, 1):
                print(f"--- Заказ #{i} ---")
                print(f"Название: {project.get('title', 'Нет названия')}")
                print(f"URL: {project.get('url', 'Не указан')}")
                print(f"Категория: {project.get('category', 'Не указана')}")
                print(f"Бюджет: {project.get('price', 'Не указан')}")
                print("------------------------------")
                
    except Exception as e:
        print(f"Ошибка при тестировании парсера: {e}")


if __name__ == "__main__":
    test_parser()
