import asyncio
import os
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiohttp import web  # Необхідно додати aiohttp в requirements.txt

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Завантаження змінних оточення
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ORDER_GROUP_ID = os.getenv("ORDER_GROUP_ID")

# Перевірка наявності токена
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не знайдено в змінних оточення!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- СЕРВЕР ДЛЯ ПІДТРИМКИ ЖИТТЄДІЯЛЬНОСТІ (RENDER KEEP-ALIVE) ---
async def handle(request):
    return web.Response(text="Sushi Mama Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Порт 10000 стандартний для Render Web Services
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    logging.info("Веб-сервер запущено на порту 10000")

# --- ЛОГІКА МЕНЮ ---
def load_menu():
    try:
        with open("menu_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("Файл menu_data.json не знайдено!")
        return {"categories": []}

menu_data = load_menu()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🛒 Перейти до меню", callback_data="main_menu"))
    await message.answer(
        f"Привіт, {message.from_user.full_name}! 👋\nВітаємо у Sushi Mama! 🍣\nОберіть дію нижче:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "main_menu")
async def show_categories(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for category in menu_data["categories"]:
        builder.row(types.InlineKeyboardButton(text=category["name"], callback_data=f"category_{category['id']}"))
    
    await callback.message.edit_text("Оберіть категорію:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("category_"))
async def show_items(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    category = next((c for c in menu_data["categories"] if c["id"] == category_id), None)
    
    if not category:
        return

    builder = InlineKeyboardBuilder()
    for item in category["items"]:
        builder.row(types.InlineKeyboardButton(text=f"{item['name']} - {item['price']} грн", callback_data=f"buy_{item['id']}"))
    
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"))
    await callback.message.edit_text(f"Категорія: {category['name']}", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    item = None
    for cat in menu_data["categories"]:
        for i in cat["items"]:
            if i["id"] == item_id:
                item = i
                break
    
    if item:
        # Відправка замовлення в групу
        order_text = (
            f"🔔 **Нове замовлення!**\n"
            f"------------------------\n"
            f"🍱 Товар: {item['name']}\n"
            f"💰 Ціна: {item['price']} грн\n"
            f"👤 Клієнт: @{callback.from_user.username or 'Без юзернейму'}\n"
            f"🆔 ID: {callback.from_user.id}"
        )
        
        try:
            await bot.send_message(chat_id=ORDER_GROUP_ID, text=order_text)
            await callback.answer("✅ Замовлення надіслано! Ми зв'яжемося з вами.", show_alert=True)
        except Exception as e:
            logging.error(f"Помилка при відправці в групу: {e}")
            await callback.answer("❌ Помилка при оформленні. Перевірте ID групи.", show_alert=True)

# --- ЗАПУСК ---
async def main():
    # Запускаємо веб-сервер для Render одночасно з ботом
    await start_web_server()
    
    logging.info("Бот прокинувся і готовий до роботи!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот зупинений")
