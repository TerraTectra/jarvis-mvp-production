import os

def load_token():
    """
    Загружает токен Telegram.
    Сначала пытается прочитать его из переменной окружения TELEGRAM_TOKEN.
    Если не найден, запрашивает у пользователя.
    """
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        print("Переменная окружения TELEGRAM_TOKEN не найдена.")
        token = input("Пожалуйста, введите ваш токен Telegram: ").strip()
    return token

if __name__ == '__main__':
    # Для тестирования функции
    print(f"Загруженный токен: {load_token()}")
