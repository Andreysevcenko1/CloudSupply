"""
CRUD операции для работы с базой данных
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func
from .models import User, Model, Product, Cart, Order, OrderItem, BotSettings
from typing import Optional, List
from datetime import datetime


# ==================== USERS ====================

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: Optional[str] = None, 
                             first_name: Optional[str] = None, last_name: Optional[str] = None) -> User:
    """Получить пользователя или создать нового"""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Получить пользователя по telegram_id"""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def ban_user(session: AsyncSession, user_id: int, ban: bool = True):
    """Забанить/разбанить пользователя"""
    await session.execute(
        update(User).where(User.id == user_id).values(is_banned=ban)
    )
    await session.commit()


async def get_all_users(session: AsyncSession) -> List[User]:
    """Получить всех пользователей"""
    result = await session.execute(select(User))
    return result.scalars().all()


# ==================== MODELS ====================

async def create_model(session: AsyncSession, name: str, description: Optional[str] = None, 
                      image_path: Optional[str] = None, cost_price: float = 0.0) -> Model:
    """Создать новую модель"""
    model = Model(
        name=name,
        description=description,
        image_path=image_path,
        cost_price=cost_price
    )
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return model


async def get_all_models(session: AsyncSession, available_only: bool = True) -> List[Model]:
    """Получить все модели"""
    query = select(Model)
    if available_only:
        query = query.where(Model.is_available == True)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_model_by_id(session: AsyncSession, model_id: int) -> Optional[Model]:
    """Получить модель по ID"""
    result = await session.execute(select(Model).where(Model.id == model_id))
    return result.scalar_one_or_none()


async def update_model(session: AsyncSession, model_id: int, **kwargs):
    """Обновить модель"""
    await session.execute(
        update(Model).where(Model.id == model_id).values(**kwargs)
    )
    await session.commit()


async def delete_model(session: AsyncSession, model_id: int):
    """Удалить модель"""
    await session.execute(delete(Model).where(Model.id == model_id))
    await session.commit()


# ==================== PRODUCTS ====================

