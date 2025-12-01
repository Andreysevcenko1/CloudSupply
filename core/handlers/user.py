"""
Обработчики для пользователей (python-telegram-bot)
"""

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, and_
import os
import asyncio
from functools import wraps
from dotenv import load_dotenv

# Загружаем .env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

from ..db import crud, async_session_maker
from ..db.models import OrderItem
from ..keyboards.inline import (
    get_main_menu_kb, get_back_to_menu_kb, get_models_kb, get_products_kb, get_product_quantity_kb,
    get_cart_kb, get_delivery_method_kb, get_confirm_order_kb, get_orders_kb, get_order_detail_kb, get_support_kb
)


def is_admin(username: str) -> bool:
    """Проверка является ли пользователь админом"""
    admin_username = os.getenv('ADMIN_USERNAME', '')
    support_username = os.getenv('SUPPORT_USERNAME', '')
    return username in [admin_username, support_username]


def check_banned(func):
    """Декоратор для проверки бана пользователя перед выполнением любого действия"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        async with async_session_maker() as session:
            user = await crud.get_user_by_telegram_id(session, user_id)
            if user and user.is_banned:
                # Пытаемся ответить на callback_query если есть, иначе на сообщение
                if update.callback_query:
                    await update.callback_query.answer(
                        "❌ Вы заблокированы и не можете использовать бота.",
                        show_alert=True
                    )
                elif update.message:
                    await update.message.reply_text(
                        "❌ Вы заблокированы и не можете использовать бота."
                    )
                return
        
        return await func(update, context, *args, **kwargs)
    return wrapper


def check_maintenance(func):
    """Декоратор для проверки режима технических работ"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Проверяем, является ли пользователь админом
        username = update.effective_user.username
        if is_admin(username):
            # Админ может работать в любом режиме
            return await func(update, context, *args, **kwargs)
        
        # Проверяем режим тех. работ
        async with async_session_maker() as session:
            maintenance_enabled = await crud.get_maintenance_mode(session)
            
            if maintenance_enabled:
                # Отправляем приветственное изображение с сообщением
                welcome_image_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), 
                    'assets', 
                    'welcome.jpg'
                )
                
                message_text = "🔧 Бот приостановлен для улучшений, скоро увидимся!"
                
                if os.path.exists(welcome_image_path):
                    with open(welcome_image_path, 'rb') as photo:
                        if update.callback_query:
                            await context.bot.send_photo(
                                chat_id=update.effective_chat.id,
                                photo=photo,
                                caption=message_text
                            )
                            await update.callback_query.answer()
                        elif update.message:
                            await update.message.reply_photo(
                                photo=photo,
                                caption=message_text
                            )
                else:
                    # Если картинка не найдена, отправляем просто текст
                    if update.callback_query:
                        await update.callback_query.answer(message_text, show_alert=True)
                    elif update.message:
                        await update.message.reply_text(message_text)
                
                return
        
        return await func(update, context, *args, **kwargs)
    return wrapper


async def send_order_notification_to_admin(context, order, user, cart_items, delivery_method, delivery_fee):
    """Отправить уведомление админу о новом заказе"""
    admin_username = os.getenv('ADMIN_USERNAME', '')
    support_username = os.getenv('SUPPORT_USERNAME', '')
    
    # Получаем telegram_id обоих админов из базы
    async with async_session_maker() as session:
        admin_users = []
        
        if admin_username:
            result = await session.execute(select(crud.User).where(crud.User.username == admin_username))
            admin_user = result.scalar_one_or_none()
            if admin_user:
                admin_users.append(admin_user)
        
        if support_username:
            result = await session.execute(select(crud.User).where(crud.User.username == support_username))
            support_user = result.scalar_one_or_none()
            if support_user:
                admin_users.append(support_user)
        
        if not admin_users:
            return
        
        delivery_text = "🚚 Доставка (+5€)" if delivery_method == "delivery" else "🏃 Самовывоз"
        
        text = f"🔔 Новый заказ #{order.id}!\n\n"
        text += f"👤 Клиент: {user.username or user.first_name}\n"
        text += f"📞 Контакт: {order.contact_info}\n\n"
        text += "📋 Товары:\n"
        
        async with async_session_maker() as session:
            for item in cart_items:
                product = await crud.get_product_by_id(session, item.product_id)
                model = await crud.get_model_by_id(session, product.model_id)
                text += f"• {model.name} - {product.flavor_name} x{item.quantity}\n"
        
        text += f"\n{delivery_text}\n"
        text += f"💰 Итого: {order.total_price}€"
        
        # Отправляем обоим админам
        for admin in admin_users:
            try:
                await context.bot.send_message(chat_id=admin.telegram_id, text=text)
            except Exception as e:
                print(f"Ошибка отправки уведомления админу {admin.username}: {e}")


