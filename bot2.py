import logging
import sqlite3
import os
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
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

# Активные переписки в памяти. Это отдельная переменная.
active_chats = {}

# Заблокированные пользователи
banned_users = set()

# --- Конфигурация ---
class Config:
    ADMIN_IDS = [1345438940, 792396771]  # ID админов
    CHANNEL_ID = "-1002364019566"        # ID канала
    CHANNEL_USERNAME = "nexus_infrek"
    DATABASE = "bot_db.sqlite"           # Путь к БД
    TOKEN = "7423580380:AAEchqJy_1Kn4O20V2nAGE2pjzW4c-O5qhw"
    ADMIN_CHAT_ID = "-4703103295"

def generate_channel_links (username: str):
    return{
        "mobile": f"https://t.me/{username}?embed=1",
        "web": f"https://web.telegram.org/k/#@{username}",
        'universal': f"https://t.me/{username}",
        'fallback': f"https://t.me/{username}"
    }

def adapt_datetime(dt):
    return dt.isoformat()

sqlite3.register_adapter(datetime, adapt_datetime)


CANCEL_KEYWORDS = ['отмена', 'стоп']
def cancel_if_requested(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Обрабатываем только сообщения (не callback'и)
        message = update.message

        #Если не текстовое сообщение пропускаем проверку
        if not message or not message.text:
            return await func(update, context)
        
        text = update.message.text.strip().lower()  

        if text in CANCEL_KEYWORDS:  
            user = update.effective_user  
            context.user_data.clear()  
            print(f"[ОТМЕНА] Пользователь {user.id} отменил процесс.")  
            await update.message.reply_text("❌ Заявка отменена. Вы можете начать заново командой /start.")  
            return ConversationHandler.END  

        return await func(update, context)  
    return wrapper

def get_default_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("/start")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# --- Настройка логгирования ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def log_sql(query, params=None):
    """Логирование SQL запросов"""
    logger.debug(f"SQL: {query} {f'with params {params}' if params else ''}")


# import sqlite3
# conn = sqlite3.connect("bot_db.sqlite")
# cursor = conn.cursor()
# cursor.execute("SELECT seller_id, user_id, platform_usercode FROM sellers")
# rows = cursor.fetchall()
# print("ID | USER_ID | PLATFORM_USERCODE")
# for row in rows:
#     print(row)
# conn.close()


# import sqlite3
# conn = sqlite3.connect("bot_db.sqlite")
# cursor = conn.cursor()
# cursor.execute("ALTER TABLE sellers ADD COLUMN platform_usercode TEXT;")
# conn.commit()
# conn.close()

# import sqlite3
# conn = sqlite3.connect("bot_db.sqlite")  # проверь путь!
# cursor = conn.cursor()
# cursor.execute("ALTER TABLE sellers ADD COLUMN reject_reason TEXT;")
# conn.commit()
# conn.close()
# print("Поле reject_reason добавлено!")

# import sqlite3
# conn = sqlite3.connect("bot_db.sqlite")
# cursor = conn.cursor()
# try:
#     cursor.execute("ALTER TABLE sellers ADD COLUMN nickname TEXT;")
# except sqlite3.OperationalError:
#     print("Поле 'nickname' уже существует")

# try:
#     cursor.execute("ALTER TABLE sellers ADD COLUMN platform_usercode TEXT;")
# except sqlite3.OperationalError:
#     print("Поле 'platform_usercode' уже существует")
# conn.commit()
# conn.close()
# print("Обновление завершено.")

# import sqlite3
# conn = sqlite3.connect("bot_db.sqlite")
# cursor = conn.cursor()
# try:
#     cursor.execute("ALTER TABLE sellers ADD COLUMN deals INTEGER DEFAULT 0;")
# except sqlite3.OperationalError as e:
#     print("Поле deals уже существует:", e)
# try:
#     cursor.execute("ALTER TABLE sellers ADD COLUMN rating REAL;")
# except sqlite3.OperationalError as e:
#     print("Поле rating уже существует:", e)
# conn.commit()
# conn.close()
# print("Готово.")

# def upgrade_db():
#     try:
#         conn = sqlite3.connect(Config.DATABASE)
#         cursor = conn.cursor()

#         try:
#             cursor.execute("ALTER TABLE sellers ADD COLUMN deals INTEGER DEFAULT 0;")
#             print("✅ Добавлен столбец 'deals'.")
#         except sqlite3.OperationalError as e:
#             print(f"⚠️ Столбец 'deals' уже существует или ошибка: {e}")

#         try:
#             cursor.execute("ALTER TABLE sellers ADD COLUMN rating REAL DEFAULT 0;")
#             print("✅ Добавлен столбец 'rating'.")
#         except sqlite3.OperationalError as e:
#             print(f"⚠️ Столбец 'rating' уже существует или ошибка: {e}")

#         # Создание таблицы сделок
#         cursor.execute('''CREATE TABLE IF NOT EXISTS deals (
#             deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
#             buyer_id INTEGER,
#             seller_id INTEGER,
#             status TEXT,
#             payment_type TEXT,
#             buyer_confirmed BOOLEAN DEFAULT 0,
#             seller_confirmed BOOLEAN DEFAULT 0,
#             rating INTEGER,
#             comment TEXT,
#             timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#         );''')
#         print("✅ Таблица 'deals' создана (если не существовала).")

#         conn.commit()
#     except Exception as e:
#         print(f"❌ Ошибка при обновлении БД: {e}")
#     finally:
#         conn.close()
# # Запускаем функцию
# upgrade_db()

# conn = sqlite3.connect("bot_db.sqlite")
# cursor = conn.cursor()
# # Добавляем колонку nickname, если её ещё нет
# cursor.execute("ALTER TABLE users ADD COLUMN nickname TEXT;")
# conn.commit()
# conn.close()
# print("✅ Колонка nickname добавлена в таблицу users.")

# --- Состояния ConversationHandler ---
(
    CHECK_SUBSCRIPTION, CHOOSE_ROLE,
    SELLER_PLATFORM, SELLER_AUDIENCE, SELLER_THEME, SELLER_VIEWS,
    SELLER_AD_TYPE, SELLER_SCREENSHOT, SELLER_CONFIRM,
    BUYER_PLATFORM, SELLER_NICKNAME, BUYER_CHOOSE_SELLER, BUYER_MESSAGE,
    REJECT_REASON, ADMIN_PANEL, SELLER_CUSTOM_AD_TYPE,
    SELLER_REPLY, DIALOG, SELLER_USERCODE, SHOW_SELLER_PROFILE,
    CHOOSE_BUYER_NICKNAME
) = range(21)
# Здесь был REPLY_TO_BUYER вместо SELLER_REPLY


# --- Клавиатуры ---
KEYBOARDS = {
    'role': [
        [InlineKeyboardButton("Продавец", callback_data='seller')],
        [InlineKeyboardButton("Покупатель", callback_data='buyer')]
    ],
    'platform': [
        [InlineKeyboardButton("TikTok", callback_data='tiktok')],
        [InlineKeyboardButton("YouTube", callback_data='youtube')],
        [InlineKeyboardButton("Instagram", callback_data='instagram')],
        [InlineKeyboardButton("VK", callback_data='vk')],
        [InlineKeyboardButton("Twitch", callback_data='twitch')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_roles')]
    ],
    'ad_type': [
        [InlineKeyboardButton("Продвижение музыки", callback_data='music')],
        [InlineKeyboardButton("Продвижение ТГК", callback_data='tgk')],
        [InlineKeyboardButton("Продвижение товаров", callback_data='products')],
        [InlineKeyboardButton("Продвижение площадок", callback_data='platforms')],
        [InlineKeyboardButton("Продвижение брендов", callback_data='brands')],
        [InlineKeyboardButton("❓ Другое", callback_data='custom_ad')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_views')]
    ],
    'confirm': [
        [InlineKeyboardButton("✅ Подтвердить", callback_data='confirm_application')],
        [InlineKeyboardButton("❌ Изменить", callback_data='edit_application')]
    ]
}

#Кнопка завершения диалога. Она находится под полем ввода сообщения в телеграмме.
dialog_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("💰 Начать оплату"), KeyboardButton("💼 Эксроу-счет")],
        [KeyboardButton("❌ Завершить диалог")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# --- Инициализация БД ---
def init_db():
    try:
        conn = sqlite3.connect(Config.DATABASE, timeout=20)
        conn.execute("PRAGMA journal_mode=WAL")
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
                          reject_reason TEXT,
                          FOREIGN KEY(user_id) REFERENCES users(user_id))''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS admin_logs
                          (log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                          admin_id INTEGER,
                          action TEXT,
                          application_id INTEGER,
                          timestamp TIMESTAMP)''')
        
        # Создаем индексы для ускорения запросов
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_sellers_platform ON sellers(platform)''')
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_sellers_status ON sellers(status)''')
        
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise
    finally:
        conn.close() if 'conn' in locals() else None

# --- Вспомогательные функции ---
# --- Универсальная функция отказа по причине ---
async def ask_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, app_id: int, message_id: int = None):
    """Запрашивает у админа причину отказа заявки"""
    context.user_data['reject_app_id'] = app_id
    context.user_data['reject_message_id'] = message_id

    try:
        # Спрашиваем причину отказа
        if update.callback_query:
            await update.callback_query.message.reply_text(
                "Укажите причину отказа:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Отмена", callback_data=f"cancel_reject_{app_id}")]
                ])
            )
        else:
            await update.message.reply_text(
                "Укажите причину отказа:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Отмена", callback_data=f"cancel_reject_{app_id}")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка при запросе причины отказа: {e}")

async def save_user(user_id, username, first_name, last_name, role, nickname=None):
    try:
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, role, reg_date, nickname)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name, role, now, nickname))

        if nickname:
            cursor.execute("UPDATE users SET nickname=? WHERE user_id=?", (nickname, user_id))

        cursor.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка сохранения пользователя: {e}")
    finally:
        conn.close()

async def save_seller_application(user_id, data):
    try:
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO sellers
                        (user_id, platform, audience, theme, views, ad_type, screenshot_id, status, nickname, platform_usercode)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (user_id, data['platform'], data['audience'], data['theme'], 
                        data['views'], data['ad_type'], data.get('screenshot', ''), 'pending', data['nickname'], data['platform_usercode']))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Ошибка сохранения заявки продавца: {e}")
        return None
    finally:
        conn.close() if 'conn' in locals() else None

async def log_admin_action(admin_id, action, app_id):
    conn = None
    try:
        conn = sqlite3.connect(Config.DATABASE, timeout=10)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO admin_logs 
                        (admin_id, action, application_id, timestamp)
                        VALUES (?, ?, ?, ?)''',
                     (admin_id, action, app_id, datetime.now()))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка логирования действия админа: {e}")
        if "locked" in str(e):
            await asyncio.sleep(0.1)
            return await log_admin_action(admin_id, action, app_id)
    finally:
        if conn:
            conn.close()

async def get_sellers_by_platform(platform, descending=True):
    """Получение списка продавцов по платформе с сортировкой по аудитории"""
    try:
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()

        order = "DESC" if descending else "ASC"

        cursor.execute(f'''
            SELECT user_id, nickname, audience, views 
            FROM sellers 
            WHERE platform=? AND status='approved'
            ORDER BY 
                CAST(REPLACE(REPLACE(REPLACE(LOWER(audience), 'к', ''), 'k', ''), '+', '') AS INTEGER) {order}
        ''', (platform,))
        
        return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Ошибка получения продавцов: {e}")
        return []
    finally:
        conn.close()

async def send_new_message(query, context, text, reply_markup=None, photo=None, document=None):
    if photo:
        await context.bot.send_photo(
            chat_id=query.from_user.id,
            photo=photo,
            caption=text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    elif document:
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=document,
            caption=text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    else:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

async def clear_my_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет заявку текущего пользователя"""
    user_id = update.effective_user.id
    conn = None
    try:
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sellers WHERE user_id=?", (user_id,))
        conn.commit()
        await update.message.reply_text(
            "✅ Все ваши заявки удалены",
            reply_markup=get_default_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка удаления заявки: {e}")
        await update.message.reply_text("❌ Ошибка при удалении заявки")
    finally:
        if conn:
            conn.close()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Справка*\n\n"
        "Вы можете управлять диалогом с помощью следующих слов и команд:\n\n"
        "• /start — начать всё заново\n"
        "• /cancel — отменить текущий процесс\n"
        "• отмена, cancel, стоп — работают как команда отмены, если вы пишете их вручную\n"
        "• /profile — узнать свой статус\n"
        "• /help — открыть это сообщение\n\n"
        "Если вы застряли — просто напишите /start.",
        parse_mode="Markdown",
        reply_markup=get_default_keyboard()
    )

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔️ Только админ может блокировать.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Укажите username для блокировки, например: /block @username")
        return

    username = context.args[0].lstrip('@')
    user_id = await get_user_id_by_username(update, username)

    if user_id:
        banned_users.add(user_id)
        await update.message.reply_text(f"✅ Пользователь @{username} заблокирован.")
    else:
        await update.message.reply_text(f"❌ Не удалось найти пользователя @{username}.")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update):
        await update.message.reply_text("⛔️ Только админ может разблокировать.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Укажите username для разблокировки, например: /unblock @username")
        return

    username = context.args[0].lstrip('@')
    user_id = await get_user_id_by_username(update, username)

    if user_id:
        banned_users.discard(user_id)
        await update.message.reply_text(f"✅ Пользователь @{username} разблокирован.")
    else:
        await update.message.reply_text(f"❌ Не удалось найти пользователя @{username}.")

async def is_admin(update: Update) -> bool:
    chat_member = await update.effective_chat.get_member(update.effective_user.id)
    return chat_member.status in ['administrator', 'creator']

async def get_user_id_by_username(update: Update, username: str):
    try:
        members = await update.effective_chat.get_administrators()
        for member in members:
            if member.user.username and member.user.username.lower() == username.lower():
                return member.user.id

        # Попробуем получить из чата
        async for msg in update.effective_chat.get_history(limit=100):
            if msg.from_user.username and msg.from_user.username.lower() == username.lower():
                return msg.from_user.id
    except:
        return None

async def group_message_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in banned_users:
        return  # Бот игнорирует сообщения от заблокированных
    # Обработка сообщения дальше...

# --- Основные обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало взаимодействия с ботом."""
    try:
        user = update.effective_user
        await save_user(user.id, user.username, user.first_name, user.last_name, 'unassigned')
        
        links = generate_channel_links(Config.CHANNEL_USERNAME)
        
        text = (f"Здравствуйте, {user.first_name}! Перед использованием подпишитесь на наш канал:\n")
        
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Мобильная", url=links['mobile'])],
            [InlineKeyboardButton("🌐 Веб-версия", url=links['web'])],
            [InlineKeyboardButton("💻 Desktop", url=links['universal'])],
            [InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')]
        ])

        # Отправляем или редактируем сообщение
        if update.callback_query:
            await send_new_message(update.callback_query, context, text, markup)
            await context.bot.send_message(  # <--- Добавлено
                chat_id=update.effective_user.id,
                text="Вы можете начать заново в любой момент с помощью /start.",
                reply_markup=get_default_keyboard()
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=markup,
                parse_mode='Markdown'
            )
            await update.message.reply_text(  # <--- Добавлено
                "Нажмите /start, чтобы начать заново.",
                reply_markup=get_default_keyboard()
            )
        
        return CHECK_SUBSCRIPTION

    except Exception as e:
        logger.error(f"Ошибка в start: {e}", exc_info=True)
        
        # Пытаемся отправить сообщение об ошибке
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    "⚠️ Произошла ошибка. Попробуйте снова: /start",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Начать заново", callback_data='start')]
                    ])
                )
            elif update.message:
                await update.message.reply_text(
                    "⚠️ Произошла ошибка. Попробуйте снова: /start",
                    reply_markup=get_default_keyboard()
                )
            else:
                # Если вообще не можем отправить сообщение
                logger.error("Не удалось отправить сообщение об ошибке")
        except Exception as inner_e:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {inner_e}")
        
        return ConversationHandler.END

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверка подписки на канал"""
    query = update.callback_query
    await query.answer()
    
    try:
        user_id = query.from_user.id
        chat_member = await context.bot.get_chat_member(
            chat_id=Config.CHANNEL_ID,
            user_id=user_id
        )

        links = generate_channel_links(Config.CHANNEL_USERNAME)

        if chat_member.status in ['member', 'administrator', 'creator']:
            await query.message.reply_text("✅ Спасибо за подписку!\n\n"
                "❗Чтобы узнать какие команды можно использовать в боте напишите /help\n\n"
                "Кем вы хотите быть?", 
                reply_markup=InlineKeyboardMarkup(KEYBOARDS['role'])
            )
            return CHOOSE_ROLE
        else:
            # Если не подписан - возвращаем в начало
            # await start(update, context)
            await query.answer()
            await send_new_message(query, context, "Вы не подписаны на канал, пожалуйста, подпишитесь и нажмите на кнопку ещё раз.", InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 Мобильная", url=links['mobile'])],
                    [InlineKeyboardButton("🌐 Веб-версия", url=links['web'])],
                    [InlineKeyboardButton("💻 Desktop", url=links['universal'])],
                    [InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')]
                ])
            )
            return CHECK_SUBSCRIPTION
            
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        await send_new_message(query, context, "⚠️ Произошла ошибка. Попробуйте снова: /start")
        return ConversationHandler.END

async def save_buyer_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nickname = update.message.text.strip()
    user = update.effective_user

    try:
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET nickname = ? WHERE user_id = ?", (nickname, user.id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка при сохранении никнейма покупателя: {e}")
        await update.message.reply_text("❌ Не удалось сохранить никнейм.")
        return CHOOSE_BUYER_NICKNAME

    await update.message.reply_text(f"✅ Никнейм *{nickname}* сохранён. Теперь выберите платформу:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(KEYBOARDS['platform']))
    return BUYER_PLATFORM

async def buyer_nickname_keep(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    await query.message.reply_text("✅ Хорошо! Выберите платформу:",
        reply_markup=InlineKeyboardMarkup(KEYBOARDS['platform']))
    return BUYER_PLATFORM

async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    role = query.data
    user = query.from_user

    if role == "buyer":
        context.user_data["role"] = "buyer"
        try:
            conn = sqlite3.connect(Config.DATABASE)
            cursor = conn.cursor()
            cursor.execute("SELECT nickname FROM users WHERE user_id=?", (user.id,))
            result = cursor.fetchone()
            conn.close()

            if result and result[0]:  # Никнейм уже есть
                await query.message.reply_text(
                    f"👤 Ваш текущий никнейм: *{result[0]}*.\n\n"
                    "Если хотите его изменить, введите новый. Если всё устраивает — нажмите кнопку:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Оставить как есть", callback_data="keep_nickname")]
                    ])
                )
                return CHOOSE_BUYER_NICKNAME
            else:
                await query.message.reply_text("📝 Введите ваш никнейм, который будет отображаться продавцу:")
                return CHOOSE_BUYER_NICKNAME

        except Exception as e:
            logger.error(f"Ошибка при получении никнейма: {e}")
            await query.message.reply_text("⚠️ Ошибка при обращении к базе. Попробуйте снова.")
            return ConversationHandler.END

    elif role == "seller":
        await query.message.reply_text("🖥 Выберите платформу:", reply_markup=InlineKeyboardMarkup(KEYBOARDS['platform']))
        return SELLER_PLATFORM

@cancel_if_requested
async def seller_platform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора платформы продавцом."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'back_to_roles':
        await send_new_message(query, context, "Кем вы хотите быть?", InlineKeyboardMarkup(KEYBOARDS['role']))
        return CHOOSE_ROLE
    
    platform = query.data
    if 'application_data' not in context.user_data:
        context.user_data['application_data'] = {}
        context.user_data['application_data']['platform'] = platform
    
    await send_new_message(query, context, f"Введите ваш никнейм (он будет отражаться в списке продавцов)")
    return SELLER_NICKNAME

@cancel_if_requested
async def seller_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение никнейма продавца"""
    nickname = update.message.text.strip()
    context.user_data['application_data']['nickname'] = nickname

    await update.message.reply_text(f"Укажите юз-код вашего аккаунта на платформе (например, @channel или ссылка):")
    return SELLER_USERCODE

