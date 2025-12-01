"""
Админ handlers для python-telegram-bot
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, delete
import os
import shutil
import asyncio
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

# Загружаем .env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

from ..db import crud, async_session_maker
from ..db.models import OrderItem, User
from ..keyboards.inline import (
    get_admin_panel_kb, get_admin_products_kb, get_admin_users_kb,
    get_admin_user_actions_kb, get_orders_kb, get_order_detail_kb, get_order_status_kb
)


def is_admin(username: str) -> bool:
    """Проверка прав админа"""
    admin_username = os.getenv('ADMIN_USERNAME', '')
    support_username = os.getenv('SUPPORT_USERNAME', '')
    return username in [admin_username, support_username]


def admin_required(func):
    """Декоратор для проверки прав админа"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Получаем username из update (может быть callback_query или message)
        if update.callback_query:
            username = update.callback_query.from_user.username
        elif update.message:
            username = update.message.from_user.username
        else:
            username = update.effective_user.username
        
        if not is_admin(username):
            # Отправляем сообщение об ошибке
            if update.callback_query:
                await update.callback_query.answer("❌ Нет прав администратора!", show_alert=True)
            elif update.message:
                await update.message.reply_text("❌ У вас нет прав администратора!")
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper


# ==================== КОМАНДЫ ====================

