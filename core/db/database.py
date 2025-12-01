"""
Подключение к базе данных и функции инициализации
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from .models import Base, User, Model, Product, Cart, Order, OrderItem, BotSettings
from datetime import datetime
import os


# Получаем имя БД из .env
DB_NAME = os.getenv('DB_NAME', 'cloud_supply.db')
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

# Создаем асинхронный движок
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
engine = create_async_engine(DATABASE_URL, echo=False)

# Создаем фабрику сессий
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """
    Инициализация базы данных - создание всех таблиц
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаем дефолтные настройки бота
    async with async_session_maker() as session:
        # Проверяем есть ли настройки
        result = await session.execute(select(BotSettings).where(BotSettings.setting_key == 'welcome_message'))
        existing = result.scalar_one_or_none()
        
        if not existing:
            # Создаем дефолтные настройки
            default_settings = [
                BotSettings(
                    setting_key='welcome_message',
                    setting_value='☁️ Добро пожаловать в Cloud Supply!\n\nВыберите модель вейпа и наслаждайтесь лучшими вкусами! 💨'
                ),
                BotSettings(
                    setting_key='support_message',
                    setting_value='📞 Свяжитесь с поддержкой Cloud Supply: @cloud_supplier'
                )
            ]
            
            session.add_all(default_settings)
            await session.commit()
    
    print("✅ База данных инициализирована!")


async def get_session() -> AsyncSession:
    """
    Получить сессию для работы с БД
    """
    return async_session_maker()


async def close_db():
    """
    Закрыть соединение с БД
    """
    await engine.dispose()
    print("✅ Соединение с БД закрыто!")