@cancel_if_requested
async def seller_usercode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    usercode = update.message.text.strip()
    context.user_data['application_data']['platform_usercode'] = usercode

    if not usercode:
        await update.message.reply_text("Пожалуйста, введите юз-код - это важно для покупателя.")
        return SELLER_USERCODE

    await update.message.reply_text("Укажите аудиторию вашего аккаунта в формате 'XК' или 'XK' (например: 10К, 50К, 100К+):")
    return SELLER_AUDIENCE

@cancel_if_requested
async def seller_audience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода аудитории продавцом."""
    text = update.message.text.strip().lower()

    if not (text.endswith('к') or text.endswith('k')):
        await update.message.reply_text("Пожалуйста, укажите аудиторию в формате 'XК'  или 'XK' (например: 10К, 50К, 100К+):")
        return SELLER_AUDIENCE
    
    context.user_data['application_data']['audience'] = update.message.text
    await update.message.reply_text("Опишите тематику вашего контента:")
    return SELLER_THEME

@cancel_if_requested
async def seller_theme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода тематики контента."""
    if len(update.message.text) < 10:
        await update.message.reply_text("Пожалуйста, опишите тематику более подробно (минимум 10 символов)")
        return SELLER_THEME
    
    context.user_data['application_data']['theme'] = update.message.text
    await update.message.reply_text("Укажите средние просмотры ваших видео/рилсов в формате 'XК' или 'XK' (например: 30К, 36К):")
    return SELLER_VIEWS