async def get_welcome_image_path() -> str:
    """Получить путь к приветственной картинке"""
    photo_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'photo')
    welcome_image = os.path.join(photo_dir, 'welcome.jpg')
    
    if os.path.exists(welcome_image):
        return welcome_image
    return None


# ==================== КОМАНДЫ ====================

@check_maintenance
@check_banned
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    async with async_session_maker() as session:
        user = await crud.get_or_create_user(
            session,
            telegram_id=update.effective_user.id,
            username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name
        )
        
        welcome_msg = await crud.get_setting(session, 'welcome_message')
        if not welcome_msg:
            welcome_msg = "🌊 Добро пожаловать в Liquid Planet!\n\nВыберите модель вейпа и наслаждайтесь лучшими вкусами! 💨"
        
        admin = is_admin(update.effective_user.username)
        
        welcome_image = await get_welcome_image_path()
        if welcome_image:
            with open(welcome_image, 'rb') as photo:
                msg = await update.message.reply_photo(
                    photo=photo,
                    caption=welcome_msg,
                    reply_markup=get_main_menu_kb(is_admin=admin)
                )
                context.user_data['last_bot_message'] = msg.message_id
        else:
            msg = await update.message.reply_text(
                welcome_msg,
                reply_markup=get_main_menu_kb(is_admin=admin)
            )
            context.user_data['last_bot_message'] = msg.message_id


@check_maintenance
@check_banned
async def cmd_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /catalog"""
    async with async_session_maker() as session:
        models = await crud.get_all_models(session, available_only=True)
        
        if not models:
            msg = await update.message.reply_text(
                "😔 К сожалению, сейчас нет доступных моделей.",
                reply_markup=get_main_menu_kb(is_admin=is_admin(update.effective_user.username))
            )
            context.user_data['last_bot_message'] = msg.message_id
        else:
            msg = await update.message.reply_text(
                "🛍 Выберите модель вейпа:",
                reply_markup=get_models_kb(models)
            )
            context.user_data['last_bot_message'] = msg.message_id


@check_maintenance
@check_banned
async def cmd_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /cart"""
    await show_cart_internal(update, context, update.effective_user.id)


