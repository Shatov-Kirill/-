import logging
import sqlite3
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Конфигурация
ADMIN_IDS = [
        1345438940, # ID Ильи
        792396771 # ID Кирилла
    ]
CHANNEL_ID = "-1002364019566"  # ID канала
DATABASE = "bot_db.sqlite" # База данных 

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
(
    CHECK_SUBSCRIPTION, CHOOSE_ROLE,
    SELLER_PLATFORM, SELLER_AUDIENCE, SELLER_THEME, SELLER_VIEWS,
    SELLER_AD_TYPE, SELLER_SCREENSHOT,
    BUYER_PLATFORM, BUYER_CHOOSE_SELLER, BUYER_MESSAGE
) = range(11)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      last_name TEXT,
                      role TEXT,
                      reg_date TIMESTAMP)''')
                      
    cursor.execute('''CREATE TABLE IF NOT EXISTS sellers
                     (seller_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      platform TEXT,
                      audience TEXT,
                      theme TEXT,
                      views TEXT,
                      ad_type TEXT,
                      screenshot_id TEXT,
                      status TEXT DEFAULT 'pending',
                      FOREIGN KEY(user_id) REFERENCES users(user_id))''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_logs
                     (log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      admin_id INTEGER,
                      action TEXT,
                      application_id INTEGER,
                      timestamp TIMESTAMP)''')
    
    conn.commit()
    conn.close()

# Клавиатуры
role_keyboard = [
    [InlineKeyboardButton("Продавец", callback_data='seller')],
    [InlineKeyboardButton("Покупатель", callback_data='buyer')]
]

platform_keyboard = [
    [InlineKeyboardButton("TikTok", callback_data='tiktok')],
    [InlineKeyboardButton("YouTube", callback_data='youtube')],
    [InlineKeyboardButton("Instagram", callback_data='instagram')],
    [InlineKeyboardButton("VK", callback_data='vk')],
    [InlineKeyboardButton("Twitch", callback_data='twitch')]
]

ad_type_keyboard = [
    [InlineKeyboardButton("Продвижение музыки", callback_data='music')],
    [InlineKeyboardButton("Продвижение ТГК", callback_data='tgk')],
    [InlineKeyboardButton("Продвижение товаров", callback_data='products')],
    [InlineKeyboardButton("Продвижение площадок", callback_data='platforms')],
    [InlineKeyboardButton("Продвижение брендов", callback_data='brands')]
]

# --- Основные функции бота ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало взаимодействия с ботом."""
    user = update.effective_user
    
    # Сохраняем/обновляем данные пользователя
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO users 
                      (user_id, username, first_name, last_name, reg_date)
                      VALUES (?, ?, ?, ?, ?)''',
                   (user.id, user.username, user.first_name, 
                    user.last_name, datetime.now()))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"Здравствуйте, {user.first_name}! Перед использованием подпишитесь на наш канал:\n"
        f"https://t.me/nexus_infrek{CHANNEL_ID}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Я подписался", callback_data='check_subscription')]
        ])
    )
    return CHECK_SUBSCRIPTION

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверка подписки на канал."""
    # subscribed = True
    query = update.callback_query
    await query.answer()
    
    try:
        user_id = query.from_user.id
        chat_member = await context.bot.get_chat_member(
            chat_id=CHANNEL_ID, 
            user_id=user_id
        )
        subscribed = chat_member.status in ['member', 'administrator', 'creator']
        
        if subscribed:
            await query.edit_message_text(
                "Спасибо за подписку! Кем вы хотите быть?",
                reply_markup=InlineKeyboardMarkup(role_keyboard))
            return CHOOSE_ROLE
        else:
            await query.edit_message_text(
                "Вы не подписаны на канал. Пожалуйста, подпишитесь и нажмите кнопку снова.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Я подписался", callback_data='check_subscription')]
                ]))
            return CHECK_SUBSCRIPTION
            
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуйте позже.")
        return ConversationHandler.END

async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора роли (продавец/покупатель)."""
    query = update.callback_query
    await query.answer()
    
    # Сохраняем роль в базе данных
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET role=? WHERE user_id=?''',
                   (query.data, query.from_user.id))
    conn.commit()
    conn.close()
    
    if query.data == 'seller':
        await query.edit_message_text(
            "На какой площадке вы готовы выставлять рекламу?",
            reply_markup=InlineKeyboardMarkup(platform_keyboard))
        return SELLER_PLATFORM
    else:
        await query.edit_message_text(
            "Выберите платформу:",
            reply_markup=InlineKeyboardMarkup(platform_keyboard))
        return BUYER_PLATFORM

# --- Функции для продавцов ---

async def seller_platform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора платформы продавцом."""
    query = update.callback_query
    await query.answer()
    
    # Сохраняем временные данные
    if 'user_data' not in context.chat_data:
        context.chat_data['user_data'] = {}
    context.chat_data['user_data']['platform'] = query.data
    
    await query.edit_message_text("Какая аудитория вашего канала? (укажите в 'К', например: 1К, 5.6К)")
    return SELLER_AUDIENCE

async def seller_audience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода аудитории продавцом."""
    context.chat_data['user_data']['audience'] = update.message.text
    await update.message.reply_text("Опишите тематику вашего контента:")
    return SELLER_THEME

async def seller_theme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода тематики контента."""
    context.chat_data['user_data']['theme'] = update.message.text
    await update.message.reply_text("Укажите средние просмотры ваших видео/рилсов (в 'К', например: 30К, 36К):")
    return SELLER_VIEWS

async def seller_views(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода средних просмотров."""
    context.chat_data['user_data']['views'] = update.message.text
    await update.message.reply_text(
        "Какую рекламу вы предлагаете?",
        reply_markup=InlineKeyboardMarkup(ad_type_keyboard))
    return SELLER_AD_TYPE

async def seller_ad_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора типа рекламы."""
    query = update.callback_query
    await query.answer()
    context.chat_data['user_data']['ad_type'] = query.data
    await query.edit_message_text("Скиньте скриншот, подтверждающий, что вы владелец аккаунта.")
    return SELLER_SCREENSHOT

async def seller_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка скриншота и завершение анкеты продавца."""
    user = update.message.from_user
    screenshot_id = update.message.photo[-1].file_id if update.message.photo else None
    
    # Сохраняем заявку в базе данных
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''INSERT INTO sellers 
                      (user_id, platform, audience, theme, views, ad_type, screenshot_id)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''',
                   (user.id, 
                    context.chat_data['user_data']['platform'],
                    context.chat_data['user_data']['audience'],
                    context.chat_data['user_data']['theme'],
                    context.chat_data['user_data']['views'],
                    context.chat_data['user_data']['ad_type'],
                    screenshot_id))
    
    seller_id = cursor.lastrowid
    conn.commit()
    
    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"Новая заявка от @{user.username} (#{seller_id})"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления админа {admin_id}: {e}")
    
    conn.close()
    
    await update.message.reply_text(
        "Заявка отправлена на модерацию. Мы свяжемся с вами в ближайшее время.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/start")]], resize_keyboard=True))
    
    return ConversationHandler.END

