# Ваш исправленный bot2.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, ContextTypes, filters
)
import sqlite3
import logging

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ваш токен
TOKEN = '7423580380:AAEchqJy_1Kn4O20V2nAGE2pjzW4c-O5qhw'

# Состояния
CHECK_SUBSCRIPTION, CHOOSE_ROLE, SELLER_PLATFORM, SELLER_AUDIENCE, SELLER_THEME, SELLER_VIEWS, \
SELLER_AD_TYPE, SELLER_SCREENSHOT, SELLER_CONFIRM, BUYER_PLATFORM, BUYER_CHOOSE_SELLER, BUYER_MESSAGE, REJECT_REASON = range(13)

# Старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[InlineKeyboardButton("Продавец", callback_data='seller'),
                 InlineKeyboardButton("Покупатель", callback_data='buyer')]]
    await update.message.reply_text("Кто вы?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_ROLE

# Обработчик роли
async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Вы выбрали роль.")
    return ConversationHandler.END

# Функция запроса причины отказа
async def ask_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, app_id: int, message_id: int = None):
    context.user_data['reject_app_id'] = app_id
    context.user_data['reject_message_id'] = message_id

    if update.callback_query:
        await update.callback_query.message.reply_text("Укажите причину отказа:")
    else:
        await update.message.reply_text("Укажите причину отказа:")

# Обработка причины отказа
async def reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        logger.warning("Нет сообщения от пользователя")
        return ConversationHandler.END

    reason = update.message.text
    print("Пойман текст отказа:", reason)

    app_id = context.user_data.get('reject_app_id')

    if not app_id:
        await update.message.reply_text("❌ Ошибка: заявка не найдена.")
        return ConversationHandler.END

    try:
        # Подключение к базе данных
        conn = sqlite3.connect('your_database.db')
        cursor = conn.cursor()

        # Получаем user_id по app_id
        cursor.execute("SELECT user_id FROM sellers WHERE seller_id=?", (app_id,))
        result = cursor.fetchone()

        if not result:
            await update.message.reply_text("❌ Пользователь заявки не найден.")
            return ConversationHandler.END

        user_id = result[0]

        # Обновляем статус заявки в базе
        cursor.execute("UPDATE sellers SET status='rejected', reject_reason=? WHERE seller_id=?", (reason, app_id))
        conn.commit()

    except Exception as e:
        logger.error(f"Ошибка базы данных: {e}")
        await update.message.reply_text("❌ Ошибка базы данных при обновлении заявки.")
        return ConversationHandler.END

    finally:
        conn.close()

    # Уведомление пользователя с кнопкой
    keyboard = [[InlineKeyboardButton("Подать новую заявку", callback_data='start')]]
    await context.bot.send_message(
        chat_id=user_id,
        text=f"❌ *Ваша заявка отклонена!*\n\n*Причина:* _{reason}_",
        parse_mode='MarkdownV2',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Уведомляем админа
    await update.message.reply_text(f"✅ Заявка #{app_id} отклонена. Пользователь уведомлён.")

    return ConversationHandler.END

# Обработчик admin_action
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith('reject_'):
        app_id = int(query.data.split('_')[1])
        await ask_reject_reason(update, context, app_id=app_id, message_id=query.message.message_id)
        return REJECT_REASON

# Функция отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

# Основная функция запуска бота
def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSE_ROLE: [CallbackQueryHandler(choose_role)],
            REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, reject_reason)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(admin_action, pattern='^reject_\\d+$'))

    application.run_polling()

if __name__ == '__main__':
    main()