@cancel_if_requested
async def seller_views(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода средних просмотров."""
    text = update.message.text.strip().lower()

    if not (text.endswith('к') or text.endswith('k')):
        await update.message.reply_text("Пожалуйста, укажите средние просмотры в формате 'XК'  или 'XK' (например: 30К, 36К)")
        return SELLER_VIEWS

    context.user_data['application_data']['views'] = update.message.text
    await update.message.reply_text(
        "Какую рекламу вы предлагаете?",
        reply_markup=InlineKeyboardMarkup(KEYBOARDS['ad_type']))
    return SELLER_AD_TYPE

@cancel_if_requested
async def seller_ad_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора типа рекламы."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'back_to_views':
        await send_new_message(query, context, "Укажите средние просмотры ваших видео/рилсов (в 'К', например: 30К, 36К):")
        return SELLER_VIEWS

    if query.data == 'custom_ad':
        await send_new_message(query, context, "Напишите текстом, какую рекламу вы будете предлагать:")
        return SELLER_CUSTOM_AD_TYPE
    else:
        context.user_data['application_data']['ad_type'] = query.data
        await send_new_message(query, context, "Скиньте скриншот, подтверждающий, что вы владелец аккаунта.")
        return SELLER_SCREENSHOT

@cancel_if_requested
async def seller_custom_ad_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text

    context.user_data['application_data']['ad_type'] = text
    await update.message.reply_text("Скиньте скриншот, подтверждающий, что вы владелец аккаунта.")
    return SELLER_SCREENSHOT

@cancel_if_requested
async def seller_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка скриншота и подтверждение заявки."""
    if update.message.photo:
        context.user_data['application_data']['screenshot'] = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type.startswith('image/'):
        context.user_data['application_data']['screenshot'] = update.message.document.file_id
    else:
        await update.message.reply_text("Пожалуйста, отправьте изображение.", reply_markup=get_default_keyboard())
        return SELLER_SCREENSHOT
    
    data = context.user_data['application_data']
    text = (
        "Проверьте ваши данные:\n\n"
        f"Платформа: {data['platform']}\n"
        f"Аудитория: {data['audience']}\n"
        f"Тематика: {data['theme']}\n"
        f"Просмотры: {data['views']}\n"
        f"Тип рекламы: {data['ad_type']}"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(KEYBOARDS['confirm']))
    return SELLER_CONFIRM

async def seller_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтверждение заявки и отправка админам на модерацию"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'confirm_application':
        user = query.from_user
        data = context.user_data['application_data']
        
        app_id = await save_seller_application(user.id, data)
        
        if app_id:
            # Формируем текст заявки для админов (как при подтверждении у пользователя)
            application_text = (
                "📄 *Новая заявка на продавца* #" + str(app_id) + "\n\n"
                f"👤 *Пользователь:* @{user.username} ([{user.first_name}](tg://user?id={user.id}))\n"
                f"👤 *Юз-код аккаунта:* {data['platform_usercode']}\n"
                f"🖥 *Платформа:* {data['platform']}\n"
                f"👥 *Аудитория:* {data['audience']}\n"
                f"📌 *Тематика:* {data['theme']}\n"
                f"👀 *Просмотры:* {data['views']}\n"
                f"📢 *Тип рекламы:* {data['ad_type']}\n\n"
                "*Скриншот подтверждения:*"
            )
            
            # Клавиатура для админов
            admin_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{app_id}")],
                [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app_id}")]
            ])
            
            # Отправляем админам заявку
            for admin_id in Config.ADMIN_IDS:
                try:
                    # Сначала отправляем текст заявки
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=application_text,
                        parse_mode='Markdown'
                    )
                    # Затем отправляем скриншот с кнопками
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=data['screenshot'],
                        reply_markup=admin_keyboard
                    )
                except Exception as e:
                    logger.error(f"Ошибка уведомления админа {admin_id}: {e}")
            
            # Сообщение пользователю
            await send_new_message(query, context, "✅ Ваша заявка отправлена на модерацию. Мы уведомим вас о решении.")
        else:
            await send_new_message(query, context, "❌ Произошла ошибка при сохранении заявки. Попробуйте позже.", InlineKeyboardMarkup([
                    [InlineKeyboardButton("Попробовать снова", callback_data='start')]
                ])
            )
        
        return ConversationHandler.END
    else:
        # Если пользователь выбрал "Изменить"
        await send_new_message(query, context, "Выберите платформу:", InlineKeyboardMarkup(KEYBOARDS['platform']))
        return SELLER_PLATFORM