# --- Функции для покупателей ---

async def buyer_platform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора платформы покупателем."""
    query = update.callback_query
    await query.answer()
    
    # Получаем продавцов для выбранной платформы из базы данных
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''SELECT user_id, platform, audience, views 
                      FROM sellers 
                      WHERE platform=? AND status='approved' ''',
                   (query.data,))
    sellers = cursor.fetchall()
    conn.close()
    
    if not sellers:
        await query.edit_message_text(
            "На данный момент нет продавцов для выбранной платформы.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Выбрать другую платформу", callback_data='another_platform')]
            ]))
        return BUYER_PLATFORM
    
    # Формируем список продавцов
    seller_list = "\n".join(
        f"{idx+1}. @{seller[0]} | {seller[2]} | {seller[3]}"
        for idx, seller in enumerate(sellers)
    )
    
    # Сохраняем данные для следующего шага
    context.chat_data['sellers'] = sellers
    
    await query.edit_message_text(
        f"Продавцы на {query.data}:\n\n{seller_list}\n\n"
        "Введите номер продавца, которому хотите написать:")
    
    return BUYER_CHOOSE_SELLER

async def buyer_choose_seller(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора продавца покупателем."""
    try:
        seller_num = int(update.message.text) - 1
        sellers = context.chat_data['sellers']
        
        if 0 <= seller_num < len(sellers):
            selected_seller = sellers[seller_num]
            context.chat_data['selected_seller'] = selected_seller

            await update.message.reply_text(
                f"Вы выбрали продавца: @{selected_seller[0]}\n"
                "Напишите ваше сообщение для продавца:")
            return BUYER_MESSAGE
        else:
            await update.message.reply_text("Неверный номер продавца. Пожалуйста, введите корректный номер.")
            return BUYER_CHOOSE_SELLER
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число.")
        return BUYER_CHOOSE_SELLER
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("Ошибка отправки")
async def buyer_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка сообщения покупателя для продавца."""
    message = update.message.text
    user = update.message.from_user
    seller = context.chat_data['selected_seller']
    
    # Пересылаем сообщение продавцу
    try:
        await context.bot.send_message(
            chat_id=seller[0],  # ID продавца
            text=f"Сообщение от @{user.username}:\n\n{message}"
        )
        
        await update.message.reply_text(
            "Ваше сообщение отправлено продавцу. Он свяжется с вами в ближайшее время.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/start")]], resize_keyboard=True))
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения продавцу: {e}")
        await update.message.reply_text("Произошла ошибка при отправке сообщения.")
    
    return ConversationHandler.END

# --- Админ-панель ---

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель управления для администраторов"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Доступ запрещен")
        return
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Получаем заявки на модерацию
    cursor.execute('''SELECT s.seller_id, u.username, s.platform, s.audience, s.views 
                      FROM sellers s
                      JOIN users u ON s.user_id = u.user_id
                      WHERE s.status='pending' ''')
    applications = cursor.fetchall()
    
    if not applications:
        await update.message.reply_text("Нет заявок на модерацию")
        return
    
    for app in applications:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{app[0]}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app[0]}")]
        ])
        
        await update.message.reply_text(
            f"Заявка #{app[0]}\n"
            f"Пользователь: @{app[1]}\n"
            f"Платформа: {app[2]}\n"
            f"Аудитория: {app[3]}\n"
            f"Просмотры: {app[4]}\n",
            reply_markup=keyboard
        )
    
    conn.close()

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка действий администратора"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("Доступ запрещен")
        return
    
    action, app_id = query.data.split('_')
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    if action == 'approve':
        cursor.execute("UPDATE sellers SET status='approved' WHERE seller_id=?", (app_id,))
        
        # Получаем данные пользователя для уведомления
        cursor.execute('''SELECT u.user_id, u.username 
                          FROM sellers s
                          JOIN users u ON s.user_id = u.user_id
                          WHERE s.seller_id=?''', (app_id,))
        user_data = cursor.fetchone()
        
        if user_data:
            try:
                await context.bot.send_message(
                    chat_id=user_data[0],
                    text="✅ Ваша заявка одобрена! Теперь вы можете принимать заказы."

)
            except Exception as e:
                logger.error(f"Ошибка уведомления пользователя: {e}")
        
        # Логируем действие
        cursor.execute('''INSERT INTO admin_logs 
                          (admin_id, action, application_id, timestamp)
                          VALUES (?, ?, ?, ?)''',
                       (query.from_user.id, 'approve', app_id, datetime.now()))
        
    elif action == 'reject':
        cursor.execute("UPDATE sellers SET status='rejected' WHERE seller_id=?", (app_id,))
        
        # Логируем действие
        cursor.execute('''INSERT INTO admin_logs 
                          (admin_id, action, application_id, timestamp)
                          VALUES (?, ?, ?, ?)''',
                       (query.from_user.id, 'reject', app_id, datetime.now()))
    
    conn.commit()
    conn.close()
    await query.edit_message_text(f"Заявка #{app_id} обработана")

# --- Вспомогательные функции ---

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершение диалога."""
    await update.message.reply_text(
        "Диалог завершен. Нажмите /start чтобы начать заново.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/start")]], resize_keyboard=True))
    return ConversationHandler.END

