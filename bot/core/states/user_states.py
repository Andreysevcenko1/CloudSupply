"""
FSM States для бота (управление состояниями диалогов)
Для python-telegram-bot используются простые строковые константы
"""

# Order states
ORDER_WAITING_CONTACT = "order_waiting_contact"
ORDER_WAITING_CONFIRMATION = "order_waiting_confirmation"

# Admin add model states
ADMIN_ADD_MODEL_NAME = "admin_add_model_name"
ADMIN_ADD_MODEL_DESCRIPTION = "admin_add_model_description"
ADMIN_ADD_MODEL_COST = "admin_add_model_cost"
ADMIN_ADD_MODEL_IMAGE = "admin_add_model_image"

# Admin add product states
ADMIN_ADD_PRODUCT_MODEL = "admin_add_product_model"
ADMIN_ADD_PRODUCT_FLAVOR = "admin_add_product_flavor"
ADMIN_ADD_PRODUCT_PRICE = "admin_add_product_price"
ADMIN_ADD_PRODUCT_STOCK = "admin_add_product_stock"

# Admin edit product states
ADMIN_EDIT_PRODUCT_ID = "admin_edit_product_id"
ADMIN_EDIT_PRODUCT_FIELD = "admin_edit_product_field"
ADMIN_EDIT_PRODUCT_VALUE = "admin_edit_product_value"

# Admin settings states
ADMIN_SETTINGS_KEY = "admin_settings_key"
ADMIN_SETTINGS_VALUE = "admin_settings_value"