async def reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        print("❌ reject_reason: НЕТ update.message")
        return ConversationHandler.END

    print("✅ reject_reason СРАБОТАЛ")

    text = update.message.text
    print(f"Пойман текст отказа: {text}")

    reason = text
    app_id = context.user_data.get('reject_app_id')

    if not app_id:
        await update.message.reply_text("❌ Ошибка: заявка не найдена.")
        return ConversationHandler.END

    try:
        # Обновляем статус заявки в БД
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sellers SET status='rejected', reject_reason=? WHERE seller_id=?",
            (reason, app_id)
        )
        cursor.execute("SELECT user_id FROM sellers WHERE seller_id=?", (app_id,))
        result = cursor.fetchone()
        conn.commit()
    except Exception as e:
        print(f"Ошибка обновления базы: {e}")
        await update.message.reply_text(
                "❌ Произошла ошибка при обновлении заявки.",
                reply_markup=get_default_keyboard()
            )
        return ConversationHandler.END
    finally:
        conn.close()

    if not result:
        await update.message.reply_text("❌ Не удалось найти пользователя заявки.")
        return ConversationHandler.END

    user_id = result[0]

    # Отправляем пользователю сообщение об отказе
    await context.bot.send_message(
        chat_id=user_id,
        text=f"❌ Ваша заявка отклонена по причине:\n\n{reason}\n\nВы можете подать новую заявку через /start."
    )

    # Уведомляем админа об успешной обработке
    await update.message.reply_text(f"✅ Заявка #{app_id} отклонена. Пользователь уведомлён.")

    return ConversationHandler.END

async def cancel_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, _, app_id = query.data.split('_')
    try:
        await send_new_message(query, context, f"Отклонение заявки #{app_id} отменено", InlineKeyboardMarkup([
                [InlineKeyboardButton("Админ-панель", callback_data='admin_panel')]
            ])
        )
    except:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=f"Отклонение заявки #{app_id} отменено",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Админ-панель", callback_data='admin_panel')]
            ])
        )
    return ConversationHandler.END

async def buyer_platform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    # print("назад сработал!")
    if query.data == 'back_to_roles':
        await send_new_message(query, context, "Кем вы хотите быть?", InlineKeyboardMarkup(KEYBOARDS['role']))
        return CHOOSE_ROLE

    platform = query.data
    context.user_data['selected_platform'] = platform
    # Устанавливаем сортировку по умолчанию
    context.user_data['sort_descending'] = True

    return await show_sorted_sellers(update, context)

async def show_sorted_sellers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    platform = context.user_data.get('selected_platform')
    descending = context.user_data.get('sort_descending', True)

    sellers = await get_sellers_by_platform(platform, descending)

    query = update.callback_query
    await query.answer()

    platform = context.user_data.get('selected_platform')
    descending = context.user_data.get('sort_descending')

    sellers = await get_sellers_by_platform(platform, descending)

    if not sellers:
        await send_new_message(query, context, "На данный момент нет продавцов для выбранной платформы.", InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀️ Назад", callback_data='back_to_roles')]])
        )
        return BUYER_PLATFORM

    # Формируем список
    seller_list = "\n".join(
        f"{idx+1}. {seller[1]} | Аудитория: {seller[2]} | Просмотры: {seller[3]}"
        for idx, seller in enumerate(sellers)
    )
    context.user_data['sellers'] = sellers

    sort_button = InlineKeyboardButton(
        "🔽 Убывание" if descending else "🔼 Возрастание",
        callback_data="toggle_sort"
    )

    await send_new_message(query, context, f"🔍 Продавцы на {platform}:\n\n{seller_list}\n\nВыберите номер продавца:", InlineKeyboardMarkup([
            [sort_button],
            [InlineKeyboardButton("◀️ Назад", callback_data='back_to_roles')]
        ])
    )

    return SHOW_SELLER_PROFILE

async def toggle_sort(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # Безопасное переключение
    context.user_data['sort_descending'] = not context.user_data.get('sort_descending', True)

    print("Sort bit:", context.user_data['sort_descending'])  # Отладка

    # Повторный показ отсортированного списка
    return await show_sorted_sellers(update, context)

async def show_seller_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = int(update.message.text.strip()) - 1
    sellers = context.user_data.get('sellers', [])

    if idx < 0 or idx >= len(sellers):
        await update.message.reply_text("❌ Неверный номер продавца.")
        return BUYER_CHOOSE_SELLER

    seller = sellers[idx]
    context.user_data['selected_seller'] = seller

    # Получаем данные продавца
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    cursor.execute('''SELECT nickname, platform_usercode, audience, views, ad_type, deals, rating
                      FROM sellers WHERE user_id=? ORDER BY seller_id DESC LIMIT 1''', (seller[0],))
    row = cursor.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("❌ Профиль продавца не найден.")
        return BUYER_PLATFORM

    nickname, usercode, audience, views, ad_type, deals, rating = row

    profile_text = (
        f"👤 *{nickname}*\n"
        f"📎 Юз-код: {usercode}\n"
        f"👥 Аудитория: {audience}\n"
        f"👁 Просмотры: {views}\n"
        f"📢 Реклама: {ad_type}\n"
        f"🤝 Сделок: {deals or 0}\n"
        f"⭐️ Оценка: {rating or 'неизвестно'}"
    )

    seller_user_id = seller[0]

    await update.message.reply_text(profile_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Написать", callback_data="start_dialog")],
        [InlineKeyboardButton("◀️ Другие продавцы", callback_data="back_to_platforms")],
        [InlineKeyboardButton("📝 Комментарии", callback_data=f"view_comments_{seller_user_id}")]
    ]))
    return ConversationHandler.END

@cancel_if_requested
async def start_dialog_from_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    seller = context.user_data.get('selected_seller')
    if not seller:
        await query.message.reply_text("❌ Продавец не найден.")
        return ConversationHandler.END

    await query.message.reply_text("✏️ Напишите сообщение продавцу. Оно будет передано ему в бот.")
    return BUYER_MESSAGE