@admin_required
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin"""
    # Удаляем команду
    try:
        await update.message.delete()
    except:
        pass
    
    # Удаляем предыдущее сообщение бота (меню магазина)
    if 'last_bot_message' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['last_bot_message']
            )
        except:
            pass
    
    context.user_data.clear()  # Очищаем состояние
    text = "⚙️ Админ-панель Cloud Supply"
    msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=get_admin_panel_kb()
    )
    context.user_data['last_bot_message'] = msg.message_id


# ==================== CALLBACK HANDLERS ====================

@admin_required
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик админ callbacks"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # Админ панель
    if data == "admin_panel":
        await show_admin_panel(query, context)
    
    # Заказы
    elif data == "admin_orders":
        await show_admin_orders(query, context)
    elif data.startswith("change_status_"):
        await change_order_status_menu(query, context)
    elif data.startswith("setstatus_"):
        await set_order_status(query, context)
    elif data.startswith("delete_order_"):
        await delete_order_confirm(query, context)
    
    # Товары
    elif data == "admin_products":
        context.user_data.clear()  # Очищаем состояние
        await show_admin_products(query, context)
    elif data == "admin_add_model":
        await start_add_model(query, context)
    elif data == "admin_add_product":
        await start_add_product(query, context)
    
    # Просмотр моделей и вкусов
    elif data == "admin_view_models":
        await show_models_list(query, context)
    elif data.startswith("view_model_"):
        await show_model_detail(query, context)
    elif data.startswith("view_flavors_"):
        await show_model_flavors(query, context)
    elif data.startswith("view_flavor_detail_"):
        await show_flavor_detail(query, context)
    elif data.startswith("edit_flavor_price_"):
        await start_edit_flavor_price(query, context)
    elif data.startswith("edit_flavor_stock_"):
        await start_edit_flavor_stock(query, context)
    elif data.startswith("edit_model_description_"):
        await start_edit_model_description(query, context)
    elif data.startswith("confirm_delete_model_"):
        await confirm_delete_model(query, context)
    elif data.startswith("confirm_delete_flavor_"):
        await confirm_delete_flavor(query, context)
    elif data.startswith("select_model_"):
        await select_model_for_product(query, context)
    elif data.startswith("admin_delete_model_"):
        await delete_model_confirm(query, context)
    elif data.startswith("admin_delete_product_"):
        await delete_product_confirm(query, context)
    
    # Пользователи
    elif data == "admin_users":
        await show_admin_users(query, context)
    elif data.startswith("admin_user_"):
        await show_admin_user_detail(query, context)
    elif data.startswith("admin_ban_"):
        await admin_ban_user(query, context)
    elif data.startswith("admin_unban_"):
        await admin_unban_user(query, context)
    
    # Статистика
    elif data == "admin_stats":
        await show_admin_stats(query, context)
    
    # Очистка базы
    elif data == "confirm_reset_db":
        await confirm_reset_db(query, context)
    
    # Бэкап
    elif data == "admin_backup":
        await admin_backup_db(query, context)


async def show_admin_panel(query, context):
    """Админ панель"""
    context.user_data.clear()  # Очищаем состояние
    text = "⚙️ Админ-панель"
    await query.edit_message_text(text, reply_markup=get_admin_panel_kb())


async def show_admin_orders(query, context):
    """Все заказы"""
    async with async_session_maker() as session:
        orders = await crud.get_all_orders(session)
        
        if not orders:
            await query.edit_message_text("📦 Заказов нет", reply_markup=get_admin_panel_kb())
        else:
            # Собираем данные о пользователях
            orders_with_users = []
            for order in orders:
                user_result = await session.execute(select(User).where(User.id == order.user_id))
                user = user_result.scalar_one_or_none()
                orders_with_users.append((order, user))
            
            await query.edit_message_text(f"📦 Всего заказов: {len(orders)}", reply_markup=get_orders_kb(orders_with_users))


async def change_order_status_menu(query, context):
    """Меню изменения статуса"""
    order_id = int(query.data.split("_")[2])
    
    text = f"📦 Изменение статуса заказа #{order_id}"
    await query.edit_message_text(text, reply_markup=get_order_status_kb(order_id))


async def set_order_status(query, context):
    """Установить статус заказа"""
    parts = query.data.split("_")
    order_id = int(parts[1])
    new_status = parts[2]
    
    async with async_session_maker() as session:
        await crud.update_order_status(session, order_id, new_status)
    
    status_text = {
        'processing': 'В процессе',
        'completed': 'Готов'
    }.get(new_status, 'Неизвестно')
    
    await query.answer(f"✅ Статус: {status_text}", show_alert=True)
    
    # Показываем детали заказа
    async with async_session_maker() as session:
        order = await crud.get_order_by_id(session, order_id)
        user_result = await session.execute(select(User).where(User.id == order.user_id))
        user = user_result.scalar_one_or_none()
        
        status_emoji = {
            'processing': '📦',
            'completed': '✅'
        }.get(order.status, '❓')
        
        delivery_text = "🚚 Доставка" if order.delivery_method == "delivery" else "🏃 Самовывоз"
        
        text = f"📋 Заказ #{order.id}\n\n"
        text += f"👤 Пользователь: {user.username or user.first_name}\n"
        text += f"📞 Контакт: {order.contact_info}\n"
        text += f"{delivery_text}\n"
        text += f"Статус: {status_emoji} {status_text}\n"
        text += f"Сумма: {order.total_price}€"
        
        await query.edit_message_text(text, reply_markup=get_order_detail_kb(order_id, is_admin=True))


async def show_admin_products(query, context):
    """Управление товарами"""
    async with async_session_maker() as session:
        models = await crud.get_all_models(session, available_only=False)
        
        text = f"📦 Управление товарами\n\nМоделей: {len(models)}"
        await query.edit_message_text(text, reply_markup=get_admin_products_kb())


async def show_admin_users(query, context):
    """Список пользователей"""
    async with async_session_maker() as session:
        users = await crud.get_all_users(session)
        
        if not users:
            await query.edit_message_text("👥 Пользователей нет", reply_markup=get_admin_panel_kb())
        else:
            text = f"👥 Всего пользователей: {len(users)}"
            await query.edit_message_text(text, reply_markup=get_admin_users_kb(users))


async def show_admin_user_detail(query, context):
    """Детали пользователя"""
    user_id = int(query.data.split("_")[2])
    
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await query.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        status = "🚫 Заблокирован" if user.is_banned else "✅ Активен"
        
        text = f"👤 Пользователь #{user.id}\n\n"
        text += f"Telegram ID: {user.telegram_id}\n"
        text += f"Username: @{user.username or 'нет'}\n"
        text += f"Имя: {user.first_name or 'нет'}\n"
        text += f"Статус: {status}"
        
        await query.edit_message_text(text, reply_markup=get_admin_user_actions_kb(user_id, user.is_banned))


async def admin_ban_user(query, context):
    """Забанить пользователя"""
    user_id = int(query.data.split("_")[2])
    
    async with async_session_maker() as session:
        await crud.ban_user(session, user_id, ban=True)
    
    await query.answer("✅ Пользователь заблокирован", show_alert=True)
    await show_admin_users(query, context)


async def admin_unban_user(query, context):
    """Разбанить пользователя"""
    user_id = int(query.data.split("_")[2])
    
    async with async_session_maker() as session:
        await crud.ban_user(session, user_id, ban=False)
    
    await query.answer("✅ Пользователь разблокирован", show_alert=True)
    await show_admin_users(query, context)


async def delete_order_confirm(query, context):
    """Удаление заказа"""
    order_id = int(query.data.split("_")[2])
    
    async with async_session_maker() as session:
        success = await crud.delete_order(session, order_id)
        
        if success:
            await query.answer("✅ Заказ удален, товары возвращены на склад", show_alert=True)
        else:
            await query.answer("❌ Ошибка при удалении заказа", show_alert=True)
    
    await show_admin_orders(query, context)


async def show_admin_stats(query, context):
    """Статистика"""
    async with async_session_maker() as session:
        revenue_data = await crud.get_revenue_and_profit(session)
        orders_count = await crud.get_total_orders_count(session)
        users = await crud.get_all_users(session)
        top_products = await crud.get_top_products(session, limit=5)
        
        text = "📊 Статистика Cloud Supply\n\n"
        text += f"💰 Выручка: {revenue_data['revenue']:.2f}€\n"
        text += f"💸 Себестоимость: {revenue_data['cost']:.2f}€\n"
        text += f"💵 Прибыль: {revenue_data['profit']:.2f}€\n\n"
        text += f"📦 Заказов: {orders_count}\n"
        text += f"👥 Пользователей: {len(users)}\n\n"
        
        if top_products:
            text += "🏆 Топ товаров:\n"
            for i, item in enumerate(top_products, 1):
                product = item['product']
                model = await crud.get_model_by_id(session, product.model_id)
                text += f"{i}. {model.name} - {product.flavor_name} ({item['total_sold']} шт)\n"
        
        await query.edit_message_text(text, reply_markup=get_admin_panel_kb())


async def admin_backup_db(query, context):
    """Бэкап БД"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', os.getenv('DB_NAME', 'cloud_supply.db'))
    
    if not os.path.exists(db_path):
        await query.answer("❌ БД не найдена!", show_alert=True)
        return
    
    await query.message.reply_text("📥 Создаю бэкап...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    with open(db_path, 'rb') as db_file:
        await query.message.reply_document(
            document=db_file,
            filename=f"cloud_supply_backup_{timestamp}.db",
            caption=f"💾 Бэкап БД\n{timestamp}"
        )
    
    await query.answer("✅ Бэкап создан!", show_alert=True)


# ==================== ДОБАВЛЕНИЕ МОДЕЛИ (ПОСЛЕДОВАТЕЛЬНО) ====================

async def start_add_model(query, context):
    """Начало добавления модели - запрос названия"""
    context.user_data['state'] = 'awaiting_model_name'
    await query.edit_message_text(
        "➕ Добавление новой модели\n\n"
        "Шаг 1/3: Введите название модели:\n"
        "(например: ELFBAR 5000)",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_products")]])
    )


@admin_required
async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений от админа в процессе добавления"""
    state = context.user_data.get('state')
    
    # Добавление модели - шаг 1: название
    if state == 'awaiting_model_name':
        model_name = update.message.text.strip()
        if len(model_name) < 2:
            await update.message.reply_text("❌ Название слишком короткое. Попробуйте еще раз:")
            return
        
        context.user_data['model_name'] = model_name
        context.user_data['state'] = 'awaiting_model_description'
        
        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Название: {model_name}\n\n"
            "Шаг 2/3: Введите описание модели:\n"
            "(или напишите '-' если описание не нужно)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_products")]])
        )
    
    # Добавление модели - шаг 2: описание
    elif state == 'awaiting_model_description':
        description = update.message.text.strip()
        if description == '-':
            description = ''
        
        context.user_data['model_description'] = description
        context.user_data['state'] = 'awaiting_model_cost'
        
        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Описание: {description if description else 'не указано'}\n\n"
            "Шаг 3/3: Введите себестоимость (€):\n"
            "(например: 2.5)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_products")]])
        )
    
    # Добавление модели - шаг 3: себестоимость
    elif state == 'awaiting_model_cost':
        try:
            cost_price = float(update.message.text.strip().replace(',', '.'))
            if cost_price < 0:
                await update.message.reply_text("❌ Себестоимость не может быть отрицательной. Попробуйте еще раз:")
                return
            
            # Создаем модель
            model_name = context.user_data.get('model_name')
            model_description = context.user_data.get('model_description', '')
            
            async with async_session_maker() as session:
                new_model = await crud.create_model(
                    session,
                    name=model_name,
                    description=model_description,
                    cost_price=cost_price
                )
                
                text = f"✅ Модель создана!\n\n"
                text += f"📱 Название: {new_model.name}\n"
                if new_model.description:
                    text += f"📝 Описание: {new_model.description}\n"
                text += f"💰 Себестоимость: {new_model.cost_price}€\n"
                text += f"🆔 ID: {new_model.id}\n\n"
                text += "📸 Теперь отправьте фото модели\n"
                text += "(или напишите '-' чтобы пропустить)"
                
                # Сохраняем ID модели для загрузки фото
                context.user_data['model_id'] = new_model.id
                context.user_data['state'] = 'awaiting_model_photo'
                
                # Удаляем сообщение пользователя
                try:
                    await update.message.delete()
                except:
                    pass
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Пропустить", callback_data="admin_products")]])
                )
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат числа. Введите себестоимость (например: 2.5):")
    
    # Добавление вкуса - шаг 2: название вкуса
    elif state == 'awaiting_product_flavor':
        flavor_name = update.message.text.strip()
        if len(flavor_name) < 2:
            await update.message.reply_text("❌ Название вкуса слишком короткое. Попробуйте еще раз:")
            return
        
        context.user_data['product_flavor'] = flavor_name
        context.user_data['state'] = 'awaiting_product_price'
        
        try:
            await update.message.delete()
        except:
            pass
        
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Вкус: {flavor_name}\n\n"
            "Шаг 3/4: Введите цену (€):\n"
            "(например: 8.5)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_products")]])
        )
        if 'messages_to_delete' not in context.user_data:
            context.user_data['messages_to_delete'] = []
        context.user_data['messages_to_delete'].append(msg.message_id)
    
    # Добавление вкуса - шаг 3: цена
    elif state == 'awaiting_product_price':
        try:
            price = float(update.message.text.strip().replace(',', '.'))
            if price <= 0:
                await update.message.reply_text("❌ Цена должна быть положительной. Попробуйте еще раз:")
                return
            
            context.user_data['product_price'] = price
            context.user_data['state'] = 'awaiting_product_stock'
            
            try:
                await update.message.delete()
            except:
                pass
            
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ Цена: {price}€\n\n"
                "Шаг 4/4: Введите количество на складе:\n"
                "(например: 50)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_products")]])
            )
            if 'messages_to_delete' not in context.user_data:
                context.user_data['messages_to_delete'] = []
            context.user_data['messages_to_delete'].append(msg.message_id)
        except ValueError:
            await update.message.reply_text("❌ Неверный формат числа. Введите цену (например: 8.5):")
    
    # Добавление вкуса - шаг 4: количество
    elif state == 'awaiting_product_stock':
        try:
            stock = int(update.message.text.strip())
            if stock < 0:
                await update.message.reply_text("❌ Количество не может быть отрицательным. Попробуйте еще раз:")
                return
            
            # Создаем вкус
            model_id = context.user_data.get('product_model_id')
            flavor_name = context.user_data.get('product_flavor')
            price = context.user_data.get('product_price')
            
            async with async_session_maker() as session:
                new_product = await crud.create_product(
                    session,
                    model_id=model_id,
                    flavor_name=flavor_name,
                    price=price,
                    stock_quantity=stock
                )
                
                model = await crud.get_model_by_id(session, model_id)
                
                text = f"✅ Вкус создан!\n\n"
                text += f"📱 Модель: {model.name}\n"
                text += f"🍃 Вкус: {new_product.flavor_name}\n"
                text += f"💰 Цена: {new_product.price}€\n"
                text += f"📦 На складе: {new_product.stock_quantity} шт\n"
                text += f"🆔 ID: {new_product.id}"
                
                try:
                    await update.message.delete()
                except:
                    pass
                
                # Удаляем все промежуточные сообщения
                if 'messages_to_delete' in context.user_data:
                    for msg_id in context.user_data['messages_to_delete']:
                        try:
                            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                        except:
                            pass
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=get_admin_panel_kb()
                )
            
            context.user_data.clear()
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат числа. Введите количество (например: 50):")
    
    # Редактирование цены вкуса
    elif state == 'awaiting_flavor_price_edit':
        try:
            new_price = float(update.message.text.strip().replace(',', '.'))
            if new_price <= 0:
                await update.message.reply_text("❌ Цена должна быть положительной. Попробуйте еще раз:")
                return
            
            product_id = context.user_data.get('edit_product_id')
            
            async with async_session_maker() as session:
                product = await crud.get_product_by_id(session, product_id)
                if not product:
                    await update.message.reply_text("❌ Вкус не найден")
                    context.user_data.clear()
                    return
                
                old_price = product.price
                product.price = new_price
                await session.commit()
                
                model = await crud.get_model_by_id(session, product.model_id)
                
                # Удаляем все промежуточные сообщения
                try:
                    await update.message.delete()
                except:
                    pass
                
                if 'messages_to_delete' in context.user_data:
                    for msg_id in context.user_data['messages_to_delete']:
                        try:
                            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                        except:
                            pass
                
                text = f"✅ Цена обновлена!\n\n"
                text += f"🍃 {product.flavor_name}\n"
                text += f"📱 Модель: {model.name}\n"
                text += f"💰 Старая цена: {old_price}€\n"
                text += f"💰 Новая цена: {new_price}€\n"
                text += f"📦 На складе: {product.stock_quantity} шт"
                
                keyboard = [
                    [InlineKeyboardButton("◀️ К деталям вкуса", callback_data=f"view_flavor_detail_{product_id}")]
                ]
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                context.user_data.clear()
                
        except ValueError:
            await update.message.reply_text("❌ Неверный формат числа. Введите цену (например: 8.5):")
    
    # Редактирование описания модели
    elif state == 'awaiting_model_description_edit':
        new_description = update.message.text.strip()
        
        model_id = context.user_data.get('edit_model_id')
        
        async with async_session_maker() as session:
            model = await crud.get_model_by_id(session, model_id)
            if not model:
                await update.message.reply_text("❌ Модель не найдена")
                context.user_data.clear()
                return
            
            old_description = model.description or "(не указано)"
            model.description = new_description
            await session.commit()
            
            # Удаляем промежуточные сообщения
            try:
                await update.message.delete()
            except:
                pass
            
            if 'messages_to_delete' in context.user_data:
                for msg_id in context.user_data['messages_to_delete']:
                    try:
                        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                    except:
                        pass
            
            text = f"✅ Описание обновлено!\n\n"
            text += f"📱 Модель: {model.name}\n"
            text += f"📝 Старое описание: {old_description}\n"
            text += f"📝 Новое описание: {new_description}"
            
            keyboard = [
                [InlineKeyboardButton("◀️ К деталям модели", callback_data=f"view_model_{model_id}")]
            ]
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            context.user_data.clear()
    
    # Редактирование количества вкуса
    elif state == 'awaiting_flavor_stock_edit':
        try:
            new_stock = int(update.message.text.strip())
            if new_stock < 0:
                await update.message.reply_text("❌ Количество не может быть отрицательным. Попробуйте еще раз:")
                return
            
            product_id = context.user_data.get('edit_product_id')
            
            async with async_session_maker() as session:
                product = await crud.get_product_by_id(session, product_id)
                if not product:
                    await update.message.reply_text("❌ Вкус не найден")
                    context.user_data.clear()
                    return
                
                old_stock = product.stock_quantity
                product.stock_quantity = new_stock
                await session.commit()
                
                model = await crud.get_model_by_id(session, product.model_id)
                
                # Удаляем все промежуточные сообщения
                try:
                    await update.message.delete()
                except:
                    pass
                
                if 'messages_to_delete' in context.user_data:
                    for msg_id in context.user_data['messages_to_delete']:
                        try:
                            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                        except:
                            pass
                
                text = f"✅ Количество обновлено!\n\n"
                text += f"🍃 {product.flavor_name}\n"
                text += f"📱 Модель: {model.name}\n"
                text += f"💰 Цена: {product.price}€\n"
                text += f"📦 Старое количество: {old_stock} шт\n"
                text += f"📦 Новое количество: {new_stock} шт"
                
                keyboard = [
                    [InlineKeyboardButton("◀️ К деталям вкуса", callback_data=f"view_flavor_detail_{product_id}")]
                ]
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                context.user_data.clear()
                
        except ValueError:
            await update.message.reply_text("❌ Неверный формат числа. Введите количество (например: 50):")
    
    # Ожидание фото модели - пропуск
    elif state == 'awaiting_model_photo':
        if update.message.text and update.message.text.strip() == '-':
            try:
                await update.message.delete()
            except:
                pass
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ Модель создана без фото",
                reply_markup=get_admin_panel_kb()
            )
            context.user_data.clear()


async def start_add_product(query, context):
    """Начало добавления вкуса - выбор модели"""
    async with async_session_maker() as session:
        models = await crud.get_all_models(session, available_only=False)
        
        if not models:
            await query.edit_message_text(
                "❌ Нет доступных моделей. Сначала создайте модель.",
                reply_markup=get_admin_products_kb()
            )
            return
        
        context.user_data['state'] = 'awaiting_product_model'
        
        keyboard = []
        for model in models:
            keyboard.append([InlineKeyboardButton(model.name, callback_data=f"select_model_{model.id}")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="admin_products")])
        
        await query.edit_message_text(
            "➕ Добавление вкуса\n\n"
            "Шаг 1/4: Выберите модель:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def select_model_for_product(query, context):
    """Обработка выбора модели для вкуса"""
    model_id = int(query.data.split("_")[2])
    
    async with async_session_maker() as session:
        model = await crud.get_model_by_id(session, model_id)
        if not model:
            await query.answer("❌ Модель не найдена", show_alert=True)
            return
        
        context.user_data['product_model_id'] = model_id
        context.user_data['state'] = 'awaiting_product_flavor'
        
        await query.edit_message_text(
            f"✅ Модель: {model.name}\n\n"
            "Шаг 2/4: Введите название вкуса:\n"
            "(например: Watermelon Ice)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_products")]])
        )


# ==================== ПРОСМОТР МОДЕЛЕЙ И ВКУСОВ ====================

async def show_models_list(query, context):
    """Показать список всех моделей"""
    async with async_session_maker() as session:
        models = await crud.get_all_models(session, available_only=False)
        
        if not models:
            await query.edit_message_text(
                "❌ Нет моделей",
                reply_markup=get_admin_products_kb()
            )
            return
        
        keyboard = []
        for model in models:
            products_count = len(await crud.get_products_by_model(session, model.id, available_only=False))
            keyboard.append([InlineKeyboardButton(
                f"📱 {model.name} ({products_count} вкусов)",
                callback_data=f"view_model_{model.id}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_products")])
        
        try:
            await query.edit_message_text(
                "📱 Просмотр моделей\n\n"
                "Выберите модель:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📱 Просмотр моделей\n\n"
                "Выберите модель:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


async def show_model_detail(query, context):
    """Показать детали модели с фото"""
    model_id = int(query.data.split("_")[2])
    
    async with async_session_maker() as session:
        model = await crud.get_model_by_id(session, model_id)
        if not model:
            await query.answer("❌ Модель не найдена", show_alert=True)
            return
        
        products = await crud.get_products_by_model(session, model_id, available_only=False)
        
        text = f"📱 {model.name}\n\n"
        if model.description:
            text += f"📝 Описание: {model.description}\n"
        text += f"💰 Себестоимость: {model.cost_price}€\n"
        text += f"🍃 Вкусов: {len(products)} шт\n"
        text += f"🆔 ID: {model.id}"
        
        keyboard = [
            [InlineKeyboardButton("🍃 Просмотреть вкусы", callback_data=f"view_flavors_{model_id}")],
            [InlineKeyboardButton("✏️ Изменить описание", callback_data=f"edit_model_description_{model_id}")],
            [InlineKeyboardButton("🗑 Удалить модель", callback_data=f"confirm_delete_model_{model_id}")],
            [InlineKeyboardButton("◀️ К списку моделей", callback_data="admin_view_models")]
        ]
        
        # Проверяем наличие фото
        photo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'photo', f'model_{model_id}.jpg')
        
        try:
            await query.message.delete()
        except:
            pass
        
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=photo,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


async def show_model_flavors(query, context):
    """Показать список вкусов модели"""
    model_id = int(query.data.split("_")[2])
    
    async with async_session_maker() as session:
        model = await crud.get_model_by_id(session, model_id)
        products = await crud.get_products_by_model(session, model_id, available_only=False)
        
        if not products:
            await query.answer("❌ Нет вкусов для этой модели", show_alert=True)
            return
        
        keyboard = []
        for product in products:
            stock_emoji = "✅" if product.stock_quantity > 0 else "❌"
            keyboard.append([InlineKeyboardButton(
                f"{stock_emoji} {product.flavor_name} - {product.price}€",
                callback_data=f"view_flavor_detail_{product.id}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Назад к модели", callback_data=f"view_model_{model_id}")])
        
        # Всегда удаляем сообщение (может быть с фото) и создаем новое текстовое
        try:
            await query.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🍃 Вкусы: {model.name}\n\n"
            "Выберите вкус:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_flavor_detail(query, context):
    """Показать детали вкуса"""
    product_id = int(query.data.split("_")[3])
    
    async with async_session_maker() as session:
        product = await crud.get_product_by_id(session, product_id)
        if not product:
            await query.answer("❌ Вкус не найден", show_alert=True)
            return
        
        model = await crud.get_model_by_id(session, product.model_id)
        
        text = f"🍃 {product.flavor_name}\n\n"
        text += f"📱 Модель: {model.name}\n"
        text += f"💰 Цена: {product.price}€\n"
        text += f"📦 На складе: {product.stock_quantity} шт\n"
        text += f"🆔 ID: {product.id}\n"
        text += f"✅ Доступен: {'Да' if product.is_available else 'Нет'}"
        
        keyboard = [
            [InlineKeyboardButton("✏️ Изменить цену", callback_data=f"edit_flavor_price_{product_id}")],
            [InlineKeyboardButton("📦 Изменить количество", callback_data=f"edit_flavor_stock_{product_id}")],
            [InlineKeyboardButton("🗑 Удалить вкус", callback_data=f"confirm_delete_flavor_{product_id}")],
            [InlineKeyboardButton("◀️ К списку вкусов", callback_data=f"view_flavors_{model.id}")]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def start_edit_flavor_price(query, context):
    """Начать редактирование цены вкуса"""
    product_id = int(query.data.split("_")[-1])
    
    async with async_session_maker() as session:
        product = await crud.get_product_by_id(session, product_id)
        if not product:
            await query.answer("❌ Вкус не найден", show_alert=True)
            return
        
        context.user_data['state'] = 'awaiting_flavor_price_edit'
        context.user_data['edit_product_id'] = product_id
        context.user_data['messages_to_delete'] = []
        
        text = f"✏️ Изменение цены: {product.flavor_name}\n\n"
        text += f"Текущая цена: {product.price}€\n\n"
        text += "Введите новую цену (например: 25.50):"
        
        msg = await query.edit_message_text(text)
        context.user_data['messages_to_delete'].append(msg.message_id)


async def start_edit_flavor_stock(query, context):
    """Начать редактирование количества вкуса"""
    product_id = int(query.data.split("_")[-1])
    
    async with async_session_maker() as session:
        product = await crud.get_product_by_id(session, product_id)
        if not product:
            await query.answer("❌ Вкус не найден", show_alert=True)
            return
        
        context.user_data['state'] = 'awaiting_flavor_stock_edit'
        context.user_data['edit_product_id'] = product_id
        context.user_data['messages_to_delete'] = []
        
        text = f"📦 Изменение количества: {product.flavor_name}\n\n"
        text += f"Текущее количество: {product.stock_quantity} шт\n\n"
        text += "Введите новое количество:"
        
        msg = await query.edit_message_text(text)
        context.user_data['messages_to_delete'].append(msg.message_id)


async def start_edit_model_description(query, context):
    """Начать редактирование описания модели"""
    model_id = int(query.data.split("_")[-1])
    
    async with async_session_maker() as session:
        model = await crud.get_model_by_id(session, model_id)
        if not model:
            await query.answer("❌ Модель не найдена", show_alert=True)
            return
        
        context.user_data['state'] = 'awaiting_model_description_edit'
        context.user_data['edit_model_id'] = model_id
        context.user_data['messages_to_delete'] = []
        
        text = f"✏️ Изменение описания: {model.name}\n\n"
        if model.description:
            text += f"Текущее описание: {model.description}\n\n"
        else:
            text += "Текущее описание: (не указано)\n\n"
        text += "Введите новое описание модели:"
        
        msg = await query.edit_message_text(text)
        context.user_data['messages_to_delete'].append(msg.message_id)


async def confirm_delete_model(query, context):
    """Подтверждение удаления модели"""
    model_id = int(query.data.split("_")[3])
    
    async with async_session_maker() as session:
        model = await crud.get_model_by_id(session, model_id)
        if not model:
            await query.answer("❌ Модель не найдена", show_alert=True)
            return
        
        products = await crud.get_products_by_model(session, model_id, available_only=False)
        
        text = f"⚠️ Удалить модель {model.name}?\n\n"
        text += f"Вместе с ней будут удалены:\n"
        text += f"• {len(products)} вкусов\n"
        text += f"• Фото модели"
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"admin_delete_model_{model_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"view_model_{model_id}")]
        ]
        
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


async def confirm_delete_flavor(query, context):
    """Подтверждение удаления вкуса"""
    product_id = int(query.data.split("_")[3])
    
    async with async_session_maker() as session:
        product = await crud.get_product_by_id(session, product_id)
        if not product:
            await query.answer("❌ Вкус не найден", show_alert=True)
            return
        
        model = await crud.get_model_by_id(session, product.model_id)
        
        text = f"⚠️ Удалить вкус {product.flavor_name}?\n\n"
        text += f"📱 Модель: {model.name}\n"
        text += f"💰 Цена: {product.price}€\n"
        text += f"📦 На складе: {product.stock_quantity} шт"
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data=f"admin_delete_product_{product_id}")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"view_flavor_detail_{product_id}")]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_products_for_delete(query, context):
    """Показать список моделей, затем их вкусов для удаления"""
    async with async_session_maker() as session:
        models = await crud.get_all_models(session, available_only=False)
        
        if not models:
            await query.edit_message_text(
                "❌ Нет моделей",
                reply_markup=get_admin_products_kb()
            )
            return
        
        keyboard = []
        for model in models:
            products = await crud.get_products_by_model(session, model.id, available_only=False)
            if products:
                keyboard.append([InlineKeyboardButton(
                    f"📱 {model.name} ({len(products)} вкусов)",
                    callback_data=f"show_flavors_{model.id}"
                )])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_products")])
        
        await query.edit_message_text(
            "🗑 Удаление вкуса\n\n"
            "Выберите модель:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def delete_model_confirm(query, context):
    """Фактическое удаление модели"""
    model_id = int(query.data.split("_")[-1])
    
    async with async_session_maker() as session:
        model = await crud.get_model_by_id(session, model_id)
        if not model:
            await query.answer("❌ Модель не найдена", show_alert=True)
            return
        
        model_name = model.name
        
        # Удаляем модель
        await crud.delete_model(session, model_id)
        
        # Удаляем фото если есть
        photo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'photo', f'model_{model_id}.jpg')
        if os.path.exists(photo_path):
            os.remove(photo_path)
        
        await query.answer(f"✅ Модель {model_name} удалена", show_alert=True)
        await show_models_list(query, context)


async def delete_product_confirm(query, context):
    """Фактическое удаление вкуса"""
    product_id = int(query.data.split("_")[-1])
    
    async with async_session_maker() as session:
        product = await crud.get_product_by_id(session, product_id)
        if not product:
            await query.answer("❌ Продукт не найден", show_alert=True)
            return
        
        model_id = product.model_id
        flavor_name = product.flavor_name
        
        await crud.delete_product(session, product_id)
        
        await query.answer(f"✅ Вкус {flavor_name} удален", show_alert=True)
        
        # Возвращаемся к списку вкусов модели
        model = await crud.get_model_by_id(session, model_id)
        products = await crud.get_products_by_model(session, model_id, available_only=False)
        
        if not products:
            await query.edit_message_text(
                f"✅ Вкус {flavor_name} удален\n\n"
                f"У модели {model.name} больше нет вкусов",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ К моделям", callback_data="admin_view_models")]])
            )
        else:
            keyboard = []
            for product in products:
                stock_emoji = "✅" if product.stock_quantity > 0 else "❌"
                keyboard.append([InlineKeyboardButton(
                    f"{stock_emoji} {product.flavor_name} - {product.price}€",
                    callback_data=f"view_flavor_detail_{product.id}"
                )])
            keyboard.append([InlineKeyboardButton("◀️ Назад к модели", callback_data=f"view_model_{model_id}")])
            
            # Удаляем сообщение и создаем новое текстовое
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"✅ Вкус {flavor_name} удален\n\n"
                     f"🍃 Вкусы: {model.name}\n\n"
                     "Выберите вкус:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


# ==================== MESSAGE HANDLERS ====================

@admin_required
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото (для добавления моделей)"""
    state = context.user_data.get('state')
    
    # Если ожидаем фото модели
    if state == 'awaiting_model_photo':
        model_id = context.user_data.get('model_id')
        if not model_id:
            await update.message.reply_text("❌ Ошибка: ID модели не найден")
            return
        
        try:
            # Получаем файл фото
            photo = update.message.photo[-1]  # Берем самое качественное
            file = await context.bot.get_file(photo.file_id)
            
            # Создаем папку для фото если ее нет
            photo_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'photo')
            os.makedirs(photo_dir, exist_ok=True)
            
            # Сохраняем фото с именем model_{id}.jpg
            photo_path = os.path.join(photo_dir, f'model_{model_id}.jpg')
            await file.download_to_drive(photo_path)
            
            # Удаляем сообщение с фото
            try:
                await update.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ Фото успешно сохранено!\n"
                f"📸 Файл: model_{model_id}.jpg",
                reply_markup=get_admin_panel_kb()
            )
            
            # Очищаем состояние
            context.user_data.clear()
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при сохранении фото: {e}")
    
    else:
        await update.message.reply_text("📸 Фото получено, но не используется. Добавьте модель сначала.")


