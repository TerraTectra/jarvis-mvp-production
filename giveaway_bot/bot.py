from config import load_token

TELEGRAM_BOT_TOKEN = load_token()

if not TELEGRAM_BOT_TOKEN:
    print("Токен Telegram не был предоставлен. Выход.")
    exit()

print(f"Токен получен: {TELEGRAM_BOT_TOKEN[:6]}...") # Выводим только часть токена для безопасности

import logging
import random # Added import
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Включаем логирование, чтобы видеть ошибки и информацию о работе бота
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Словарь для хранения активных розыгрышей.
# Ключ: chat_id, Значение: {'prize': 'название приза', 'participants': {user_id: username}, 'creator_id': user.id}
giveaways = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение в ответ на команду /start."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Привет, {user.mention_html()}! Я бот для проведения розыгрышей. Пока я в разработке.",
    )
    logger.info(f"Пользователь {user.id} ({user.username}) вызвал команду /start")

async def new_giveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает новый розыгрыш в текущем чате."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id in giveaways:
        await update.message.reply_text("В этом чате уже идет розыгрыш! Сначала завершите текущий с помощью /draw_winner.")
        return

    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите название приза после команды. Пример: /new_giveaway Кружка")
        return

    prize = " ".join(context.args)
    giveaways[chat_id] = {'prize': prize, 'participants': {}, 'creator_id': user.id}

    logger.info(f"Пользователь {user.id} ({user.username}) начал новый розыгрыш '{prize}' в чате {chat_id}.")
    await update.message.reply_text(f"🎉 Новый розыгрыш начался! Приз: {prize}\nДля участия используйте команду /enter")

async def enter_giveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Позволяет пользователю присоединиться к текущему розыгрышу."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    if chat_id not in giveaways:
        await update.message.reply_text("В этом чате сейчас нет активных розыгрышей. Попросите администратора начать новый с помощью /new_giveaway.")
        return

    current_giveaway = giveaways[chat_id]
    if user.id in current_giveaway['participants']:
        await update.message.reply_text("Вы уже участвуете в этом розыгрыше!")
        return

    current_giveaway['participants'][user.id] = user.username or user.first_name # Сохраняем username или first_name
    logger.info(f"Пользователь {user.id} ({user.username or user.first_name}) присоединился к розыгрышу '{current_giveaway['prize']}' в чате {chat_id}.")
    await update.message.reply_text(f"Отлично, {user.mention_html()}, вы присоединились к розыгрышу приза: {current_giveaway['prize']}!")

async def draw_winner_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Определяет победителя текущего розыгрыша."""
    chat_id = update.effective_chat.id
    user = update.effective_user # Пользователь, вызвавший команду

    if chat_id not in giveaways:
        await update.message.reply_text("В этом чате сейчас нет активных розыгрышей.")
        return

    current_giveaway = giveaways[chat_id]

    # Простое ограничение: только создатель розыгрыша может его завершить
    # В будущем можно добавить проверку на администратора чата
    # if user.id != current_giveaway.get('creator_id'):
    #     await update.message.reply_text("Только тот, кто начал розыгрыш, может определить победителя.")
    #     return

    participants_map = current_giveaway['participants']
    if not participants_map:
        await update.message.reply_text("В розыгрыше пока нет участников! Никто не может выиграть.")
        return

    winner_id = random.choice(list(participants_map.keys()))
    winner_username = participants_map[winner_id]

    prize = current_giveaway['prize']
    logger.info(f"В розыгрыше '{prize}' в чате {chat_id} определен победитель: {winner_id} ({winner_username}). Розыгрыш завершен.")

    # Упоминаем победителя, если username доступен, иначе просто ID
    winner_mention = f"@{winner_username}" if winner_username else f"пользователь с ID {winner_id}"

    await update.message.reply_text(
        f"🎉 Поздравляем победителя розыгрыша \"{prize}\"!\n"
        f"И это... {winner_mention}!\n\n"
        "Розыгрыш завершен."
    )

    # Удаляем завершенный розыгрыш
    del giveaways[chat_id]

def main() -> None:
    """Запускает бота."""
    # Создаем Application и передаем ему токен бота.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Регистрируем обработчик команды /start
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new_giveaway", new_giveaway_command))
    application.add_handler(CommandHandler("enter", enter_giveaway_command)) # Added handler
    application.add_handler(CommandHandler("draw_winner", draw_winner_command)) # Added handler

    # Запускаем бота до тех пор, пока пользователь не нажмет Ctrl-C
    logger.info("Запуск бота...")
    application.run_polling()

if __name__ == '__main__':
    main()
