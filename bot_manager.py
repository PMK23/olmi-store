import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from mistralai import Mistral
import requests

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', "8520703061:AAF6-dZLHItnazaDdBslZ8ETq94hIG4kOfE")
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY', "wgKU6cSxQKxFIOAjBnuhV4FvCP6v3Lc4")
WEB_APP_URL = "https://ваш-username.github.io/olmi-store/"  # Замените на ваш URL

# Инициализация Mistral AI
mistral_client = Mistral(api_key=MISTRAL_API_KEY)

# Хранилище заказов и диалогов
orders_db = {}
user_sessions = {}

# Flask приложение для Keep-Alive
app = Flask(__name__)


@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'bot': '@olmi_connect_store_bot',
        'time': datetime.now().isoformat()
    })


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200


def run_flask():
    app.run(host='0.0.0.0', port=8080)


# Системный промпт для AI-менеджера
MANAGER_SYSTEM_PROMPT = """Ты - Алексей, профессиональный менеджер по продажам телекоммуникационного оборудования в компании OLMI Connect. 
Твои характеристики:
- Имя: Алексей
- Компания: OLMI Connect (телекоммуникационное оборудование)
- Ты дружелюбный, но профессиональный
- Отвечаешь кратко и по делу (максимум 2-3 предложения)
- Помогаешь с выбором оборудования
- Консультируешь по характеристикам
- Когда клиент готов сделать заказ, ты предлагаешь способы оплаты

Важно: Отвечай ТОЛЬКО на русском языке, будь вежлив и профессионален."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user

    # Кнопка для открытия Mini App
    keyboard = [
        [InlineKeyboardButton("🛍 Открыть магазин", web_app={"url": WEB_APP_URL})],
        [InlineKeyboardButton("📞 Связаться с менеджером", url="https://t.me/olmi_connect_support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_message = (
        f"👋 Здравствуйте, {user.first_name}!\n\n"
        f"Я Алексей, ваш персональный менеджер компании OLMI Connect.\n"
        f"Я работаю 24/7 и готов помочь с любыми вопросами!\n\n"
        f"🛒 Нажмите кнопку ниже, чтобы открыть каталог.\n"
        f"💬 Просто напишите мне, и я отвечу на любые вопросы!"
    )

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    # Сохраняем сессию пользователя
    user_sessions[user.id] = {
        'name': user.full_name,
        'username': user.username,
        'first_interaction': datetime.now().isoformat(),
        'context': []
    }

    # Отправляем приветственное сообщение в личку после заказа (если есть)
    if user.id in pending_orders:
        order = pending_orders[user.id]
        await update.message.reply_text(
            f"👋 Я вижу вы оформили заказ #{order['id']}!\n"
            f"Чем могу помочь с его оформлением?"
        )


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка данных из Mini App (заказы)"""
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        user = update.effective_user

        logger.info(f"Получены данные от пользователя {user.id}: {data}")

        if data['action'] == 'new_order':
            order = data['order']
            user_data = data.get('user', {})

            # Сохраняем заказ
            order_id = order['id']
            orders_db[order_id] = {
                'user_id': user.id,
                'user_name': user.full_name,
                'username': user.username,
                'order_data': order,
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }

            # Сохраняем как ожидающий заказ для этого пользователя
            pending_orders[user.id] = orders_db[order_id]

            # Формируем красивое сообщение о заказе
            items_list = "\n".join([
                f"• {item['name'][:50]}... - {item['quantity']} шт × {item['price']}₽ = {item['quantity'] * item['price']}₽"
                for item in order['items']
            ])

            order_message = (
                f"✅ Заказ #{order_id} успешно сформирован!\n\n"
                f"📦 Товары:\n{items_list}\n\n"
                f"💰 ИТОГО: {order['total']}₽\n\n"
                f"👋 Я Алексей, ваш менеджер. Чем могу помочь?\n"
                f"• Могу ответить на вопросы о товарах\n"
                f"• Помочь с оформлением доставки\n"
                f"• Предложить способы оплаты"
            )

            # Кнопки для быстрых действий
            keyboard = [
                [InlineKeyboardButton("💳 Оплатить сейчас", callback_data=f"pay_{order_id}")],
                [InlineKeyboardButton("📦 Доставка", callback_data=f"delivery_{order_id}")],
                [InlineKeyboardButton("❓ Задать вопрос", callback_data=f"ask_{order_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.effective_message.reply_text(order_message, reply_markup=reply_markup)

            # Отправляем уведомление администратору (опционально)
            logger.info(f"Новый заказ #{order_id} от {user.full_name} на сумму {order['total']}₽")

    except Exception as e:
        logger.error(f"Ошибка обработки заказа: {e}")
        await update.effective_message.reply_text(
            "Произошла ошибка при обработке заказа. Пожалуйста, попробуйте еще раз.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений с AI"""
    user = update.effective_user
    user_message = update.message.text

    # Отправляем индикатор "печатает"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Инициализируем сессию если нужно
    if user.id not in user_sessions:
        user_sessions[user.id] = {
            'name': user.full_name,
            'username': user.username,
            'context': []
        }

    # Добавляем сообщение в историю
    user_sessions[user.id]['context'].append({
        'role': 'user',
        'content': user_message
    })

    # Формируем контекст для AI
    messages = [
        {"role": "system", "content": MANAGER_SYSTEM_PROMPT}
    ]

    # Добавляем информацию о заказе если есть
    if user.id in pending_orders:
        order = pending_orders[user.id]
        messages.append({
            "role": "system",
            "content": f"У пользователя есть активный заказ #{order['id']} на сумму {order['order_data']['total']}₽. Товары: {json.dumps(order['order_data']['items'], ensure_ascii=False)}"
        })

    # Добавляем историю диалога
    for msg in user_sessions[user.id]['context'][-10:]:
        messages.append({"role": msg['role'], "content": msg['content']})

    try:
        # Получаем ответ от Mistral AI
        chat_response = mistral_client.chat.complete(
            model="mistral-tiny",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )

        ai_response = chat_response.choices[0].message.content

        # Сохраняем ответ AI
        user_sessions[user.id]['context'].append({
            'role': 'assistant',
            'content': ai_response
        })

        await update.message.reply_text(ai_response)

    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        await update.message.reply_text(
            "Извините, возникла техническая проблема. Напишите мне через минуту или свяжитесь с поддержкой."
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[0]
    order_id = data[1] if len(data) > 1 else None

    if action == 'pay' and order_id:
        # Имитация оплаты
        keyboard = [
            [InlineKeyboardButton("💳 Карта онлайн", callback_data=f"process_card_{order_id}")],
            [InlineKeyboardButton("🏦 По счету", callback_data=f"process_invoice_{order_id}")],
            [InlineKeyboardButton("📱 При получении", callback_data=f"process_cash_{order_id}")],
            [InlineKeyboardButton("◀️ Назад", callback_data=f"back_{order_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Выберите способ оплаты для заказа #{order_id}:",
            reply_markup=reply_markup
        )

    elif action == 'process':
        method = data[1]
        order_id = data[2]

        if method == 'card':
            # Имитация онлайн-оплаты
            payment_keyboard = [
                [InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_{order_id}")],
                [InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_{order_id}")]
            ]
            await query.edit_message_text(
                f"💳 Оплата заказа #{order_id}\n\n"
                f"Сумма: {orders_db[order_id]['order_data']['total']}₽\n\n"
                f"Тестовые данные карты:\n"
                f"Номер: 4242 4242 4242 4242\n"
                f"Срок: 12/25\n"
                f"CVV: 123\n\n"
                f"Нажмите кнопку для имитации оплаты:",
                reply_markup=InlineKeyboardMarkup(payment_keyboard)
            )

        elif method == 'invoice':
            # Счет для юрлиц
            invoice_text = (
                f"🧾 Счет на оплату #{order_id}\n\n"
                f"Плательщик: {orders_db[order_id]['user_name']}\n"
                f"Сумма: {orders_db[order_id]['order_data']['total']}₽\n"
                f"НДС 20%: {int(orders_db[order_id]['order_data']['total'] * 0.2)}₽\n\n"
                f"Реквизиты:\n"
                f"Банк: АО 'Т-Банк'\n"
                f"БИК: 044525974\n"
                f"Счет: 40702810123450123456\n"
                f"Корр.счет: 30101810145250000974\n\n"
                f"Счет отправлен вам в личные сообщения."
            )
            await query.edit_message_text(invoice_text)

        elif method == 'cash':
            # Оплата при получении
            cash_text = (
                f"📦 Заказ #{order_id} будет доставлен курьером.\n\n"
                f"Способ оплаты: наличными или картой при получении.\n"
                f"Срок доставки: 2-3 рабочих дня.\n"
                f"Курьер свяжется за час до приезда."
            )
            await query.edit_message_text(cash_text)

    elif action == 'confirm':
        # Подтверждение оплаты
        order_id = data[1]
        if order_id in orders_db:
            orders_db[order_id]['status'] = 'paid'
            if orders_db[order_id]['user_id'] in pending_orders:
                del pending_orders[orders_db[order_id]['user_id']]

            success_text = (
                f"✅ Оплата заказа #{order_id} прошла успешно!\n\n"
                f"Спасибо за покупку!\n"
                f"Чек отправлен на email.\n"
                f"Номер заказа: {order_id}\n\n"
                f"Если есть вопросы, я всегда на связи."
            )
            await query.edit_message_text(success_text)

    elif action == 'delivery':
        order_id = data[1]
        delivery_text = (
            f"📦 Доставка заказа #{order_id}\n\n"
            f"Варианты доставки:\n"
            f"• Курьером по Москве - 500₽ (1-2 дня)\n"
            f"• СДЭК до пункта выдачи - 350₽ (2-4 дня)\n"
            f"• Почта России - 300₽ (5-7 дней)\n\n"
            f"Напишите ваш город и удобный способ доставки."
        )
        await query.edit_message_text(delivery_text)

    elif action == 'ask':
        await query.edit_message_text(
            "Задайте ваш вопрос, и я с удовольствием отвечу!"
        )

    elif action == 'back':
        # Возврат к главному меню заказа
        order_id = data[1]
        keyboard = [
            [InlineKeyboardButton("💳 Оплатить сейчас", callback_data=f"pay_{order_id}")],
            [InlineKeyboardButton("📦 Доставка", callback_data=f"delivery_{order_id}")],
            [InlineKeyboardButton("❓ Задать вопрос", callback_data=f"ask_{order_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Заказ #{order_id}. Выберите действие:",
            reply_markup=reply_markup
        )

    elif action == 'cancel':
        await query.edit_message_text("Операция отменена. Могу помочь чем-то еще?")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "🆘 Помощь\n\n"
        "Я Алексей, ваш менеджер 24/7.\n\n"
        "Команды:\n"
        "/start - начать диалог\n"
        "/cart - открыть корзину\n"
        "/order - мой заказ\n"
        "/help - это сообщение\n\n"
        "Или просто напишите вопрос!"
    )
    await update.message.reply_text(help_text)


async def cart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /cart - открыть корзину"""
    keyboard = [[InlineKeyboardButton("🛒 Открыть корзину", web_app={"url": WEB_APP_URL})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Нажмите кнопку, чтобы открыть корзину:", reply_markup=reply_markup)


async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /order - информация о текущем заказе"""
    user = update.effective_user

    if user.id in pending_orders:
        order = pending_orders[user.id]
        await update.message.reply_text(
            f"Ваш текущий заказ: #{order['id']}\n"
            f"Статус: {order['status']}\n"
            f"Сумма: {order['order_data']['total']}₽"
        )
    else:
        await update.message.reply_text("У вас нет активных заказов.")


def main():
    """Запуск бота"""
    # Запускаем Flask в отдельном потоке для Keep-Alive
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask сервер для Keep-Alive запущен на порту 8080")

    # Создаем приложение бота
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cart", cart_command))
    application.add_handler(CommandHandler("order", order_command))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Запускаем бота
    logger.info("🤖 Бот-менеджер запущен и работает 24/7...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()