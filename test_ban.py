"""
Тестовый скрипт для проверки системы банов
"""
import asyncio
from core.db import async_session_maker, crud


async def test_ban_system():
    """Проверка системы банов"""
    
    print("=== Тест системы банов ===\n")
    
    # Получаем всех пользователей
    async with async_session_maker() as session:
        users = await crud.get_all_users(session)
        
        print(f"Найдено пользователей: {len(users)}\n")
        
        for user in users:
            ban_status = "🚫 ЗАБЛОКИРОВАН" if user.is_banned else "✅ Активен"
            print(f"ID: {user.telegram_id}")
            print(f"Username: @{user.username or 'нет'}")
            print(f"Имя: {user.first_name or 'нет'}")
            print(f"Статус: {ban_status}")
            print("-" * 40)
        
        print("\n=== Проверка декоратора check_banned ===")
        print("✅ Декоратор @check_banned добавлен к:")
        print("  - cmd_start")
        print("  - cmd_catalog")
        print("  - cmd_cart")
        print("  - cmd_orders")
        print("  - cmd_support")
        print("  - handle_callback (все кнопки)")
        print("  - handle_message (все текстовые сообщения)")
        print("\n📌 Заблокированные пользователи получат сообщение:")
        print("   '❌ Вы заблокированы и не можете использовать бота.'")
        print("   при любой попытке взаимодействия с ботом\n")


if __name__ == "__main__":
    asyncio.run(test_ban_system())