@cancel_if_requested
async def back_to_sellers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    sellers = context.user_data.get('sellers', [])
    platform = context.user_data.get('platform', 'неизвестно')

    if not sellers:
        await query.message.reply_text("❌ Список продавцов недоступен.")
        return ConversationHandler.END

    seller_list = "\n".join(
        f"{idx+1}. {seller[1]} | Аудитория: {seller[2]} | Просмотры: {seller[3]}"
        for idx, seller in enumerate(sellers)
    )

    await query.message.reply_text(
        f"🔍 Продавцы на {platform}:\n\n{seller_list}\n\n"
        "Введите номер продавца, чтобы посмотреть его профиль:"
    )
    return BUYER_CHOOSE_SELLER

@cancel_if_requested
async def buyer_choose_seller(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора продавца покупателем."""
    try:
        seller_num = int(update.message.text) - 1
        sellers = context.user_data['sellers']
        
        if seller_num < 0 or seller_num >= len(sellers):
            raise ValueError
            
        selected_seller = sellers[seller_num]
        context.user_data['selected_seller'] = selected_seller

        await update.message.reply_text(
            f"Вы выбрали продавца: {selected_seller[1]}\n"
            "Напишите ваше сообщение для продавца:")
        return BUYER_MESSAGE
    except ValueError:
        await update.message.reply_text(
                "Неверный номер продавца. Пожалуйста, введите корректный номер из списка.",
                reply_markup=get_default_keyboard()    
            )
        return BUYER_CHOOSE_SELLER

# @cancel_if_requested
# async def buyer_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     """Обработка сообщения покупателя для продавца."""
#     message = update.message.text
#     user = update.message.from_user
#     seller = context.user_data['selected_seller']
#     receiver_id = seller[0]
#     sender_id = user.id
#     text = message
#     buyer_id = update.effective_user.id

#     active_chats[update.effective_user.id] = seller[0]
#     active_chats[seller[0]] = update.effective_user.id

#     sender_user = await context.bot.get_chat(sender_id)
#     receiver_user = await context.bot.get_chat(receiver_id)

#     conn = sqlite3.connect(Config.DATABASE)
#     cursor = conn.cursor()
#     # Получаем nickname покупателя из users
#     cursor.execute("SELECT nickname FROM users WHERE user_id=?", (buyer_id,))
#     row = cursor.fetchone()
#     buyer_nickname = row[0] if row and row[0] else f"id:{buyer_id}"
#     conn.close()

#     await context.bot.send_message(
#         chat_id=seller[0],
#         text=f"💬 Вы общаетесь с покупателем: {buyer_nickname}"
#     )

#     if not buyer_id:
#         await update.message.reply_text("❌ Ошибка: покупатель не найден.")
#         return ConversationHandler.END

#     # Получаем nickname продавца из БД
#     try:
#         conn = sqlite3.connect(Config.DATABASE)
#         cursor = conn.cursor()
#         cursor.execute("SELECT nickname FROM sellers WHERE user_id=? ORDER BY seller_id DESC LIMIT 1", (seller[0],))
#         row = cursor.fetchone()
#         seller_nickname = row[0] if row and row[0] else f"id:{seller[0]}"
#         conn.close()
#     except Exception as e:
#         logger.error(f"Ошибка при получении nickname продавца: {e}")
#         seller_nickname = f"@{seller[1]}"

#     await context.bot.send_message(
#         chat_id=user.id,
#         text="Вы можете завешить диалог в любой момент.",
#         reply_markup=dialog_keyboard
#     )

#     await context.bot.send_message(
#         chat_id=seller[0],
#         text="Вы можете завешить диалог в любой момент.",
#         reply_markup=dialog_keyboard
#     )

#     logger.info(f"➡️ отправка кнопки 'Ответить' продавцу: reply_to_{user.id}")

#     # Теперь диалог будет происходить в боте
#     await context.bot.send_message(
#         chat_id=seller[0],  # ID продавца
#         text=f"📨 Новое сообщение от @{buyer_nickname}:\n\n{message}\n\n"
#              f"Ответить можно прямо здесь",
#         reply_markup=InlineKeyboardMarkup([
#             [InlineKeyboardButton("Ответить", callback_data=f"reply_to_{user.id}")]
#         ])
#     )

#     # получаем User-объекты
#     sender_user   = await context.bot.get_chat(sender_id)
#     receiver_user = await context.bot.get_chat(receiver_id)

#     # форматируем
#     sender_name   = f"@{sender_user.username}" if sender_user.username else sender_user.full_name
#     receiver_name = f"@{receiver_user.username}" if receiver_user.username else receiver_user.full_name

#     # Отправляем админу
#     await context.bot.send_message(
#         chat_id=Config.ADMIN_CHAT_ID,
#         text=(
#             f"🟠 [Диалог] Покупатель ➡️ Продавцу\n"
#             f"От {sender_name} ➡️ {receiver_name}:\n\n{text}"
#         )    
#     )

#     await update.message.reply_text("✅ Ваше сообщение отправлено продавцу. Можете продолжать переписку.")
    
#     return DIALOG

# @cancel_if_requested
# async def seller_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     query = update.callback_query
#     await query.answer()

#     try:
#         buyer_id = int(query.data.split('_')[2])
#         seller_id = query.from_user.id

#         active_chats[seller_id] = buyer_id
#         active_chats[buyer_id] = seller_id

#         context.user_data['reply_to'] = buyer_id

#         logger.info(f"📥 нажата кнопка 'Ответить': data = {query.data}, от = {query.from_user.id}")
#         logger.info(f"💬 seller_reply_start: reply_to set to {buyer_id} for user {query.from_user.id}")

#         await query.message.reply_text("✏️ Напишите сообщение для покупателя:")
#         return REPLY_TO_BUYER

#     except Exception as e:
#         logger.error(f"❌ Ошибка в seller_reply_start: {e}")
#         await query.message.reply_text("❌ Не удалось начать ответ. Попробуйте позже.")
#         return ConversationHandler.END

# @cancel_if_requested
# async def seller_send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     logger.info("👌 seller_send_reply вызван")

#     seller = update.effective_user
#     sender_id = seller.id
#     buyer_id = context.user_data.get('reply_to')
#     text = update.message.text.strip()

#     logger.info(f"seller_send_reply called by user {sender_id}, reply_to = {buyer_id}")

#     logger.info(f"✅ seller_send_reply вызван от {update.effective_user.id}")
#     reply_to_user_id = context.user_data.get("reply_to")
#     logger.info(f"📤 reply_to_user_id = {reply_to_user_id}")

#     if not buyer_id:
#         await update.message.reply_text("❌ Ошибка: не найден получатель ответа.")
#         return ConversationHandler.END

#     # Получаем nickname покупателя
#     try:
#         conn = sqlite3.connect(Config.DATABASE)
#         cursor = conn.cursor()
#         cursor.execute("SELECT nickname FROM users WHERE user_id=?", (buyer_id,))
#         row = cursor.fetchone()
#         buyer_nickname = row[0] if row and row[0] else f"id:{buyer_id}"
#         conn.close()
#     except Exception as e:
#         logger.error(f"Ошибка при получении nickname покупателя: {e}")
#         buyer_nickname = f"id:{buyer_id}"

#     try:
#         sender_user = await context.bot.get_chat(sender_id)
#         receiver_user = await context.bot.get_chat(buyer_id)

#         sender_name = f"@{sender_user.username}" if sender_user.username else sender_user.full_name
#         receiver_name = f"@{receiver_user.username}" if receiver_user.username else receiver_user.full_name

#         logger.info(f"seller {update.effective_user.id} is replying to buyer {buyer_id}")

#         await context.bot.send_message(
#             chat_id=buyer_id,
#             text=f"💬 Ответ от продавца {sender_name}:\n\n{text}",
#             reply_markup=dialog_keyboard
#         )

#         await context.bot.send_message(
#             chat_id=Config.ADMIN_CHAT_ID,
#             text=(
#                 f"🟠 [Диалог] Продавец ➡️ Покупателю\n"
#                 f"От {sender_name} ➡️ {receiver_name}:\n\n{text}"
#             )
#         )

#         await update.message.reply_text("✅ Сообщение успешно отправлено.")
#         logger.info("✅ Сообщение успешно отправлено")

#     except Exception as e:
#         logger.error(f"❌ Ошибка при отправке: {e}, buyer_id={buyer_id}, text={text}")
#         await update.message.reply_text("❌ Не удалось отправить сообщение. Попробуйте позже.")
#         return ConversationHandler.END

#     return DIALOG

#________________________________________________________________________________ 

async def get_user_role(user_id: int) -> str:
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM sellers WHERE user_id=?", (user_id,))
    if cursor.fetchone():
        conn.close()
        return "seller"

    cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone():
        conn.close()
        return "buyer"

    conn.close()
    return "unknown"

async def get_seller_nickname(user_id: int) -> str:
    try:
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT nickname FROM sellers WHERE user_id = ? ORDER BY seller_id DESC LIMIT 1", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] else f"id:{user_id}"
    except Exception as e:
        logger.error(f"Ошибка при получении никнейма продавца: {e}")
        return f"id:{user_id}"

async def get_buyer_nickname(user_id: int) -> str:
    try:
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT nickname FROM users WHERE user_id = ? LIMIT 1", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] else f"id:{user_id}"
    except Exception as e:
        logger.error(f"Ошибка при получении никнейма покупателя: {e}")
        return f"id:{user_id}"

@cancel_if_requested
async def buyer_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка сообщения от покупателя продавцу."""
    message = update.message.text
    sender_id = update.effective_user.id
    receiver_id = context.user_data.get('selected_seller')
    if isinstance(receiver_id, tuple):
        receiver_id = receiver_id[0]

    if not receiver_id:
        await update.message.reply_text("❌ Продавец не выбран.")
        return ConversationHandler.END

    # 🔄 Сохраняем диалог
    active_chats[sender_id] = receiver_id
    active_chats[receiver_id] = sender_id

    # 🧠 Определяем, кто продавец, а кто покупатель
    sender_role = await get_user_role(sender_id)
    receiver_role = await get_user_role(receiver_id)

    if sender_role == "seller":
        seller_id = sender_id
        buyer_id = receiver_id
    else:
        seller_id = receiver_id
        buyer_id = sender_id

    context.user_data["selected_seller"] = seller_id
    context.user_data["reply_to"] = buyer_id

    # 🔎 Получаем nickname покупателя
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT nickname FROM users WHERE user_id=?", (buyer_id,))
    row = cursor.fetchone()
    buyer_nickname = row[0] if row and row[0] else f"id:{buyer_id}"
    conn.close()

    # 📨 Продавцу уведомление
    await context.bot.send_message(
        chat_id=seller_id,
        text=f"📨 Новое сообщение от покупателя {buyer_nickname}:\n\n{message}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Ответить", callback_data=f"reply_to_{buyer_id}")]
        ])
    )

    # Покупателю — подтверждение
    await update.message.reply_text("✅ Ваше сообщение отправлено продавцу. Можете продолжать переписку.")

    # Админу
    sender_user = await context.bot.get_chat(sender_id)
    receiver_user = await context.bot.get_chat(receiver_id)
    sender_name = f"@{sender_user.username}" if sender_user.username else sender_user.full_name
    receiver_name = f"@{receiver_user.username}" if receiver_user.username else receiver_user.full_name

    await context.bot.send_message(
        chat_id=Config.ADMIN_CHAT_ID,
        text=f"🟠 [Диалог] {sender_name} ➡️ {receiver_name}:\n\n{message}"
    )

    return DIALOG

