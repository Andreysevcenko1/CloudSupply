"""
Inline клавиатуры для python-telegram-bot
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ==================== ГЛАВНОЕ МЕНЮ ====================

def get_main_menu_kb(is_admin: bool = False):
    """Главное меню бота"""
    keyboard = [
        [InlineKeyboardButton("🛍 Выбрать модель", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Корзина", callback_data="cart")],
        [InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")],
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_kb():
    """Простая клавиатура с кнопками возврата"""
    keyboard = [
        [InlineKeyboardButton("🛍 Выбрать модель", callback_data="catalog")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_after_add_to_cart_kb():
    """Клавиатура после добавления в корзину"""
    keyboard = [
        [InlineKeyboardButton("🛒 Просмотреть корзину", callback_data="cart")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== КАТАЛОГ ====================

def get_models_kb(models):
    """Клавиатура с моделями вейпов"""
    keyboard = []
    
    for model in models:
        keyboard.append([InlineKeyboardButton(model.name, callback_data=f"model_{model.id}")])
    
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_products_kb(products, model_id):
    """Клавиатура с вкусами для модели"""
    keyboard = []
    
    for product in products:
        stock_text = f" (осталось {product.stock_quantity})" if product.stock_quantity < 10 else ""
        text = f"{product.flavor_name} - {product.price}€{stock_text}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"product_{product.id}")])
    
    keyboard.append([InlineKeyboardButton("◀️ К моделям", callback_data="catalog")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_product_quantity_kb(product_id):
    """Клавиатура для товара (без выбора количества - теперь вводится вручную)"""
    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_products")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


# ==================== КОРЗИНА ====================

def get_cart_kb(cart_items_data, has_items=True):
    """Клавиатура корзины
    cart_items_data: список кортежей (item, product, model) или пустой список
    """
    keyboard = []
    
    if has_items and cart_items_data:
        for item, product, model in cart_items_data:
            text = f"❌ {product.flavor_name} ({item.quantity} шт)"
            keyboard.append([InlineKeyboardButton(text, callback_data=f"removecart_{item.id}")])
        
        keyboard.append([InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout")])
        keyboard.append([InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart")])
    
    keyboard.append([InlineKeyboardButton("🛍 Продолжить покупки", callback_data="catalog")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_delivery_method_kb():
    """Выбор способа доставки"""
    keyboard = [
        [InlineKeyboardButton("🏃 Самовывоз (бесплатно)", callback_data="delivery_pickup")],
        [InlineKeyboardButton("🚚 Доставка (+5€)", callback_data="delivery_delivery")],
        [InlineKeyboardButton("❌ Отменить", callback_data="cart")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_confirm_order_kb(delivery_method: str):
    """Подтверждение оформления заказа"""
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить заказ", callback_data=f"confirm_order_{delivery_method}")],
        [InlineKeyboardButton("◀️ Изменить доставку", callback_data="checkout")],
        [InlineKeyboardButton("❌ Отменить", callback_data="cart")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


# ==================== ЗАКАЗЫ ====================

def get_orders_kb(orders):
    """Клавиатура со списком заказов"""
    keyboard = []
    
    # Проверяем формат данных (список кортежей или просто заказов)
    if orders and isinstance(orders[0], tuple):
        # Формат: [(order, user), ...]
        for order, user in orders:
            status_emoji = {
                'processing': '📦',
                'completed': '✅'
            }.get(order.status, '❓')
            
            username = f"@{user.username}" if user and user.username else ("👤 " + (user.first_name if user else "Неизвестно"))
            text = f"{status_emoji} #{order.id} {username} - {order.total_price}€"
            keyboard.append([InlineKeyboardButton(text, callback_data=f"order_{order.id}")])
    else:
        # Формат: [order, ...] (без информации о пользователе)
        for order in orders:
            status_emoji = {
                'processing': '📦',
                'completed': '✅'
            }.get(order.status, '❓')
            
            text = f"{status_emoji} Заказ #{order.id} - {order.total_price}€"
            keyboard.append([InlineKeyboardButton(text, callback_data=f"order_{order.id}")])
    
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)


def get_order_detail_kb(order_id, is_admin=False, is_processing=False):
    """Детали заказа"""
    keyboard = []
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("✏️ Изменить статус", callback_data=f"change_status_{order_id}")])
        keyboard.append([InlineKeyboardButton("◀️ К заказам", callback_data="admin_orders")])
        keyboard.append([InlineKeyboardButton("🏠 Админ-панель", callback_data="admin_panel")])
    else:
        # Если заказ в процессе - добавляем кнопку редактирования
        if is_processing:
            keyboard.append([InlineKeyboardButton("➕ Добавить товары", callback_data="catalog")])
        keyboard.append([InlineKeyboardButton("◀️ К заказам", callback_data="my_orders")])
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)


# ==================== АДМИН ПАНЕЛЬ ====================

def get_admin_panel_kb():
    """Админ панель"""
    keyboard = [
        [InlineKeyboardButton("📦 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton("🎨 Товары", callback_data="admin_products")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("💾 Бэкап БД", callback_data="admin_backup")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_admin_products_kb():
    """Управление товарами"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить модель", callback_data="admin_add_model")],
        [InlineKeyboardButton("➕ Добавить вкус", callback_data="admin_add_product")],
        [InlineKeyboardButton("📱 Просмотреть модели/вкусы", callback_data="admin_view_models")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_order_status_kb(order_id):
    """Изменение статуса заказа"""
    keyboard = [
        [InlineKeyboardButton("📦 В процессе", callback_data=f"setstatus_{order_id}_processing")],
        [InlineKeyboardButton("✅ Готов", callback_data=f"setstatus_{order_id}_completed")],
        [InlineKeyboardButton("🗑 Удалить заказ", callback_data=f"delete_order_{order_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_orders")]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_admin_users_kb(users):
    """Список пользователей"""
    keyboard = []
    
    for user in users[:10]:
        status = "🚫" if user.is_banned else "✅"
        text = f"{status} {user.username or user.first_name or f'ID{user.telegram_id}'}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"admin_user_{user.id}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)


def get_admin_user_actions_kb(user_id, is_banned):
    """Действия с пользователем"""
    keyboard = []
    
    if is_banned:
        keyboard.append([InlineKeyboardButton("✅ Разбанить", callback_data=f"admin_unban_{user_id}")])
    else:
        keyboard.append([InlineKeyboardButton("🚫 Забанить", callback_data=f"admin_ban_{user_id}")])
    
    keyboard.append([InlineKeyboardButton("◀️ К пользователям", callback_data="admin_users")])
    
    return InlineKeyboardMarkup(keyboard)


# ==================== ПОДДЕРЖКА ====================

def get_support_kb(support_username):
    """Кнопка связи с поддержкой"""
    keyboard = [
        [InlineKeyboardButton("📞 Написать в поддержку", url=f"https://t.me/{support_username}")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    
    return InlineKeyboardMarkup(keyboard)
