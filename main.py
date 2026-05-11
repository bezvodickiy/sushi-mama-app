import os
import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, MenuButtonDefault
from aiogram.filters import CommandStart
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('BOT_TOKEN')
WEB_APP_URL = os.getenv('WEB_APP_URL')
ORDER_GROUP_ID = -1003873717126 

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

user_orders = {}

DISTRICT_PRICES = {
    "Добровеличківка": 900, "Злинка": 500, "Новоолександрівка": 250,
    "Новомиколаївка": 400, "Звірівка": 300, "Комишувате": 500,
    "Піщаний Брід": 500, "Новоєгорівка": 450, "Скіфія": 750,
    "Фурманівка": 500, "Рівне": 500, "Захарівка": 750,
    "Юріївка": 900, "Адабаш": 300, "Глодоси": 550,
    "Помічна": 550, "Кам'яний міст": 400
}

async def get_menu_kb():
    import random
    url = f"{WEB_APP_URL}?v={random.randint(1, 999999)}"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🍣 Відкрити Меню", web_app=WebAppInfo(url=url))],
            [KeyboardButton(text="📞 Зв'язатися з оператором"), KeyboardButton(text="❌ Скасувати")]
        ], 
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def start(message: types.Message):
    await bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonDefault())
    user_orders.pop(message.from_user.id, None)
    await message.answer("Вітаємо у **Sushi Mama Premium**! 👋", reply_markup=await get_menu_kb(), parse_mode="Markdown")

# --- ЛОГІКА ОПЕРАТОРА (ПОЧАТОК) ---
@dp.message(F.text == "📞 Зв'язатися з оператором")
async def contact_op(message: types.Message):
    uid = message.from_user.id
    user_orders[uid] = {"step": "operator_chat"} # Ставимо статус чату з оператором
    
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Вийти з чату")]], resize_keyboard=True)
    await message.answer("Ви підключені до оператора. Напишіть ваше питання одним повідомленням, і ми відповімо вам тут.", reply_markup=kb)
    
    await bot.send_message(ORDER_GROUP_ID, f"❓ **НОВИЙ ЗАПИТ ОПЕРАТОРА!**\n👤 Клієнт: {message.from_user.full_name}\nID: (`{uid}`)\nUsername: @{message.from_user.username or 'відсутній'}")

@dp.message(F.text == "⬅️ Вийти з чату")
async def exit_operator_chat(message: types.Message):
    user_orders.pop(message.from_user.id, None)
    await message.answer("Ви вийшли з чату з оператором.", reply_markup=await get_menu_kb())

# Пересилання повідомлень від клієнта до адміна
@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "operator_chat")
async def forward_to_admin(message: types.Message):
    uid = message.from_user.id
    # Пересилаємо текст клієнта в групу
    await bot.send_message(ORDER_GROUP_ID, f"💬 **Повідомлення від клієнта** (`{uid}`):\n\n{message.text}")
# --- ЛОГІКА ОПЕРАТОРА (КІНЕЦЬ) ---

@dp.message(F.web_app_data)
async def handle_order(message: types.Message):
    data = json.loads(message.web_app_data.data)
    uid = message.from_user.id
    
    p_count = sum(i['count'] for i in data if "піца" in i['name'].lower() or "пицца" in i['name'].lower())
    s_count = sum(i['count'] for i in data if not ("піца" in i['name'].lower() or "пицца" in i['name'].lower()))
    pack_price = (p_count * 15) + (((s_count + 5) // 6) * 10)
    
    user_orders[uid] = {
        "items": data,
        "base_total": sum(i['price']*i['count'] for i in data),
        "pack_price": pack_price,
        "has_sushi": s_count > 0,
        "step": "phone"
    }
    
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Надіслати контакт", request_contact=True)]], resize_keyboard=True)
    await message.answer("📞 Надішліть номер телефону:", reply_markup=kb)

@dp.message(F.contact)
@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "phone")
async def got_phone(message: types.Message):
    uid = message.from_user.id
    if uid not in user_orders: return
    user_orders[uid]["phone"] = message.contact.phone_number if message.contact else message.text
    
    if user_orders[uid]["has_sushi"]:
        user_orders[uid]["step"] = "sticks"
        await message.answer("🥢 Скільки паличок (на скільки осіб) покласти?", reply_markup=ReplyKeyboardRemove())
    else:
        user_orders[uid]["sticks"] = "Не потрібні"
        await ask_time(message)

@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "sticks")
async def got_sticks(message: types.Message):
    user_orders[message.from_user.id]["sticks"] = message.text
    await ask_time(message)

async def ask_time(message: types.Message):
    user_orders[message.from_user.id]["step"] = "time"
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚀 На найближчий час")]], resize_keyboard=True)
    await message.answer("⏰ На котру годину підготувати?", reply_markup=kb)

@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "time")
async def got_time(message: types.Message):
    user_orders[message.from_user.id].update({"time": message.text, "step": "delivery_main"})
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏠 Самовивіз"), KeyboardButton(text="🚗 Доставка")]], resize_keyboard=True)
    await message.answer("🚚 Оберіть спосіб отримання:", reply_markup=kb)

@dp.message(F.text == "🏠 Самовивіз")
async def self_delivery(message: types.Message):
    uid = message.from_user.id
    user_orders[uid].update({"delivery": "Самовивіз", "deliv_cost": 0, "address": "вул. М.Вороного, 94", "step": "pay"})
    await ask_pay(message)

@dp.message(F.text == "🚗 Доставка")
async def delivery_choice(message: types.Message):
    user_orders[message.from_user.id]["step"] = "delivery_type"
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏙 По місту (150 грн)")], [KeyboardButton(text="🏘 По району")]], resize_keyboard=True)
    await message.answer("Оберіть зону доставки:", reply_markup=kb)