@check_maintenance
@check_banned
async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /orders"""
    async with async_session_maker() as session:
        user = await crud.get_user_by_telegram_id(session, update.effective_user.id)
        orders = await crud.get_user_orders(session, user.id)
        
        if not orders:
            msg = await update.message.reply_text(
                "📦 У вас пока нет заказов",
                reply_markup=get_main_menu_kb(is_admin=is_admin(update.effective_user.username))
            )
            context.user_data['last_bot_message'] = msg.message_id
        else:
            msg = await update.message.reply_text(
                "📦 Ваши заказы:",
                reply_markup=get_orders_kb(orders)
            )
            context.user_data['last_bot_message'] = msg.message_id


@check_maintenance
@check_banned
async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /support"""
    support_username = os.getenv('SUPPORT_USERNAME', 'cloud_supplier')
    
    text = f"📞 Поддержка Cloud Supply\n\n"
    text += f"Свяжитесь с нами: @{support_username}"
    
    await update.message.reply_text(text, reply_markup=get_support_kb(support_username))


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скрытая команда /clear - очистка чата"""
    if not is_admin(update.effective_user.username):
        return
    
    try:
        # Удаляем последние 100 сообщений
        chat_id = update.effective_chat.id
        message_id = update.message.message_id
        
        deleted_count = 0
        for i in range(message_id, max(message_id - 100, 0), -1):
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=i)
                deleted_count += 1
            except:
                pass
        
        # Отправляем подтверждение и удаляем его через 3 секунды
        msg = await update.message.reply_text(f"✅ Удалено {deleted_count} сообщений")
        await asyncio.sleep(3)
        await msg.delete()
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


# ==================== CALLBACK HANDLERS ====================

@check_maintenance
@check_banned
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-запросов"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Главное меню
    if data == "main_menu":
        await show_main_menu(query, context)
    
    # Каталог
    elif data == "catalog":
        await show_catalog(query, context)
    elif data.startswith("model_"):
        await show_model_products(query, context)
    elif data.startswith("product_"):
        await show_product_detail(query, context)
    elif data == "back_to_products":
        await show_catalog(query, context)
    
    # Корзина
    elif data == "cart":
        await show_cart(query, context)
    elif data.startswith("removecart_"):
        await remove_from_cart(query, context)
    elif data == "clear_cart":
        await clear_cart(query, context)
    
    # Заказы
    elif data == "checkout":
        await checkout(query, context)
    elif data.startswith("delivery_"):
        await select_delivery_method(query, context)
    elif data.startswith("confirm_order_"):
        await confirm_order(query, context)
    elif data == "my_orders":
        await show_my_orders(query, context)
    elif data.startswith("order_") and not data.startswith("order_status"):
        await show_order_detail(query, context)
    
    # Поддержка
    elif data == "support":
        await show_support(query, context)


async def show_main_menu(query, context):
    """Главное меню"""
    admin = is_admin(query.from_user.username)
    
    async with async_session_maker() as session:
        welcome_msg = await crud.get_setting(session, 'welcome_message')
        if not welcome_msg:
            welcome_msg = "☁️ Добро пожаловать в Cloud Supply!"
    
    # Проверяем наличие приветственной картинки
    welcome_image = await get_welcome_image_path()
    
    # Всегда удаляем старое сообщение и отправляем новое с картинкой
    await query.message.delete()
    
    if welcome_image:
        with open(welcome_image, 'rb') as photo:
            msg = await query.message.reply_photo(
                photo=photo,
                caption=welcome_msg,
                reply_markup=get_main_menu_kb(is_admin=admin)
            )
            context.user_data['last_bot_message'] = msg.message_id
    else:
        msg = await query.message.reply_text(welcome_msg, reply_markup=get_main_menu_kb(is_admin=admin))
        context.user_data['last_bot_message'] = msg.message_id


async def show_catalog(query, context):
    """Показать каталог"""
    async with async_session_maker() as session:
        models = await crud.get_all_models(session, available_only=True)
        
        # Удаляем сообщение с фото
        await query.message.delete()
        
        if not models:
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]
            msg = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="😔 Нет доступных моделей",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            context.user_data['last_bot_message'] = msg.message_id
        else:
            msg = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="🛍 Выберите модель:",
                reply_markup=get_models_kb(models)
            )
            context.user_data['last_bot_message'] = msg.message_id


async def show_model_products(query, context):
    """Показать вкусы модели"""
    model_id = int(query.data.split("_")[1])
    
    async with async_session_maker() as session:
        model = await crud.get_model_by_id(session, model_id)
        products = await crud.get_products_by_model(session, model_id, available_only=True)
        
        if not products:
            models = await crud.get_all_models(session, available_only=True)
            try:
                await query.edit_message_text(
                    f"😔 Для {model.name} нет вкусов",
                    reply_markup=get_models_kb(models)
                )
            except:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"😔 Для {model.name} нет вкусов",
                    reply_markup=get_models_kb(models)
                )
        else:
            text = f"🌊 {model.name}\n\n"
            if model.description:
                text += f"{model.description}\n\n"
            text += "Выберите вкус:"
            
            # Удаляем предыдущее сообщение
            try:
                await query.message.delete()
            except:
                pass
            
            # Проверяем наличие фото модели
            photo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'photo', f'model_{model_id}.jpg')
            
            if os.path.exists(photo_path):
                with open(photo_path, 'rb') as photo:
                    msg = await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=photo,
                        caption=text,
                        reply_markup=get_products_kb(products, model_id)
                    )
                    context.user_data['last_bot_message'] = msg.message_id
            else:
                msg = await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=get_products_kb(products, model_id)
                )
                context.user_data['last_bot_message'] = msg.message_id


async def show_product_detail(query, context):
    """Показать детали товара и запросить количество"""
    product_id = int(query.data.split("_")[1])
    
    async with async_session_maker() as session:
        product = await crud.get_product_by_id(session, product_id)
        model = await crud.get_model_by_id(session, product.model_id)
        user = await crud.get_user_by_telegram_id(session, query.from_user.id)
        
        # Проверяем сколько уже в корзине и заказе
        cart_items = await crud.get_user_cart(session, user.id)
        cart_total = sum(item.quantity for item in cart_items)
        
        # Проверяем активный заказ
        from sqlalchemy import select, and_
        from ..db.models import Order, OrderItem
        result = await session.execute(
            select(Order).where(
                and_(Order.user_id == user.id, Order.status == 'processing')
            )
        )
        active_order = result.scalars().first()
        order_total = 0
        if active_order:
            items_result = await session.execute(
                select(OrderItem).where(OrderItem.order_id == active_order.id)
            )
            order_items = items_result.scalars().all()
            order_total = sum(item.quantity for item in order_items)
        
        total_items = cart_total + order_total
        available_slots = 10 - total_items
        
        text = f"🌊 {model.name} - {product.flavor_name}\n\n"
        text += f"💰 Цена: {product.price}€\n"
        text += f"📦 В наличии: {product.stock_quantity} шт\n\n"
        text += f"⚠️ Лимит: максимум 10 единиц за заказ\n"
        text += f"📋 У вас уже: {total_items} ед. (корзина + заказ)\n"
        text += f"✅ Доступно: {available_slots} ед.\n\n"
        
        if available_slots <= 0:
            text += "❌ Лимит исчерпан! Оформите текущий заказ."
        else:
            text += f"✏️ Введите количество (1-{min(available_slots, product.stock_quantity)}):"
        
        # Удаляем предыдущее сообщение
        try:
            await query.message.delete()
        except:
            pass
        
        # Отправляем новое сообщение
        msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=get_product_quantity_kb(product_id)
        )
        context.user_data['last_bot_message'] = msg.message_id
        
        # Устанавливаем состояние ожидания количества
        if available_slots > 0:
            context.user_data['state'] = 'awaiting_product_quantity'
            context.user_data['product_id'] = product_id
            context.user_data['available_slots'] = available_slots
            context.user_data['product_stock'] = product.stock_quantity


async def show_cart(query, context):
    """Показать корзину"""
    await show_cart_internal(None, context, query.from_user.id, query=query)


async def show_cart_internal(update, context, user_id, query=None):
    """Внутренняя функция показа корзины"""
    async with async_session_maker() as session:
        user = await crud.get_user_by_telegram_id(session, user_id)
        # get_user_cart уже вызывает merge_duplicate_cart_items внутри
        cart_items = await crud.get_user_cart(session, user.id)
        
        if not cart_items:
            text = "🛒 Ваша корзина пуста"
            keyboard = get_cart_kb([], has_items=False)
        else:
            text = "🛒 Ваша корзина:\n\n"
            total = 0.0
            valid_items_data = []
            
            # Используем словарь для дополнительной защиты от дубликатов при отображении
            items_dict = {}
            
            for item in cart_items:
                product = await crud.get_product_by_id(session, item.product_id)
                if not product:
                    # Удаляем товар из корзины если продукт не найден
                    await crud.remove_from_cart(session, item.id)
                    continue
                
                model = await crud.get_model_by_id(session, product.model_id)
                if not model:
                    # Удаляем товар из корзины если модель не найдена
                    await crud.remove_from_cart(session, item.id)
                    continue
                
                # Проверяем дубликаты по product_id (дополнительная защита)
                if item.product_id in items_dict:
                    # Если дубликат, суммируем количество
                    prev_item, prev_product, prev_model = items_dict[item.product_id]
                    prev_item.quantity += item.quantity
                    # Удаляем дубликат из БД
                    await crud.remove_from_cart(session, item.id)
                    continue
                
                item_total = product.price * item.quantity
                total += item_total
                items_dict[item.product_id] = (item, product, model)
                valid_items_data.append((item, product, model))
                
                text += f"• {model.name} - {product.flavor_name}\n"
                text += f"  {item.quantity} x {product.price}€ = {item_total}€\n\n"
            
            if not valid_items_data:
                text = "🛒 Ваша корзина пуста"
                keyboard = get_cart_kb([], has_items=False)
            else:
                text += f"💰 Итого: {total}€"
                keyboard = get_cart_kb(valid_items_data, has_items=True)
        
        if query:
            try:
                await query.edit_message_text(text, reply_markup=keyboard)
            except Exception as e:
                print(f"Ошибка редактирования сообщения корзины: {e}")
                try:
                    await query.message.delete()
                    await query.message.reply_text(text, reply_markup=keyboard)
                except Exception as e2:
                    print(f"Ошибка отправки сообщения корзины: {e2}")
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=text,
                        reply_markup=keyboard
                    )
        else:
            try:
                await update.message.reply_text(text, reply_markup=keyboard)
            except Exception as e:
                print(f"Ошибка отправки сообщения корзины: {e}")


async def remove_from_cart(query, context):
    """Удалить из корзины"""
    cart_id = int(query.data.split("_")[1])
    
    async with async_session_maker() as session:
        await crud.remove_from_cart(session, cart_id)
    
    await query.answer("🗑 Удалено")
    await show_cart(query, context)


async def clear_cart(query, context):
    """Очистить корзину"""
    async with async_session_maker() as session:
        user = await crud.get_user_by_telegram_id(session, query.from_user.id)
        await crud.clear_user_cart(session, user.id)
    
    await query.answer("🗑 Корзина очищена")
    await show_cart(query, context)


async def checkout(query, context):
    """Оформление заказа - выбор доставки"""
    async with async_session_maker() as session:
        user = await crud.get_user_by_telegram_id(session, query.from_user.id)
        
        # Проверяем наличие активного заказа
        from sqlalchemy import select, and_
        from ..db.models import Order
        result = await session.execute(
            select(Order).where(
                and_(Order.user_id == user.id, Order.status == 'processing')
            )
        )
        active_order = result.scalars().first()
        
        if active_order:
            await query.answer(
                "⚠️ У вас уже есть активный заказ!\n"
                "Дождитесь его выполнения или добавьте товары в существующий заказ через 'Мои заказы'.",
                show_alert=True
            )
            return
        
        cart_items = await crud.get_user_cart(session, user.id)
        
        if not cart_items:
            await query.answer("❌ Корзина пуста!", show_alert=True)
            return
        
        text = "📋 Ваш заказ:\n\n"
        total = 0.0
        
        for item in cart_items:
            product = await crud.get_product_by_id(session, item.product_id)
            model = await crud.get_model_by_id(session, product.model_id)
            item_total = product.price * item.quantity
            total += item_total
            
            text += f"• {model.name} - {product.flavor_name}\n"
            text += f"  {item.quantity} x {product.price}€ = {item_total}€\n\n"
        
        text += f"💰 Итого: {total}€\n\n"
        text += "Выберите способ получения:"
        
        try:
            await query.edit_message_text(text, reply_markup=get_delivery_method_kb())
        except:
            await query.message.delete()
            msg = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text,
                reply_markup=get_delivery_method_kb()
            )
            context.user_data['last_bot_message'] = msg.message_id


async def select_delivery_method(query, context):
    """Выбор способа доставки"""
    delivery_method = query.data.split("_")[1]  # pickup или delivery
    
    async with async_session_maker() as session:
        user = await crud.get_user_by_telegram_id(session, query.from_user.id)
        cart_items = await crud.get_user_cart(session, user.id)
        
        if not cart_items:
            await query.answer("❌ Корзина пуста!", show_alert=True)
            return
        
        text = "📋 Ваш заказ:\n\n"
        total = 0.0
        
        for item in cart_items:
            product = await crud.get_product_by_id(session, item.product_id)
            model = await crud.get_model_by_id(session, product.model_id)
            item_total = product.price * item.quantity
            total += item_total
            
            text += f"• {model.name} - {product.flavor_name}\n"
            text += f"  {item.quantity} x {product.price}€ = {item_total}€\n\n"
        
        delivery_fee = 5.0 if delivery_method == "delivery" else 0.0
        delivery_text = "🚚 Доставка (+5€)" if delivery_method == "delivery" else "🏃 Самовывоз"
        
        text += f"💰 Сумма товаров: {total}€\n"
        if delivery_fee > 0:
            text += f"🚚 Доставка: {delivery_fee}€\n"
        text += f"💵 Итого: {total + delivery_fee}€\n\n"
        text += f"Способ получения: {delivery_text}\n\n"
        text += "Подтвердите заказ:"
        
        await query.edit_message_text(text, reply_markup=get_confirm_order_kb(delivery_method))


async def confirm_order(query, context):
    """Подтверждение заказа"""
    delivery_method = query.data.split("_")[2]  # pickup или delivery
    delivery_fee = 5.0 if delivery_method == "delivery" else 0.0
    
    async with async_session_maker() as session:
        user = await crud.get_user_by_telegram_id(session, query.from_user.id)
        cart_items = await crud.get_user_cart(session, user.id)
        
        if not cart_items:
            await query.answer("❌ Корзина пуста!", show_alert=True)
            return
        
        contact_info = f"@{query.from_user.username}" if query.from_user.username else f"ID: {query.from_user.id}"
        
        # Проверяем был ли активный заказ до создания
        existing_order_result = await session.execute(
            select(crud.Order).where(
                and_(crud.Order.user_id == user.id, crud.Order.status == 'processing')
            ).order_by(crud.Order.created_at.desc())
        )
        had_existing_order = existing_order_result.scalars().first() is not None
        
        order = await crud.create_order(session, user.id, cart_items, contact_info, delivery_method, delivery_fee)
        
        support_username = os.getenv('SUPPORT_USERNAME', 'cloud_supplier')
        delivery_text = "🚚 Доставка" if delivery_method == "delivery" else "🏃 Самовывоз"
        
        if had_existing_order:
            text = f"✅ Товары добавлены к заказу #{order.id}!\n\n"
        else:
            text = f"✅ Заказ #{order.id} оформлен!\n\n"
        
        text += f"💰 Сумма: {order.total_price}€\n"
        text += f"{delivery_text}\n"
        text += f"📞 Поддержка @{support_username} свяжется с вами\n\n"
        text += "Спасибо! ☁️"
        
        await query.edit_message_text(text, reply_markup=get_main_menu_kb(is_admin=is_admin(query.from_user.username)))
        await query.answer("✅ Заказ оформлен!", show_alert=True)
        
        # Отправляем уведомление админу
        await send_order_notification_to_admin(context, order, user, cart_items, delivery_method, delivery_fee)


async def show_my_orders(query, context):
    """Мои заказы"""
    async with async_session_maker() as session:
        user = await crud.get_user_by_telegram_id(session, query.from_user.id)
        orders = await crud.get_user_orders(session, user.id)
        
        # Удаляем сообщение с фото
        await query.message.delete()
        
        if not orders:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📦 У вас пока нет заказов",
                reply_markup=get_back_to_menu_kb()
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📦 Ваши заказы:",
                reply_markup=get_orders_kb(orders)
            )


async def show_order_detail(query, context):
    """Детали заказа"""
    order_id = int(query.data.split("_")[1])
    
    async with async_session_maker() as session:
        order = await crud.get_order_by_id(session, order_id)
        
        if not order:
            await query.answer("❌ Заказ не найден", show_alert=True)
            return
        
        status_text = {
            'processing': '📦 В процессе',
            'completed': '✅ Готов'
        }.get(order.status, '❓ Неизвестно')
        
        delivery_text = "🚚 Доставка" if order.delivery_method == "delivery" else "🏃 Самовывоз"
        
        text = f"📋 Заказ #{order_id}\n\n"
        text += f"Статус: {status_text}\n"
        text += f"{delivery_text}\n"
        text += f"Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        text += f"Сумма: {order.total_price}€\n\n"
        text += "Товары:\n"
        
        items_result = await session.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        items = items_result.scalars().all()
        
        total_items = 0
        for item in items:
            product = await crud.get_product_by_id(session, item.product_id)
            model = await crud.get_model_by_id(session, product.model_id)
            text += f"• {model.name} - {product.flavor_name}\n"
            text += f"  {item.quantity} x {item.price_at_order}€ = {item.quantity * item.price_at_order}€\n"
            total_items += item.quantity
        
        # Показываем общее количество и лимит если заказ активный
        if order.status == 'processing':
            text += f"\n📊 Всего единиц: {total_items}/10"
            if total_items < 10:
                text += f"\n✅ Вы можете добавить еще {10 - total_items} ед."
        
        admin = is_admin(query.from_user.username)
        is_processing = order.status == 'processing'
        await query.edit_message_text(text, reply_markup=get_order_detail_kb(order_id, is_admin=admin, is_processing=is_processing))


async def show_support(query, context):
    """Поддержка"""
    support_username = os.getenv('SUPPORT_USERNAME', 'cloud_supplier')
    
    text = f"📞 Поддержка Cloud Supply\n\n"
    text += f"Свяжитесь с нами: @{support_username}"
    
    try:
        await query.edit_message_text(text, reply_markup=get_support_kb(support_username))
    except:
        await query.message.delete()
        await query.message.reply_text(text, reply_markup=get_support_kb(support_username))


# ==================== MESSAGE HANDLERS ====================

@check_maintenance
@check_banned
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений (для FSM)"""
    state = context.user_data.get('state')
    
    print(f"DEBUG: handle_message called. State: {state}, User: {update.effective_user.username}")
    print(f"DEBUG: user_data: {context.user_data}")
    
    # Если есть состояние и пользователь админ - передаем в админ обработчик
    if state and is_admin(update.effective_user.username):
        from ..handlers import admin
        await admin.handle_admin_message(update, context)
        return
    
    # Обработка ввода количества товара
    if state == 'awaiting_product_quantity':
        try:
            quantity = int(update.message.text.strip())
            product_id = context.user_data.get('product_id')
            available_slots = context.user_data.get('available_slots', 10)
            product_stock = context.user_data.get('product_stock', 999)
            
            # Проверки
            if quantity <= 0:
                await update.message.reply_text("❌ Количество должно быть больше 0. Попробуйте еще раз:")
                return
            
            if quantity > available_slots:
                await update.message.reply_text(
                    f"❌ Превышен лимит! У вас доступно только {available_slots} единиц.\n"
                    f"⚠️ Максимум 10 единиц за заказ (корзина + активный заказ).\n\n"
                    f"Попробуйте еще раз или оформите текущий заказ."
                )
                return
            
            if quantity > product_stock:
                await update.message.reply_text(
                    f"❌ Недостаточно товара на складе!\n"
                    f"Доступно: {product_stock} шт\n\n"
                    f"Введите другое количество:"
                )
                return
            
            # Добавляем в корзину
            async with async_session_maker() as session:
                user = await crud.get_user_by_telegram_id(session, update.effective_user.id)
                product = await crud.get_product_by_id(session, product_id)
                model = await crud.get_model_by_id(session, product.model_id)
                
                await crud.add_to_cart(session, user.id, product_id, quantity)
                
                # Удаляем сообщение пользователя
                try:
                    await update.message.delete()
                except:
                    pass
                
                text = f"✅ Товар добавлен в корзину!\n\n"
                text += f"🌊 {model.name} - {product.flavor_name}\n"
                text += f"📦 Количество: {quantity} шт\n"
                text += f"💰 Сумма: {product.price * quantity}€"
                
                from ..keyboards.inline import get_after_add_to_cart_kb
                msg = await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=get_after_add_to_cart_kb()
                )
                context.user_data['last_bot_message'] = msg.message_id
                
                # Очищаем состояние
                context.user_data.clear()
                context.user_data['last_bot_message'] = msg.message_id
                
        except ValueError:
            await update.message.reply_text("❌ Введите корректное число:")
        return
    
    # Обработка контактной информации для заказа
    if state == 'awaiting_contact_info':
        contact_info = update.message.text.strip()
        delivery_method = context.user_data.get('delivery_method', 'pickup')
        
        async with async_session_maker() as session:
            user = await crud.get_user_by_telegram_id(session, update.effective_user.id)
            cart_items = await crud.get_user_cart(session, user.id)
            
            if not cart_items:
                await update.message.reply_text("❌ Корзина пуста!")
                context.user_data.clear()
                return
            
            delivery_fee = 5.0 if delivery_method == "delivery" else 0.0
            
            try:
                order = await crud.create_order(
                    session, user.id, cart_items, contact_info, delivery_method, delivery_fee
                )
                
                # Удаляем сообщение пользователя
                try:
                    await update.message.delete()
                except:
                    pass
                
                delivery_text = "🚚 Доставка (+5€)" if delivery_method == "delivery" else "🏃 Самовывоз"
                
                text = f"✅ Заказ #{order.id} оформлен!\n\n"
                text += f"📞 Контакт: {contact_info}\n"
                text += f"{delivery_text}\n"
                text += f"💰 Итого: {order.total_price}€\n\n"
                text += "Мы свяжемся с вами в ближайшее время!"
                
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=get_main_menu_kb(is_admin=is_admin(update.effective_user.username))
                )
                
                # Отправляем уведомление админам
                await send_order_notification_to_admin(context, order, user, cart_items, delivery_method, delivery_fee)
                
                context.user_data.clear()
                
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка при создании заказа: {e}")
                context.user_data.clear()
        return
    
    # Иначе показываем меню
    await update.message.reply_text(
        "Используйте меню для навигации",
        reply_markup=get_main_menu_kb(is_admin=is_admin(update.effective_user.username))
    )
