"""
Главный модуль бота Cloud Supply
Инициализация и запуск бота
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import os

# Загружаем переменные окружения из core/.env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")

# Импортируем handlers
from .handlers import user, admin

# Импортируем БД
from .db import init_db, close_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Инициализация после запуска"""
    await init_db()
    logger.info("✅ База данных инициализирована")


async def post_shutdown(application: Application):
    """Очистка после остановки"""
    await close_db()
    logger.info("👋 База данных закрыта")


def main():
    """
    Главная функция для запуска бота
    """
    # Проверка токена
    if not API_TOKEN:
        logger.error("❌ TELEGRAM_API_TOKEN не найден в .env файле!")
        return
    
    logger.info("🚀 Запуск Cloud Supply Bot...")
    
    # Создаем приложение
    application = Application.builder().token(API_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    
    # Регистрируем handlers (user)
    application.add_handler(CommandHandler("start", user.cmd_start))
    application.add_handler(CommandHandler("catalog", user.cmd_catalog))
    application.add_handler(CommandHandler("cart", user.cmd_cart))
    application.add_handler(CommandHandler("orders", user.cmd_orders))
    application.add_handler(CommandHandler("support", user.cmd_support))
    application.add_handler(CommandHandler("clear", user.cmd_clear))  # Скрытая команда
    
    # Регистрируем handlers (admin)
    application.add_handler(CommandHandler("admin", admin.cmd_admin))
    application.add_handler(CommandHandler("fix_orders", admin.cmd_fix_orders))  # Скрытая команда для исправления дубликатов
    application.add_handler(CommandHandler("reset_db", admin.cmd_reset_db))  # Скрытая команда для очистки БД
    
    # Callback handlers (порядок важен - сначала админские, потом пользовательские)
    application.add_handler(CallbackQueryHandler(admin.handle_admin_callback, pattern=r"^admin_|^change_status_|^setstatus_|^select_model_|^view_|^confirm_delete_|^confirm_reset_db|^delete_order_|^edit_"))
    application.add_handler(CallbackQueryHandler(user.handle_callback))
    
    # Message handlers для FSM
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user.handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, admin.handle_photo))
    
    logger.info("✅ Бот запущен и готов к работе!")
    
    # Запускаем polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


def run():
    """
    Функция для запуска бота (вызывается из bot.py)
    """
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⚠️ Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")