async def create_product(session: AsyncSession, model_id: int, flavor_name: str, 
                        price: float, stock_quantity: int = 0) -> Product:
    """Создать новый продукт (вкус)"""
    product = Product(
        model_id=model_id,
        flavor_name=flavor_name,
        price=price,
        stock_quantity=stock_quantity
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def get_products_by_model(session: AsyncSession, model_id: int, available_only: bool = True) -> List[Product]:
    """Получить все вкусы для модели"""
    query = select(Product).where(Product.model_id == model_id)
    if available_only:
        query = query.where(and_(Product.is_available == True, Product.stock_quantity > 0))
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_product_by_id(session: AsyncSession, product_id: int) -> Optional[Product]:
    """Получить продукт по ID"""
    result = await session.execute(select(Product).where(Product.id == product_id))
    return result.scalar_one_or_none()


async def update_product(session: AsyncSession, product_id: int, **kwargs):
    """Обновить продукт"""
    await session.execute(
        update(Product).where(Product.id == product_id).values(**kwargs)
    )
    await session.commit()


async def update_stock(session: AsyncSession, product_id: int, quantity_change: int):
    """Обновить количество на складе (+ или -)"""
    product = await get_product_by_id(session, product_id)
    if product:
        new_quantity = product.stock_quantity + quantity_change
        await update_product(session, product_id, stock_quantity=max(0, new_quantity))


async def delete_product(session: AsyncSession, product_id: int):
    """Удалить продукт"""
    await session.execute(delete(Product).where(Product.id == product_id))
    await session.commit()


# ==================== CART ====================

async def add_to_cart(session: AsyncSession, user_id: int, product_id: int, quantity: int = 1) -> Cart:
    """Добавить товар в корзину"""
    # Сначала объединяем возможные дубликаты
    await merge_duplicate_cart_items(session, user_id)
    
    # Проверяем есть ли уже такой товар в корзине с блокировкой для предотвращения race condition
    result = await session.execute(
        select(Cart).where(and_(Cart.user_id == user_id, Cart.product_id == product_id)).with_for_update()
    )
    cart_item = result.scalar_one_or_none()
    
    if cart_item:
        # Увеличиваем количество
        cart_item.quantity += quantity
    else:
        # Создаем новый элемент корзины
        cart_item = Cart(user_id=user_id, product_id=product_id, quantity=quantity)
        session.add(cart_item)
    
    await session.commit()
    await session.refresh(cart_item)
    return cart_item


async def get_user_cart(session: AsyncSession, user_id: int) -> List[Cart]:
    """Получить корзину пользователя"""
    # Сначала объединяем дубликаты товаров в корзине
    await merge_duplicate_cart_items(session, user_id)
    
    # Получаем корзину одним запросом
    result = await session.execute(
        select(Cart).where(Cart.user_id == user_id).order_by(Cart.id)
    )
    return result.scalars().all()


async def merge_duplicate_cart_items(session: AsyncSession, user_id: int):
    """Объединить дубликаты товаров в корзине"""
    # Получаем все элементы корзины отсортированные по ID (старые первыми)
    result = await session.execute(
        select(Cart).where(Cart.user_id == user_id).order_by(Cart.id)
    )
    cart_items = result.scalars().all()
    
    if len(cart_items) <= 1:
        return  # Нечего объединять
    
    # Группируем по product_id
    product_groups = {}
    for item in cart_items:
        if item.product_id in product_groups:
            product_groups[item.product_id].append(item)
        else:
            product_groups[item.product_id] = [item]
    
    # Объединяем дубликаты
    has_changes = False
    for product_id, items in product_groups.items():
        if len(items) > 1:
            has_changes = True
            # Оставляем первый элемент (самый старый), увеличиваем его количество
            total_quantity = sum(item.quantity for item in items)
            first_item = items[0]
            first_item.quantity = total_quantity
            
            # Удаляем остальные дубликаты
            for item in items[1:]:
                await session.delete(item)
    
    if has_changes:
        await session.commit()


async def update_cart_item_quantity(session: AsyncSession, cart_id: int, quantity: int):
    """Обновить количество товара в корзине"""
    if quantity <= 0:
        await session.execute(delete(Cart).where(Cart.id == cart_id))
    else:
        await session.execute(
            update(Cart).where(Cart.id == cart_id).values(quantity=quantity)
        )
    await session.commit()


async def remove_from_cart(session: AsyncSession, cart_id: int):
    """Удалить товар из корзины"""
    await session.execute(delete(Cart).where(Cart.id == cart_id))
    await session.commit()


async def clear_user_cart(session: AsyncSession, user_id: int):
    """Очистить всю корзину пользователя"""
    await session.execute(delete(Cart).where(Cart.user_id == user_id))
    await session.commit()


# ==================== ORDERS ====================

async def create_order(session: AsyncSession, user_id: int, cart_items: List[Cart], 
                      contact_info: Optional[str] = None, delivery_method: str = 'pickup', 
                      delivery_fee: float = 0.0) -> Order:
    """Создать заказ из корзины"""
    # Проверяем есть ли активный заказ "В процессе" у пользователя
    result = await session.execute(
        select(Order).where(
            and_(Order.user_id == user_id, Order.status == 'processing')
        ).order_by(Order.created_at.desc())
    )
    existing_order = result.scalars().first()
    
    if existing_order:
        # Добавляем товары к существующему заказу
        total_price_add = 0.0
        
        for cart_item in cart_items:
            product = await get_product_by_id(session, cart_item.product_id)
            if product and product.is_available and product.stock_quantity >= cart_item.quantity:
                item_price = product.price * cart_item.quantity
                total_price_add += item_price
                
                # Проверяем есть ли уже такой товар в заказе
                existing_item_result = await session.execute(
                    select(OrderItem).where(
                        and_(
                            OrderItem.order_id == existing_order.id,
                            OrderItem.product_id == product.id,
                            OrderItem.price_at_order == product.price
                        )
                    )
                )
                existing_items = existing_item_result.scalars().all()
                
                if existing_items:
                    # Увеличиваем количество в первой записи
                    existing_items[0].quantity += cart_item.quantity
                    
                    # Удаляем остальные дубликаты если есть
                    for duplicate in existing_items[1:]:
                        await session.delete(duplicate)
                else:
                    # Создаем новую запись
                    order_item = OrderItem(
                        order_id=existing_order.id,
                        product_id=product.id,
                        quantity=cart_item.quantity,
                        price_at_order=product.price
                    )
                    session.add(order_item)
                
                # Уменьшаем количество на складе
                await update_stock(session, product.id, -cart_item.quantity)
        
        # Обновляем общую сумму заказа
        existing_order.total_price += total_price_add
        await session.commit()
        
        # Очищаем корзину
        await clear_user_cart(session, user_id)
        
        return existing_order
    
    else:
        # Создаем новый заказ
        total_price = 0.0
        order_items_list = []
        
        for cart_item in cart_items:
            product = await get_product_by_id(session, cart_item.product_id)
            if product and product.is_available and product.stock_quantity >= cart_item.quantity:
                item_price = product.price * cart_item.quantity
                total_price += item_price
                
                order_items_list.append({
                    'product_id': product.id,
                    'quantity': cart_item.quantity,
                    'price_at_order': product.price
                })
                
                # Уменьшаем количество на складе
                await update_stock(session, product.id, -cart_item.quantity)
        
        # Добавляем стоимость доставки
        total_price += delivery_fee
        
        # Создаем заказ
        order = Order(
            user_id=user_id,
            total_price=total_price,
            contact_info=contact_info,
            delivery_method=delivery_method,
            delivery_fee=delivery_fee
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        
        # Добавляем товары в заказ
        for item_data in order_items_list:
            order_item = OrderItem(
                order_id=order.id,
                **item_data
            )
            session.add(order_item)
        
        await session.commit()
        
        # Очищаем корзину
        await clear_user_cart(session, user_id)
        
        return order


async def get_order_by_id(session: AsyncSession, order_id: int) -> Optional[Order]:
    """Получить заказ по ID"""
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    return order


async def merge_duplicate_order_items(session: AsyncSession, order_id: int):
    """Объединить дубликаты товаров в заказе"""
    result = await session.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    order_items = result.scalars().all()
    
    # Группируем по product_id и price_at_order
    product_groups = {}
    for item in order_items:
        key = (item.product_id, item.price_at_order)
        if key in product_groups:
            product_groups[key].append(item)
        else:
            product_groups[key] = [item]
    
    # Объединяем дубликаты
    for key, items in product_groups.items():
        if len(items) > 1:
            # Оставляем первый элемент, увеличиваем его количество
            total_quantity = sum(item.quantity for item in items)
            first_item = items[0]
            first_item.quantity = total_quantity
            
            # Удаляем остальные
            for item in items[1:]:
                await session.delete(item)
    
    await session.commit()


async def get_user_orders(session: AsyncSession, user_id: int) -> List[Order]:
    """Получить все заказы пользователя"""
    result = await session.execute(
        select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    )
    return result.scalars().all()


async def get_all_orders(session: AsyncSession) -> List[Order]:
    """Получить все заказы"""
    result = await session.execute(select(Order).order_by(Order.created_at.desc()))
    return result.scalars().all()


async def update_order_status(session: AsyncSession, order_id: int, status: str):
    """Обновить статус заказа"""
    await session.execute(
        update(Order).where(Order.id == order_id).values(status=status, updated_at=datetime.utcnow())
    )
    await session.commit()


async def delete_order(session: AsyncSession, order_id: int):
    """Удалить заказ и вернуть товары на склад"""
    # Получаем заказ и его товары
    order = await get_order_by_id(session, order_id)
    if not order:
        return False
    
    # Получаем товары в заказе
    items_result = await session.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    items = items_result.scalars().all()
    
    # Возвращаем товары на склад
    for item in items:
        await update_stock(session, item.product_id, item.quantity)
    
    # Удаляем заказ (OrderItems удалятся автоматически через cascade)
    await session.execute(delete(Order).where(Order.id == order_id))
    await session.commit()
    return True


# ==================== BOT SETTINGS ====================

async def get_setting(session: AsyncSession, key: str) -> Optional[str]:
    """Получить настройку бота"""
    result = await session.execute(select(BotSettings).where(BotSettings.setting_key == key))
    setting = result.scalar_one_or_none()
    return setting.setting_value if setting else None


async def update_setting(session: AsyncSession, key: str, value: str):
    """Обновить настройку бота"""
    result = await session.execute(select(BotSettings).where(BotSettings.setting_key == key))
    setting = result.scalar_one_or_none()
    
    if setting:
        await session.execute(
            update(BotSettings).where(BotSettings.setting_key == key).values(
                setting_value=value,
                updated_at=datetime.utcnow()
            )
        )
    else:
        new_setting = BotSettings(setting_key=key, setting_value=value)
        session.add(new_setting)
    
    await session.commit()


# ==================== STATISTICS ====================

async def get_total_revenue(session: AsyncSession) -> float:
    """Получить общую выручку"""
    result = await session.execute(
        select(func.sum(Order.total_price)).where(Order.status.in_(['completed', 'processing']))
    )
    total = result.scalar_one_or_none()
    return total or 0.0


async def get_total_orders_count(session: AsyncSession) -> int:
    """Получить общее количество заказов"""
    result = await session.execute(select(func.count(Order.id)))
    return result.scalar_one_or_none() or 0


async def get_revenue_and_profit(session: AsyncSession) -> dict:
    """Получить выручку и прибыль (прибыль = (цена - себестоимость) * кол-во + доставка)"""
    # Получаем все завершенные заказы
    result = await session.execute(
        select(Order).where(Order.status.in_(['completed', 'processing']))
    )
    orders = result.scalars().all()
    
    total_revenue = 0.0
    total_cost = 0.0
    total_profit = 0.0
    
    for order in orders:
        total_revenue += order.total_price
        
        # Получаем товары в заказе
        items_result = await session.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = items_result.scalars().all()
        
        order_profit = 0.0
        for item in items:
            product = await get_product_by_id(session, item.product_id)
            if product:
                model = await get_model_by_id(session, product.model_id)
                if model:
                    # Себестоимость за весь товар
                    item_cost = model.cost_price * item.quantity
                    total_cost += item_cost
                    
                    # Прибыль = (цена - себестоимость) * количество
                    order_profit += (product.price - model.cost_price) * item.quantity
        
        # Добавляем доставку к прибыли (если есть)
        if order.delivery_fee > 0:
            order_profit += order.delivery_fee
        
        total_profit += order_profit
    
    return {
        'revenue': total_revenue,
        'cost': total_cost,
        'profit': total_profit
    }


async def get_top_products(session: AsyncSession, limit: int = 5) -> List[dict]:
    """Получить топ продаваемых товаров"""
    result = await session.execute(
        select(
            OrderItem.product_id,
            func.sum(OrderItem.quantity).label('total_sold')
        ).group_by(OrderItem.product_id).order_by(func.sum(OrderItem.quantity).desc()).limit(limit)
    )
    
    top_products = []
    for row in result:
        product = await get_product_by_id(session, row.product_id)
        if product:
            top_products.append({
                'product': product,
                'total_sold': row.total_sold
            })
    
    return top_products


# ==================== BOT SETTINGS ====================

async def get_maintenance_mode(session: AsyncSession) -> bool:
    """Проверить включен ли режим тех. работ"""
    result = await session.execute(
        select(BotSettings).where(BotSettings.setting_key == 'maintenance_mode')
    )
    setting = result.scalar_one_or_none()
    
    if not setting:
        # Если настройка не найдена, создаем с выключенным режимом
        setting = BotSettings(setting_key='maintenance_mode', setting_value='false')
        session.add(setting)
        await session.commit()
        return False
    
    return setting.setting_value.lower() == 'true'


async def set_maintenance_mode(session: AsyncSession, enabled: bool):
    """Установить режим тех. работ"""
    result = await session.execute(
        select(BotSettings).where(BotSettings.setting_key == 'maintenance_mode')
    )
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.setting_value = 'true' if enabled else 'false'
        setting.updated_at = datetime.utcnow()
    else:
        setting = BotSettings(
            setting_key='maintenance_mode',
            setting_value='true' if enabled else 'false'
        )
        session.add(setting)
    
    await session.commit()