@cancel_if_requested
async def seller_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    try:
        buyer_id = int(query.data.split('_')[2])
        context.user_data['reply_to'] = buyer_id

        logger.info(f"📥 Нажата кнопка 'Ответить': data = {query.data}, от = {query.from_user.id}")
        logger.info(f"💬 reply_to установлен как {buyer_id} для пользователя {query.from_user.id}")

        await query.message.reply_text("✏️ Напишите сообщение для покупателя:")
        return SELLER_REPLY

    except Exception as e:
        logger.error(f"❌ Ошибка в seller_reply_start: {e}")
        await query.message.reply_text("❌ Не удалось начать ответ. Попробуйте позже.")
        return ConversationHandler.END

@cancel_if_requested
async def seller_send_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    seller_id = update.effective_user.id
    buyer_id = context.user_data.get('reply_to')
    text = update.message.text.strip()

    logger.info(f"✉️ seller_send_reply вызван от {seller_id}, получатель = {buyer_id}")

    if not buyer_id:
        await update.message.reply_text("❌ Ошибка: получатель не найден.")
        return ConversationHandler.END

    # Получаем никнеймы
    seller_name = await get_seller_nickname(seller_id)
    buyer_name = await get_buyer_nickname(buyer_id)

    sender_user = await context.bot.get_chat(seller_id)
    receiver_user = await context.bot.get_chat(buyer_id)
    sender_display = f"@{sender_user.username}" if sender_user.username else sender_user.full_name
    receiver_display = f"@{receiver_user.username}" if receiver_user.username else receiver_user.full_name

    try:
        # Отправка покупателю
        await context.bot.send_message(
            chat_id=buyer_id,
            text=f"💬 Ответ от продавца {seller_name}:\n\n{text}",
            reply_markup=dialog_keyboard
        )

        # Лог админу
        await context.bot.send_message(
            chat_id=Config.ADMIN_CHAT_ID,
            text=f"🟠 [Диалог] Продавец ➡️ Покупателю\nОт {sender_display} ➡️ {receiver_display}:\n\n{text}"
        )

        await update.message.reply_text("✅ Сообщение успешно отправлено.")
        return DIALOG

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке ответа: {e}")
        await update.message.reply_text("❌ Не удалось отправить сообщение.")
        return ConversationHandler.END

@cancel_if_requested
async def dialog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sender_id = update.effective_user.id
    receiver_id = active_chats.get(sender_id)
    text = update.message.text.strip()

    if not receiver_id:
        await update.message.reply_text("❌ Диалог завершён или собеседник недоступен.")
        return ConversationHandler.END

    # 🧠 Определяем роль отправителя
    role = await get_user_role(sender_id)

    if role == "seller":
        nickname = await get_seller_nickname(sender_id)
    elif role == "buyer":
        nickname = await get_buyer_nickname(sender_id)
    else:
        nickname = f"id:{sender_id}"

    # Получаем имена
    sender_user = await context.bot.get_chat(sender_id)
    receiver_user = await context.bot.get_chat(receiver_id)
    sender_name = f"@{sender_user.username}" if sender_user.username else sender_user.full_name
    receiver_name = f"@{receiver_user.username}" if receiver_user.username else receiver_user.full_name

    # Отправляем сообщение собеседнику
    await context.bot.send_message(
        chat_id=receiver_id,
        text=f"💬 Новое сообщение от {nickname}:\n\n{text}",
        reply_markup=dialog_keyboard
    )

    # Лог администратору
    await context.bot.send_message(
        chat_id=Config.ADMIN_CHAT_ID,
        text=(
            f"🟠 [Диалог]\n"
            f"От {sender_name} ➡️ {receiver_name}:\n\n{text}"
        )
    )

    # ✅ Если текст — кнопка сделки
    if text.lower() == "💰 начать оплату":
        payment_type = "direct"
    elif text.lower() == "💼 эксроу-счет":
        payment_type = "escrow"
    else:
        return DIALOG

    # 💳 Создание сделки
    deal_id = await create_new_deal(sender_id, receiver_id, payment_type)
    context.user_data["active_deal_id"] = deal_id

    # Определение кто продавец/покупатель
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sellers WHERE user_id = ?", (sender_id,))
    is_sender_seller = cursor.fetchone()
    conn.close()

    seller_id = sender_id if is_sender_seller else receiver_id
    buyer_id = receiver_id if is_sender_seller else sender_id

    # Сообщение второму участнику
    await context.bot.send_message(
        chat_id=receiver_id,
        text=f"{'Покупатель' if sender_id == buyer_id else 'Продавец'} хочет начать сделку #{deal_id} через {payment_type.upper()}.\n\nПодтвердите?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_deal_{deal_id}")],
            [InlineKeyboardButton("❌ Отказаться", callback_data=f"cancel_deal_{deal_id}")]
        ])
    )

    return DIALOG