@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "delivery_type")
async def got_del_type(message: types.Message):
    uid = message.from_user.id
    if "По місту" in message.text:
        user_orders[uid].update({"delivery": "Доставка по місту", "deliv_cost": 150, "step": "addr"})
        await message.answer("📍 Вкажіть адресу:", reply_markup=ReplyKeyboardRemove())
    else:
        user_orders[uid]["step"] = "district_select"
        v_btns = [KeyboardButton(text=v) for v in DISTRICT_PRICES.keys()]
        kb = ReplyKeyboardMarkup(keyboard=[v_btns[i:i + 2] for i in range(0, len(v_btns), 2)], resize_keyboard=True)
        await message.answer("Оберіть населений пункт:", reply_markup=kb)

@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "district_select")
async def got_district(message: types.Message):
    if message.text in DISTRICT_PRICES:
        user_orders[message.from_user.id].update({"delivery": f"Район: {message.text}", "deliv_cost": DISTRICT_PRICES[message.text], "step": "addr"})
        await message.answer(f"📍 Вкажіть адресу в {message.text}:", reply_markup=ReplyKeyboardRemove())

@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "addr")
async def got_addr(message: types.Message):
    user_orders[message.from_user.id].update({"address": message.text, "step": "pay"})
    await ask_pay(message)

async def ask_pay(message: types.Message):
    user_orders[message.from_user.id]["step"] = "pay_choice"
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="💵 Готівка"), KeyboardButton(text="💳 Карта")]], resize_keyboard=True)
    await message.answer("💳 Оберіть спосіб оплати:", reply_markup=kb)

@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "pay_choice")
async def got_pay(message: types.Message):
    uid = message.from_user.id
    user_orders[uid]["pay"] = message.text
    if message.text == "💵 Готівка" and "Доставка" in user_orders[uid]["delivery"]:
        user_orders[uid]["step"] = "change"
        await message.answer("💰 З якої суми приготувати решту?", reply_markup=ReplyKeyboardRemove())
    else:
        await ask_comm(message)

@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "change")
async def got_change(message: types.Message):
    user_orders[message.from_user.id].update({"change": message.text})
    await ask_comm(message)

async def ask_comm(message: types.Message):
    user_orders[message.from_user.id]["step"] = "comm"
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Пропустити ➡️")]], resize_keyboard=True)
    await message.answer("💬 Коментар:", reply_markup=kb)

@dp.message(lambda m: user_orders.get(m.from_user.id, {}).get("step") == "comm")
async def got_comm(message: types.Message):
    user_orders[message.from_user.id].update({"comm": "" if "Пропустити" in message.text else message.text, "step": "confirm"})
    await show_check(message)

async def show_check(message: types.Message):
    d = user_orders[message.from_user.id]
    items = "\n".join([f"• {i['name']} x{i['count']}" for i in d["items"]])
    total = d['base_total'] + d['pack_price'] + d['deliv_cost']
    d['final'] = total
    check = (f"🧾 **ВАШ ЧЕК:**\n{items}\n━━━━━━━━━━━━━━━\n📦 Упаковка + Доставка: {d['pack_price']+d['deliv_cost']} грн\n"
             f"💰 **РАЗОМ: {total} грн**\n\n📞 {d['phone']}\n⏰ {d['time']}\n🥢 Палички: {d['sticks']}\n📍 {d['delivery']}: {d['address']}\n💳 {d['pay']}")
    if d.get("change"): check += f"\n💰 Решта з: {d['change']}"
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ ПІДТВЕРДЖУЮ")], [KeyboardButton(text="❌ Скасувати")]], resize_keyboard=True)
    await message.answer(check, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "✅ ПІДТВЕРДЖУЮ")
async def final_confirm(message: types.Message):
    uid = message.from_user.id
    d = user_orders.get(uid)
    if not d: return
    report = (f"🚨 **НОВЕ ЗАМОВЛЕННЯ!**\n👤 {message.from_user.full_name} (`{uid}`)\n📞 {d['phone']}\n"
              f"⏰ **ЧАС: {d['time']}**\n🥢 Палички: {d['sticks']}\n📍 {d['delivery']}: {d['address']}\n"
              f"💳 {d['pay']} | 💰 **СУМА: {d['final']} грн**\n")
    if d.get("change"): report += f"💰 Решта з: {d['change']}\n"
    report += "\n".join([f"• {i['name']} x{i['count']}" for i in d["items"]])
    await bot.send_message(ORDER_GROUP_ID, report)
    await message.answer("🎉 Прийнято! Очікуйте відповідь адміна про час.", reply_markup=await get_menu_kb())
    user_orders.pop(uid, None)

@dp.message(F.text == "❌ Скасувати")
async def cancel(message: types.Message):
    user_orders.pop(message.from_user.id, None)
    await message.answer("Скасовано.", reply_markup=await get_menu_kb())

# Відповідь адміна (Reply) клієнту
@dp.message(F.chat.id == ORDER_GROUP_ID, F.reply_to_message)
async def admin_reply(message: types.Message):
    try:
        u_id = int((message.reply_to_message.text or message.reply_to_message.caption).split('(`')[1].split('`)')[0])
        await bot.send_message(u_id, f"✉️ **Відповідь від Sushi Mama:**\n\n{message.text}", parse_mode="Markdown")
        await message.reply("✅ Надіслано!")
    except: await message.reply("❌ Не знайдено ID в повідомленні.")

async def main(): await dp.start_polling(bot)
if __name__ == '__main__': asyncio.run(main())