@admin_required
async def cmd_fix_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скрытая команда для очистки дубликатов в заказах"""
    async with async_session_maker() as session:
        # Получаем все заказы
        all_orders = await crud.get_all_orders(session)
        
        fixed_count = 0
        for order in all_orders:
            # Объединяем дубликаты в каждом заказе
            items_result = await session.execute(
                select(crud.OrderItem).where(crud.OrderItem.order_id == order.id)
            )
            items = items_result.scalars().all()
            
            # Группируем по product_id и price_at_order
            product_groups = {}
            for item in items:
                key = (item.product_id, item.price_at_order)
                if key in product_groups:
                    product_groups[key].append(item)
                else:
                    product_groups[key] = [item]
            
            # Объединяем дубликаты
            for key, group_items in product_groups.items():
                if len(group_items) > 1:
                    total_quantity = sum(item.quantity for item in group_items)
                    first_item = group_items[0]
                    first_item.quantity = total_quantity
                    
                    # Удаляем остальные
                    for item in group_items[1:]:
                        await session.delete(item)
                    
                    fixed_count += 1
            
            # Пересчитываем сумму заказа
            items_result = await session.execute(
                select(crud.OrderItem).where(crud.OrderItem.order_id == order.id)
            )
            updated_items = items_result.scalars().all()
            
            new_total = sum(item.quantity * item.price_at_order for item in updated_items)
            new_total += order.delivery_fee
            order.total_price = new_total
        
        await session.commit()
    
    msg = await update.message.reply_text(f"✅ Исправлено {fixed_count} дубликатов в заказах")
    try:
        await update.message.delete()
        await asyncio.sleep(3)
        await msg.delete()
    except:
        pass


@admin_required
async def cmd_reset_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скрытая команда для полной очистки базы (только для тестирования)"""
    # Проверяем состояние подтверждения
    if context.user_data.get('reset_db_confirm') != True:
        context.user_data['reset_db_confirm'] = True
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, очистить базу", callback_data="confirm_reset_db")],
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
        ]
        
        await update.message.reply_text(
            "⚠️ ВНИМАНИЕ!\n\n"
            "Вы собираетесь удалить:\n"
            "• Все заказы\n"
            "• Все корзины\n"
            "• Все OrderItem записи\n\n"
            "Перед удалением будет создан бэкап БД.\n\n"
            "Вы уверены?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        try:
            await update.message.delete()
        except:
            pass
        return
    
    # Создаем бэкап
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'cloud_supply.db')
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'backups')
    
    # Создаем папку для бэкапов если её нет
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Имя бэкапа с датой и временем
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = os.path.join(backup_dir, backup_name)
    
    # Копируем базу
    try:
        shutil.copy2(db_path, backup_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка создания бэкапа: {e}")
        context.user_data.clear()
        return
    
    # Очищаем базу
    async with async_session_maker() as session:
        # Удаляем все корзины
        await session.execute(delete(crud.Cart))
        
        # Удаляем все OrderItem
        await session.execute(delete(crud.OrderItem))
        
        # Удаляем все заказы
        await session.execute(delete(crud.Order))
        
        await session.commit()
    
    msg = await update.message.reply_text(
        f"✅ База данных очищена!\n\n"
        f"📦 Бэкап сохранен:\n{backup_name}"
    )
    
    context.user_data.clear()
    
    try:
        await asyncio.sleep(5)
        await msg.delete()
    except:
        pass


async def confirm_reset_db(query, context):
    """Подтверждение очистки базы данных"""
    # Создаем бэкап
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'cloud_supply.db')
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'backups')
    
    # Создаем папку для бэкапов если её нет
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Имя бэкапа с датой и временем
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = os.path.join(backup_dir, backup_name)
    
    # Копируем базу
    try:
        shutil.copy2(db_path, backup_path)
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка создания бэкапа: {e}")
        context.user_data.clear()
        return
    
    # Очищаем базу
    async with async_session_maker() as session:
        # Удаляем все корзины
        await session.execute(delete(crud.Cart))
        
        # Удаляем все OrderItem
        await session.execute(delete(crud.OrderItem))
        
        # Удаляем все заказы
        await session.execute(delete(crud.Order))
        
        await session.commit()
    
    await query.edit_message_text(
        f"✅ База данных очищена!\n\n"
        f"📦 Бэкап сохранен:\n{backup_name}",
        reply_markup=get_admin_panel_kb()
    )
    
    context.user_data.clear()
    await query.answer("✅ Готово!", show_alert=True)