#________________________________________________________________________________

# @cancel_if_requested
# async def dialog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     logger.info(f"🟢 dialog_handler сработал для {update.effective_user.id} | text = {update.message.text}")
    
#     sender_id = update.effective_user.id
#     receiver_id = active_chats.get(sender_id)
#     text = update.message.text.strip().lower()

#     if not receiver_id:
#         await update.message.reply_text("❌ Диалог завершён или собеседник недоступен.")
#         return ConversationHandler.END

#     # # Определяем продавца и покупателя
#     # seller_id, buyer_id = get_seller_and_buyer_ids(sender_id, receiver_id)
    
#     seller = context.user_data.get('selected_seller')
#     if not seller:
#         await update.message.reply_text("Продавец не найден")
#         return ConversationHandler.END

#     if not context.user_data.get('deal_intro_sent'):
#         await send_deal_intro(seller[0], context)
#         await send_deal_intro(update.effective_user.id, context)
#         context.user_data['deal_intro_sent'] = True

#     # получаем User-объекты
#     sender_user   = await context.bot.get_chat(sender_id)
#     receiver_user = await context.bot.get_chat(receiver_id)

#     # форматируем
#     sender_name   = f"@{sender_user.username}" if sender_user.username else sender_user.full_name
#     receiver_name = f"@{receiver_user.username}" if receiver_user.username else receiver_user.full_name

#     # Никнейм продавца
#     nickname = await get_seller_nickname(sender_id)

#     # Показываем сообщение собеседнику
#     await context.bot.send_message(
#         chat_id=receiver_id,
#         text=f"💬 Новое сообщение от {nickname}:\n\n{text}",
#         reply_markup=dialog_keyboard
#     )

#     # Отправляем админу
#     await context.bot.send_message(
#         chat_id=Config.ADMIN_CHAT_ID,
#         text=(
#             f"🟠 [Диалог]\n"
#             f"От {sender_name} ➡️ {receiver_name}:\n\n{text}"
#         )    
#     )

#     # Проверка кнопок
#     if text.strip().lower() == "💰 начать оплату":
#         payment_type = "direct"
#     elif text.strip().lower() == "💼 эксроу-счет":
#         payment_type = "escrow"
#     else:
#         return DIALOG  # обычное сообщение

#     # Создание сделки
#     deal_id = await create_new_deal(sender_id, receiver_id, payment_type)
#     context.user_data["active_deal_id"] = deal_id

#     conn = sqlite3.connect(Config.DATABASE)
#     cursor = conn.cursor()
#     cursor.execute("SELECT 1 FROM sellers WHERE user_id = ?", (sender_id,))
#     is_sender_seller = cursor.fetchone()
#     conn.close()

#     if is_sender_seller:
#         seller_id = sender_id
#         buyer_id = receiver_id
#     else:
#         seller_id = receiver_id
#         buyer_id = sender_id

#     # Уведомление второго участника
#     await context.bot.send_message(
#         chat_id=receiver_id,
#         text=f"{'Покупатель' if sender_id == buyer_id else 'Продавец'} хочет начать сделку #{deal_id} через {payment_type.upper()}.\n\nПодтвердите?",
#         reply_markup=InlineKeyboardMarkup([
#             [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_deal_{deal_id}")],
#             [InlineKeyboardButton("❌ Отказаться", callback_data=f"cancel_deal_{deal_id}")]
#         ])
#     )

#     return DIALOG

async def confirm_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    print("🔔 confirm_deal triggered")

    deal_id = int(query.data.split("_")[-1])
    
    # Тут обновление статуса сделки в БД
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    cursor.execute("UPDATE deals SET status = 'confirmed' WHERE deal_id = ?", (deal_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text(f"✅ Сделка #{deal_id} подтверждена.")

async def cancel_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    print("🔔 cancel_deal triggered")

    deal_id = int(query.data.split("_")[-1])
    
    # Обновляем статус сделки
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    cursor.execute("UPDATE deals SET status = 'cancelled' WHERE deal_id = ?", (deal_id,))
    conn.commit()
    conn.close()

    await query.edit_message_text(f"❌ Сделка #{deal_id} была отменена.")

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    companion = active_chats.pop(uid, None)

    if companion:
        active_chats.pop(companion, None)
        await context.bot.send_message(companion, "🔕 Собеседник завершил диалог.", reply_markup=get_default_keyboard())

    await update.message.reply_text(
        "✅ Диалог завершён.",
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

async def send_deal_intro(receiver_id: int, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📦 *Это начало сделки.*\n\n"
        "💬 На данном этапе вы можете обсудить условия сделки.\n\n"
        "💰 Когда будете готовы, кликните по одной из кнопок:\n"
        "• Начать оплату — оплата напрямую между участниками.\n"
        "• Эксроу-счет — деньги временно удерживаются ботом.\n\n"
        "❗️ Внимание:\n"
        "Начать оплату — бот не несёт ответственности за честность продавца. Оплачивайте только проверенным продавцам.\n"
        "Эксроу-счет — безопасный способ. Деньги передаются продавцу только после вашего подтверждения.\n\n"
        "🔘 Вы также можете:\n"
        "• Нажать кнопку *«❌ Завершить диалог»* для выхода\n"
        "• Нажать *«Написать другим продавцам»* для выбора нового\n"
        "• Нажать *«Жалоба на продавца»* при необходимости"
    )

    await context.bot.send_message(
        chat_id=receiver_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton("❌ Завершить диалог")],
                [KeyboardButton("Написать другим продавцам")],
                [KeyboardButton("Жалоба на продавца")]
            ],
            resize_keyboard=True
        )
    )

async def create_new_deal(buyer_id, seller_id, payment_type):
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO deals (buyer_id, seller_id, status, payment_type) VALUES (?, ?, 'negotiation', ?)",
        (buyer_id, seller_id, payment_type)
    )
    conn.commit()
    deal_id = cursor.lastrowid
    conn.close()
    return deal_id

async def finish_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deal_id = context.user_data.get('active_deal_id')
    if not deal_id:
        await update.message.reply_text("❌ Нет активной сделки.")
        return ConversationHandler.END

    # Спрашиваем оценку
    await update.message.reply_text("Поставьте оценку продавцу от 1 до 5:")
    context.user_data['awaiting_rating'] = deal_id
    return WAITING_FOR_RATING

async def receive_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rating = int(update.message.text.strip())
    deal_id = context.user_data.pop('awaiting_rating')
    context.user_data['awaiting_comment'] = (deal_id, rating)

    await update.message.reply_text("Можете оставить комментарий к сделке:")
    return WAITING_FOR_COMMENT