# async def get_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     if update.effective_chat.type == "channel":
#         await update.message.reply_text(f"ID этого канала: {update.effective_chat.id}")
#     else:
#         await update.message.reply_text(f"Эта команда работает только в каналах!")

def backup_db():
    """Создание резервной копии базы данных"""
    from datetime import datetime
    import shutil
    
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.sqlite"
    shutil.copy2(DATABASE, backup_name)
    return backup_name

# --- Запуск бота ---

def main() -> None:
    """Запуск бота."""
    # Инициализация базы данных
    init_db()
    
    # Создаем Application
    application = Application.builder().token("7423580380:AAEchqJy_1Kn4O20V2nAGE2pjzW4c-O5qhw").build()
    
    # Настраиваем обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHECK_SUBSCRIPTION: [
                CallbackQueryHandler(check_subscription, pattern='^check_subscription$')
            ],
            CHOOSE_ROLE: [
                CallbackQueryHandler(choose_role, pattern='^(seller|buyer)$')
            ],
            SELLER_PLATFORM: [
                CallbackQueryHandler(seller_platform, pattern='^(tiktok|youtube|instagram|vk|twitch)$')
            ],
            SELLER_AUDIENCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, seller_audience)
            ],
            SELLER_THEME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, seller_theme)
            ],
            SELLER_VIEWS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, seller_views)
            ],
            SELLER_AD_TYPE: [
                CallbackQueryHandler(seller_ad_type, pattern='^(music|tgk|products|platforms|brands)$')
            ],
            SELLER_SCREENSHOT: [
                MessageHandler(filters.PHOTO | filters.TEXT, seller_screenshot)
            ],
            BUYER_PLATFORM: [
                CallbackQueryHandler(buyer_platform, pattern='^(tiktok|youtube|instagram|vk|twitch|another_platform)$')
            ],
            BUYER_CHOOSE_SELLER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, buyer_choose_seller)
            ],
            BUYER_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, buyer_message)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False # Дo исправления было False
    )
    
    # Регистрируем обработчики
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('admin', admin_panel))
    application.add_handler(CallbackQueryHandler(admin_action, pattern='^(approve|reject)_\d+$'))
    
    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()