async def view_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller_id = int(update.callback_query.data.split('_')[2])
    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT comment, rating FROM deals WHERE seller_id=? AND comment IS NOT NULL", (seller_id,))
    reviews = cursor.fetchall()
    conn.close()

    if not reviews:
        await update.callback_query.message.reply_text("🔹 Пока нет комментариев.")
    else:
        text = "\n\n".join([f"⭐️ {r[1]}: {r[0]}" for r in reviews])
        await update.callback_query.message.reply_text(f"💬 Комментарии о продавце:\n\n{text}")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора для модерации заявок."""
    if update.effective_user.id not in Config.ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен")
        return
    
    try:
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()
        cursor.execute('''SELECT s.seller_id, u.username, s.platform, s.audience, 
                         s.theme, s.views, s.ad_type, s.status 
                         FROM sellers s JOIN users u ON s.user_id = u.user_id 
                         WHERE s.status='pending' ''')
        applications = cursor.fetchall()
        
        if not applications:
            await update.message.reply_text("ℹ️ Нет заявок на модерацию")
            return
        
        for app in applications:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{app[0]}")],
                [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{app[0]}")]
            ])
            
            await update.message.reply_text(
                f"📄 Заявка #{app[0]}\n"
                f"👤 Пользователь: @{app[1]}\n"
                f"🖥 Платформа: {app[2]}\n"
                f"👥 Аудитория: {app[3]}\n"
                f"📌 Тематика: {app[4]}\n"
                f"👀 Просмотры: {app[5]}\n"
                f"📢 Тип рекламы: {app[6]}\n"
                f"🔄 Статус: {app[7]}",
                reply_markup=keyboard
            )
    except sqlite3.Error as e:
        logger.error(f"Ошибка получения заявок: {e}")
        await update.message.reply_text("❌ Произошла ошибка при получении заявок")
    finally:
        conn.close() if 'conn' in locals() else None

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in Config.ADMIN_IDS:
        return

    # try:
    parts = query.data.split('_')
    if len(parts) != 2:
        raise ValueError("Неверный формат callback_data")

    action, app_id_str = parts
    app_id = int(app_id_str)

    conn = sqlite3.connect(Config.DATABASE)
    cursor = conn.cursor()

    if action == 'approve':
        # Одобрение заявки
        cursor.execute("UPDATE sellers SET status='approved' WHERE seller_id=?", (app_id,))
        cursor.execute("SELECT user_id FROM sellers WHERE seller_id=?", (app_id,))
        result = cursor.fetchone()
        if not result:
            await send_new_message(query, context, "❌ Не удалось найти заявку. Возможно, она уже была обработана.")
            return ConversationHandler.END

        user_id = result[0]
        conn.commit()

        # Уведомляем пользователя
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 Ваша заявка одобрена! Теперь вы можете принимать заказы."
        )

        # Уведомляем админа
        await send_new_message(query, context, f"✅ Заявка #{app_id} одобрена")

    elif action == 'reject':
        # Здесь новый красивый вызов
        await ask_reject_reason(update, context, app_id=app_id, message_id=query.message.message_id)
        # Вручную устанавливаем состояние FSM
        context.user_data['state'] = REJECT_REASON
        return REJECT_REASON  # <-- очень важно: вернуть REJECT_REASON, чтобы бот знал, что ждет текст!


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр профиля пользователя."""
    try:
        conn = sqlite3.connect(Config.DATABASE)
        cursor = conn.cursor()

        # Получаем роль
        cursor.execute('''SELECT role FROM users WHERE user_id=?''', (update.effective_user.id,))
        role = cursor.fetchone()

        text = f"👤 *Ваш профиль*\nРоль: {role[0] if role else 'не указана'}"

        # Если продавец — добавим статус заявки и юз-код
        if role and role[0] == 'seller':
            cursor.execute('''SELECT status, platform_usercode, platform 
                              FROM sellers 
                              WHERE user_id=? 
                              ORDER BY seller_id DESC 
                              LIMIT 1''', (update.effective_user.id,))
            row = cursor.fetchone()

            if row:
                status, usercode, platform = row
                text += f"\nСтатус заявки: {status}"
                if usercode:
                    # Автоформируем ссылку, если это username
                    if usercode.startswith('@'):
                        text += f"\nАккаунт: [ссылка](https://t.me/{usercode[1:]})"
                    elif usercode.startswith('http'):
                        text += f"\nАккаунт: [перейти]({usercode})"
                    else:
                        text += f"\nАккаунт: {usercode}"
            else:
                text += "\nСтатус заявки: нет активных заявок"

        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

    except sqlite3.Error as e:
        logger.error(f"Ошибка получения профиля: {e}")
        await update.message.reply_text("❌ Произошла ошибка при получении профиля")

    finally:
        conn.close() if 'conn' in locals() else None

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Завершение диалога."""
    await update.message.reply_text(
        "🗑 Диалог завершен. Нажмите /start чтобы начать заново.",
        reply_markup=get_default_keyboard())
    return ConversationHandler.END

# --- Главная функция ---
def main() -> None:
    """Запуск бота."""
    init_db()  # Инициализация базы данных
    
    application = Application.builder().token(Config.TOKEN).build()
    
    # Обработчик диалога
    conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('start', start),
        CallbackQueryHandler(admin_action, pattern=r'^(approve|reject)_\d+$'),
        CallbackQueryHandler(start_dialog_from_profile, pattern="^start_dialog$"),
        CallbackQueryHandler(buyer_platform, pattern="^back_to_platforms$")
    ],
    states={
        CHECK_SUBSCRIPTION: [
            CallbackQueryHandler(check_subscription, pattern='^check_subscription$'),
            CallbackQueryHandler(start, pattern='^start$')
        ],
        CHOOSE_ROLE: [
            CallbackQueryHandler(choose_role, pattern='^(seller|buyer|back_to_start)$')
        ],
        SELLER_PLATFORM: [
            CallbackQueryHandler(seller_platform, pattern='^(tiktok|youtube|instagram|vk|twitch|back_to_roles)$')
        ],
        SELLER_AUDIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, seller_audience)],
        SELLER_THEME: [MessageHandler(filters.TEXT & ~filters.COMMAND, seller_theme)],
        SELLER_VIEWS: [MessageHandler(filters.TEXT & ~filters.COMMAND, seller_views)],
        SELLER_AD_TYPE: [CallbackQueryHandler(seller_ad_type)],
        SELLER_SCREENSHOT: [MessageHandler(filters.PHOTO | filters.Document.IMAGE | filters.TEXT, seller_screenshot)],
        SELLER_CONFIRM: [CallbackQueryHandler(seller_confirm, pattern='^(confirm|edit)_application$')],
        SELLER_USERCODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, seller_usercode)],
        SELLER_NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, seller_nickname)],

        BUYER_PLATFORM: [
            CallbackQueryHandler(buyer_platform, pattern='^(tiktok|youtube|instagram|vk|twitch|another_platform|back_to_roles)$')
        ],
        BUYER_CHOOSE_SELLER: [MessageHandler(filters.TEXT & ~filters.COMMAND, buyer_choose_seller)],
        BUYER_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, buyer_message)],
        CHOOSE_BUYER_NICKNAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_buyer_nickname),
            CallbackQueryHandler(buyer_nickname_keep, pattern="^keep_nickname")
        ],

        REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, reject_reason)],
        SELLER_CUSTOM_AD_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, seller_custom_ad_type)],
        
        SELLER_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, seller_send_reply)],
        DIALOG: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, dialog_handler),
            MessageHandler(filters.TEXT & filters.Regex("^(❌ Завершить диалог)$"), end_chat)
        ],

        # # 🔄 Ответ продавца
        # REPLY_TO_BUYER: [
        #     MessageHandler(filters.TEXT & ~filters.COMMAND, seller_send_reply)
        # ],

        # # 🔁 Диалог
        # DIALOG: [
        #     CallbackQueryHandler(confirm_deal, pattern=r"^confirm_deal_\d+$"),
        #     CallbackQueryHandler(cancel_deal, pattern=r"^cancel_deal_\d+$"),
        #     MessageHandler(filters.TEXT & filters.Regex("^(❌ Завершить диалог)$"), end_chat),
        #     MessageHandler(filters.TEXT & ~filters.COMMAND, dialog_handler) # ← здесь сидит основной обмен
        # ],

        # 🔍 Профили
        SHOW_SELLER_PROFILE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, show_seller_profile),
            CallbackQueryHandler(toggle_sort, pattern="^toggle_sort$"),
            CallbackQueryHandler(buyer_platform, pattern="^back_to_roles$")
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        CommandHandler('end_chat', end_chat),
        CallbackQueryHandler(cancel, pattern='^cancel$'),
    ],
    per_message=False,  # ❗ теперь обязательно
    per_chat=False,
    per_user=True
)

    # application.add_handler(CallbackQueryHandler(start_dialog_from_profile, pattern="^start_dialog$"))
    # application.add_handler(CallbackQueryHandler(start, pattern="^back_to_start$"))

    application.add_handler(CallbackQueryHandler(seller_reply_start, pattern=r"^reply_to_\d+$"))

    application.add_handler(CommandHandler('help', help_command))

    application.add_handler(CommandHandler('clear_me', clear_my_application))

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('admin', admin_panel))
    application.add_handler(CommandHandler('profile', profile))
    application.add_handler(CallbackQueryHandler(cancel_reject, pattern='^cancel_reject_'))

    application.add_handler(CallbackQueryHandler(admin_action, pattern='^(approve|reject)'))
    
    application.run_polling()


if __name__ == '__main__':
    main()