import asyncio
import logging
import sqlite3
import random
import os  # Render uchun qo'shildi
from aiohttp import web  # Render uchun qo'shildi
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ==================================================================
# 1. GLOBAL SOZLAMALAR VA KONFIGURATSIYA
# ==================================================================
BOT_TOKEN = "8635585153:AAEFwTbhc2bi_HJQNSBLyTGBtwNcR8cbkMc"
ADMIN_ID = 7578712290

REQUIRED_CHANNEL = -1002389525073
CHANNEL_INVITE_LINK = "https://t.me/musicsvlog"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ==================================================================
# 2. FSM (HOLATLAR TIZIMI)
# ==================================================================
class GameStates(StatesGroup):
    waiting_for_math = State()
    waiting_for_guess = State()
    waiting_for_anagram = State()


class SupportStates(StatesGroup):
    waiting_for_msg = State()


class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_target_id = State()
    waiting_for_balance_amount = State()


# ==================================================================
# 3. MA'LUMOTLAR BAZASI TIZIMI (SQLITE3)
# ==================================================================
def init_db():
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance INTEGER DEFAULT 100,
            last_bonus TEXT,
            games_played INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            joined_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referral_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()


def db_add_user(user_id, username, full_name, referrer_id=0):
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO users (user_id, username, full_name, balance, referred_by, joined_at) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, full_name, 100, referrer_id, now))
        conn.commit()

        if referrer_id != 0 and referrer_id != user_id:
            cursor.execute("UPDATE users SET balance = balance + 250 WHERE user_id = ?", (referrer_id,))
            cursor.execute("INSERT INTO referral_logs (referrer_id, referred_id, timestamp) VALUES (?, ?, ?)",
                           (referrer_id, user_id, now))
            conn.commit()
    conn.close()


def db_get_user(user_id):
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def db_update_balance(user_id, amount):
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def db_set_absolute_balance(user_id, amount):
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def db_update_game_stats(user_id, is_win=False):
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    if is_win:
        cursor.execute("UPDATE users SET games_played = games_played + 1, games_won = games_won + 1 WHERE user_id = ?",
                       (user_id,))
    else:
        cursor.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def db_update_bonus_time(user_id):
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now, user_id))
    conn.commit()
    conn.close()


def db_get_total_users_count():
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def db_get_all_user_ids():
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ids


def db_get_top_users():
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, balance FROM users ORDER BY balance DESC LIMIT 10")
    top = cursor.fetchall()
    conn.close()
    return top


def db_get_referrals_count(user_id):
    conn = sqlite3.connect("grand_bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM referral_logs WHERE referrer_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ==================================================================
# 4. KLAVIATURALAR TIZIMI VA OBUNA TEKSHIRUVCHI
# ==================================================================
async def is_user_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        return False
    except Exception:
        return False


def get_subscription_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Kanalga obuna bo'lish", url=CHANNEL_INVITE_LINK)
    builder.button(text="✅ Obunani tekshirish", callback_data="check_sub_status")
    builder.adjust(1)
    return builder.as_markup()


def get_main_reply_keyboard(user_id):
    builder = ReplyKeyboardBuilder()
    builder.button(text="👤 Profil")
    builder.button(text="🎁 Kunlik Bonus")
    builder.button(text="🎮 O'yinlar Markazi")
    builder.button(text="👥 Referal Tizimi")
    builder.button(text="📊 Reyting (Top 10)")
    builder.button(text="💬 Adminga Murojaat")

    if user_id == ADMIN_ID:
        builder.button(text="🛠 Katta Admin Panel")

    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# JAVOB BERMAYOTGAN VA XATO CHIQARAYOTGAN QISM MANA SHU YERDA TUZATILDI:
def get_games_inline_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🧮 Matematika O'yini", callback_data="play_math_game")
    builder.button(text="🔢 Yashirin Son O'yini", callback_data="play_guess_game")
    builder.button(text="🔤 Harflardan So'z O'yini", callback_data="play_anagram_game")
    builder.button(text="🎫 Omadli Chipta (Tavakkal)", callback_data="play_ticket_game")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_inline_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Barcha xabar tarqatish", callback_data="adm_broadcast")
    builder.button(text="💰 Balansni tahrirlash", callback_data="adm_edit_balance")
    builder.button(text="💾 Bazani yuklab olish", callback_data="adm_download_db")
    builder.adjust(1)
    return builder.as_markup()


async def is_subscribed_checker(message: Message) -> bool:
    if message.from_user.id == ADMIN_ID:
        return True
    if not await is_user_subscribed(message.from_user.id):
        await message.answer("⚠️ Botdan foydalanish uchun avval kanalga a'zo bo'ling:",
                             reply_markup=get_subscription_keyboard())
        return False
    return True


# ==================================================================
# 5. COMMAND HANDLERLARI (START)
# ==================================================================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    full_name = message.from_user.full_name

    args = message.text.split()
    referrer_id = 0
    if len(args) > 1 and args[1].isdigit():
        potential_referrer = int(args[1])
        if potential_referrer != user_id:
            referrer_id = potential_referrer

    db_add_user(user_id, username, full_name, referrer_id)

    if user_id != ADMIN_ID and not await is_user_subscribed(user_id):
        await message.answer(
            f"👋 <b>Assalomu alaykum, {full_name}!</b>\n\n"
            f"Botning barcha funksiyalaridan to'liq foydalanish va o'yinlarni boshlash uchun "
            f"quyidagi rasmiy kanalimizga a'zo bo'lishingiz shart:",
            parse_mode="HTML", reply_markup=get_subscription_keyboard()
        )
        return

    if referrer_id != 0:
        try:
            await bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 <b>Yangi taklif!</b> Havolangiz orqali {full_name} botga qo'shildi va balansingizga <b>+250 ball</b> yozildi!",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await message.answer(
        f"🚀 <b>Xush kelibsiz!</b>\nSiz botdan to'liq foydalanish huquqiga egasiz. "
        f"O'yinlar o'ynang, ballar to'plang va reytingda peshqadam bo'ling!",
        parse_mode="HTML", reply_markup=get_main_reply_keyboard(user_id)
    )


@dp.callback_query(F.data == "check_sub_status")
async def callback_check_sub(call: CallbackQuery):
    user_id = call.from_user.id
    if user_id == ADMIN_ID or await is_user_subscribed(user_id):
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer(
            "🎉 <b>Tabriklaymiz!</b> Obunangiz muvaffaqiyatli tasdiqlandi. "
            "Botning asosiy boshqaruv paneli ochildi:",
            parse_mode="HTML", reply_markup=get_main_reply_keyboard(user_id)
        )
    else:
        await call.answer("❌ Siz hali ham kanalga a'zo bo'lmadingiz! Iltimos, obuna bo'lib qayta tekshiring.",
                          show_alert=True)


# ==================================================================
# 6. ASOSIY MENYU NAVIGATSIYASI (REPLY BUTTONS LOGIC)
# ==================================================================
@dp.message(F.text == "👤 Profil")
async def show_user_profile(message: Message):
    if not await is_subscribed_checker(message): return

    user = db_get_user(message.from_user.id)
    if not user: return

    wr = 0
    if user[5] > 0:
        wr = round((user[6] / user[5]) * 100, 1)

    profile_msg = (
        f"<b>👤 Sizning Shaxsiy Profilingiz:</b>\n\n"
        f"🆔 <b>Sizning Telegram ID:</b> <code>{user[0]}</code>\n"
        f"✍️ <b>Ismingiz:</b> {user[2]}\n"
        f"🏷 <b>Username:</b> @{user[1]}\n"
        f"💰 <b>Joriy Balans:</b> <code>{user[3]}</code> ball\n\n"
        f"📊 <b>O'yinlar Statistikasi:</b>\n"
        f"├ Jami o'ynalgan: {user[5]} marta\n"
        f"├ G'alaba qozonilgan: {user[6]} marta\n"
        f"└ Ko'rsatkich (WinRate): {wr}%\n\n"
        f"📅 <b>Ro'yxatdan o'tgan sana:</b> {user[8]}"
    )
    await message.answer(profile_msg, parse_mode="HTML")


@dp.message(F.text == "🎁 Kunlik Bonus")
async def claim_daily_bonus(message: Message):
    if not await is_subscribed_checker(message): return

    user_id = message.from_user.id
    user = db_get_user(user_id)
    last_bonus_str = user[4]
    now = datetime.now()

    if last_bonus_str:
        last_time = datetime.strptime(last_bonus_str, "%Y-%m-%d %H:%M:%S")
        if now - last_time < timedelta(days=1):
            diff = timedelta(days=1) - (now - last_time)
            h, rem = divmod(diff.seconds, 3600)
            m, _ = divmod(rem, 60)
            await message.answer(
                f"❌ <b>Siz bugun bonus olgansiz!</b>\nKeyingi bonusga <b>{h} soat, {m} daqiqa</b> qoldi.",
                parse_mode="HTML")
            return

    bonus_reward = random.randint(50, 200)
    db_update_balance(user_id, bonus_reward)
    db_update_bonus_time(user_id)
    await message.answer(
        f"🎁 <b>Tabriklaymiz!</b> Kunlik omadingiz kulib boqdi va sizga <b>+{bonus_reward}</b> ball berildi!",
        parse_mode="HTML")


@dp.message(F.text == "👥 Referal Tizimi")
async def show_referral_system(message: Message):
    if not await is_subscribed_checker(message): return

    user_id = message.from_user.id
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={user_id}"
    count = db_get_referrals_count(user_id)

    ref_text = (
        f"<b>👥 Takliflar (Referal) Tizimi:</b>\n\n"
        f"Do'stlaringizni shaxsiy havolangiz orqali botga taklif qiling. "
        f"Botga qo'shilgan har bir faol do'stingiz uchun sizga <b>+250 ball</b> taqdim etiladi!\n\n"
        f"📊 <b>Sizning referal statistikangiz:</b>\n"
        f"Jami taklif qilinganlar: <b>{count} ta</b>\n\n"
        f"🔗 <b>Sizning shaxsiy referal havolangiz:</b>\n<code>{ref_link}</code>"
    )
    await message.answer(ref_text, parse_mode="HTML")


@dp.message(F.text == "📊 Reyting (Top 10)")
async def show_leaderboard(message: Message):
    if not await is_subscribed_checker(message): return

    top_list = db_get_top_users()
    leaderboard_text = "<b>🏆 Botdagi Eng Boy Top 10 Foydalanuvchilar:</b>\n\n"

    for index, player in enumerate(top_list, 1):
        medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"{index}."
        leaderboard_text += f"{medal} {player[0]} — <code>{player[1]}</code> ball\n"

    await message.answer(leaderboard_text, parse_mode="HTML")


@dp.message(F.text == "💬 Adminga Murojaat")
async def start_support_communication(message: Message, state: FSMContext):
    if not await is_subscribed_checker(message): return
    await message.answer("✍️ Adminga yubormoqchi bo'lgan xabaringizni matn shaklida yozing:")
    await state.set_state(SupportStates.waiting_for_msg)


@dp.message(SupportStates.waiting_for_msg)
async def process_support_msg(message: Message, state: FSMContext):
    msg_text = message.text
    sender_id = message.from_user.id
    sender_name = message.from_user.full_name

    admin_alert = (
        f"📩 <b>Yangi Murojaat Keldi!</b>\n"
        f"Kimdan: {sender_name} (ID: <code>{sender_id}</code>)\n"
        f"Xabar: <i>{msg_text}</i>"
    )
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_alert, parse_mode="HTML")
        await message.answer("✅ Xabaringiz muvaffaqiyatli yuborildi. Admin tez orada javob beradi!")
    except Exception:
        await message.answer("❌ Xabar yuborishda xatolik yuz berdi. Bot admini topilmadi.")
    await state.clear()


# ==================================================================
# 7. 🎮 O'YINLAR MARKAZI (INLINE CHIQISH VA LOGIKA)
# ==================================================================
@dp.message(F.text == "🎮 O'yinlar Markazi")
async def open_games_hub(message: Message):
    if not await is_subscribed_checker(message): return
    await message.answer(
        "🎮 <b>O'yinlar markaziga xush kelibsiz!</b>\nO'zingizga ma'qul o'yinni tanlang va ballar ishlang:",
        parse_mode="HTML", reply_markup=get_games_inline_keyboard())


# --- A) MATEMATIKA O'YINI ---
MATH_DATA = [
    {"q": "(3x - 4)^2 ifodani ochganda x ning koeffitsiyenti nechaga teng?", "a": "-24"},
    {"q": "2x + 15 = 4x - 5 tenglamaning javobini toping.", "a": "10"},
    {"q": "Kvadratning yuzi 64 sm^2. Uning perimetri necha sm?", "a": "32"},
    {"q": "3^x = 243 bo'lsa, x ning qiymati nechaga teng?", "a": "5"}
]


@dp.callback_query(F.data == "play_math_game")
async def start_math_game(call: CallbackQuery, state: FSMContext):
    user = db_get_user(call.from_user.id)
    if user[3] < 40:
        await call.answer("❌ Ushbu o'yin uchun hisobingizda kamida 40 ball bo'lishi shart!", show_alert=True)
        return

    await call.answer()
    problem = random.choice(MATH_DATA)
    await state.update_data(correct_math_ans=problem["a"])

    await call.message.edit_text(
        f"<b>🧮 Matematika O'yini:</b>\n\n"
        f"Savol: <b>{problem['q']}</b>\n\n"
        f"💵 Tikish: 40 ball | Yutuq: +120 ball\n"
        f"Javobingizni faqat raqam ko'rinishida chatga yozing:",
        parse_mode="HTML"
    )
    await state.set_state(GameStates.waiting_for_math)


@dp.message(GameStates.waiting_for_math)
async def check_math_answer(message: Message, state: FSMContext):
    user_ans = message.text.strip()
    data = await state.get_data()
    correct_ans = data.get("correct_math_ans")

    if user_ans == correct_ans:
        db_update_balance(message.from_user.id, 120)
        db_update_game_stats(message.from_user.id, is_win=True)
        await message.answer("🎉 <b>To'g'ri javob!</b> Hisobingizga <b>+120 ball</b> qo'shildi!", parse_mode="HTML")
    else:
        db_update_balance(message.from_user.id, -40)
        db_update_game_stats(message.from_user.id, is_win=False)
        await message.answer(
            f"❌ <b>Noto'g'ri javob!</b> To'g'ri javob: <b>{correct_ans}</b> edi. Hisobingizdan 40 ball chegirildi.",
            parse_mode="HTML")
    await state.clear()


# --- B) SONNI TOP O'YINI ---
@dp.callback_query(F.data == "play_guess_game")
async def start_guess_game(call: CallbackQuery, state: FSMContext):
    user = db_get_user(call.from_user.id)
    if user[3] < 30:
        await call.answer("❌ Ushbu o'yin uchun kamida 30 ball kerak!", show_alert=True)
        return

    await call.answer()
    secret_num = random.randint(1, 10)
    await state.update_data(secret_number=secret_num)

    await call.message.edit_text(
        "<b>🔢 Yashirin Son o'yini:</b>\n\n"
        "Men 1 dan 10 gacha bo'lgan butun son o'yladim. Uni topishga harakat qiling.\n"
        "💵 Tikish: 30 ball | Yutuq: +100 ball\n"
        "O'ylagan soningizni chatga yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(GameStates.waiting_for_guess)


@dp.message(GameStates.waiting_for_guess)
async def check_guess_answer(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Iltimos, faqat butun raqam yuboring:")
        return

    user_num = int(message.text)
    data = await state.get_data()
    secret = data.get("secret_number")

    if user_num == secret:
        db_update_balance(message.from_user.id, 100)
        db_update_game_stats(message.from_user.id, is_win=True)
        await message.answer(
            f"🎉 <b>Daxshat! Omadingiz keldi.</b> Men rostdan ham {secret} sonini o'ylagandim. <b>+100 ball!</b>",
            parse_mode="HTML")
    else:
        db_update_balance(message.from_user.id, -30)
        db_update_game_stats(message.from_user.id, is_win=False)
        await message.answer(
            f"❌ <b>Afsuski topa olmadingiz!</b> Men <b>{secret}</b> sonini o'ylagan edim. Hisobingizdan -30 ball.",
            parse_mode="HTML")
    await state.clear()


# --- C) ANAGRAMMA O'YINI ---
ANAGRAMS = [
    {"scrambled": "aktbloop", "original": "topbolka"},
    {"scrambled": "atmelnpat", "original": "parlament"},
    {"scrambled": "ompyukert", "original": "kompyuter"},
    {"scrambled": "ntleeof", "original": "telefon"}
]


@dp.callback_query(F.data == "play_anagram_game")
async def start_anagram_game(call: CallbackQuery, state: FSMContext):
    await call.answer()
    target = random.choice(ANAGRAMS)
    await state.update_data(correct_word=target["original"])

    await call.message.edit_text(
        f"<b>🔤 Harflardan so'z yasash o'yini:</b>\n\n"
        f"Berilgan aralash harflardan to'g'ri so'zni tiklang: <b>{target['scrambled']}</b>\n\n"
        f"🎁 Mukofot: +80 ball | Xato javob uchun ball olinmaydi.\n"
        f"Javobni kichik harflarda yozib yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(GameStates.waiting_for_anagram)


@dp.message(GameStates.waiting_for_anagram)
async def check_anagram_answer(message: Message, state: FSMContext):
    user_word = message.text.strip().lower()
    data = await state.get_data()
    correct_word = data.get("correct_word")

    if user_word == correct_word:
        db_update_balance(message.from_user.id, 80)
        db_update_game_stats(message.from_user.id, is_win=True)
        await message.answer(f"🎉 <b>Barakalla!</b> Yashirin so'z to'g'ri topildi. Sizga <b>+80 ball</b> berildi!",
                             parse_mode="HTML")
    else:
        db_update_game_stats(message.from_user.id, is_win=False)
        await message.answer(
            f"❌ Noto'g'ri. Bu yashirin so'z aslida <b>{correct_word}</b> edi. Keyingi o'yinlarda omad tilaymiz!",
            parse_mode="HTML")
    await state.clear()


# --- D) OMADLI CHIPTA (TAVAKKAL) ---
@dp.callback_query(F.data == "play_ticket_game")
async def process_ticket_game(call: CallbackQuery):
    user = db_get_user(call.from_user.id)
    if user[3] < 50:
        await call.answer("❌ Omadli chiptani sotib olish uchun kamida 50 ball kerak!", show_alert=True)
        return

    await call.answer()
    options = ["LOSE", "WIN_SMALL", "LOSE", "JACKPOT", "LOSE"]
    result = random.choice(options)

    if result == "WIN_SMALL":
        db_update_balance(call.from_user.id, 100)
        db_update_game_stats(call.from_user.id, is_win=True)
        await call.message.edit_text("🎫 <b>Natija:</b> Chiptadan yutuq chiqdi! Siz <b>+100 ball</b> yutdingiz.",
                                     parse_mode="HTML")
    elif result == "JACKPOT":
        db_update_balance(call.from_user.id, 400)
        db_update_game_stats(call.from_user.id, is_win=True)
        await call.message.edit_text("🔥 <b>JACKPOT!</b> Chiptangiz daxshatli super yutuqli chiqdi! <b>+400 ball!</b>",
                                     parse_mode="HTML")
    else:
        db_update_balance(call.from_user.id, -50)
        db_update_game_stats(call.from_user.id, is_win=False)
        await call.message.edit_text("🎫 <b>Natija:</b> Afsuski chipta bo'sh chiqdi. -50 ball.", parse_mode="HTML")


# ==================================================================
# 8. 🛠 ADMIN PANEL LOGIKASI (REKLAMA VA AMALLAR)
# ==================================================================
@dp.message(F.text == "🛠 Katta Admin Panel")
async def open_admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID: return
    total = db_get_total_users_count()
    await message.answer(
        f"<b>🛠 Kuchli Admin paneliga xush kelibsiz!</b>\n\n"
        f"Bazada jami ro'yxatdan o'tganlar: <b>{total} ta foydalanuvchi</b>\n"
        f"Kerakli boshqaruv amalini tanlang:",
        parse_mode="HTML", reply_markup=get_admin_inline_keyboard()
    )


@dp.callback_query(F.data == "adm_broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.answer()
    await call.message.answer("📢 Barcha foydalanuvchilarga yubormoqchi bo'lgan reklama/xabar matnini kiriting:")
    await state.set_state(AdminStates.waiting_for_broadcast)


@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    uids = db_get_all_user_ids()
    success, failed = 0, 0
    progress = await message.answer("🔄 Reklama xabari tarqatilmoqda, kuting...")

    for uid in uids:
        try:
            await bot.send_message(chat_id=uid, text=message.text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await progress.edit_text(
        f"📢 <b>Xabar tarqatish tugadi:</b>\n\n✅ Yetkazildi: {success} ta\n❌ Bloklanganlar: {failed} ta",
        parse_mode="HTML")
    await state.clear()


@dp.callback_query(F.data == "adm_edit_balance")
async def start_edit_balance(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.answer()
    await call.message.answer(
        "👤 Balansini o'zgartirmoqchi bo'lgan foydalanuvchining shaxsiy Telegram ID raqamini yozing:")
    await state.set_state(AdminStates.waiting_for_target_id)


@dp.message(AdminStates.waiting_for_target_id)
async def get_target_id_for_balance(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        await message.answer("⚠️ ID faqat raqamlardan iborat bo'ladi. Qayta kiriting:")
        return
    await state.update_data(target_user_id=int(message.text))
    await message.answer("💰 Endi ushbu foydalanuvchiga qancha mutloq ball o'rnatmoqchisiz? Miqdorini yozing:")
    await state.set_state(AdminStates.waiting_for_balance_amount)


@dp.message(AdminStates.waiting_for_balance_amount)
async def set_user_balance_finish(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        await message.answer("⚠️ Miqdorni sonda yozing:")
        return

    amount = int(message.text)
    data = await state.get_data()
    target_id = data.get("target_user_id")

    user = db_get_user(target_id)
    if not user:
        await message.answer("❌ Bunday foydalanuvchi ma'lumotlar bazasida mavjud emas!")
        await state.clear()
        return

    db_set_absolute_balance(target_id, amount)
    try:
        await bot.send_message(chat_id=target_id,
                               text=f"⚡️ <b>Admin qaroriga ko'ra sizning balansingiz {amount} ball qilib belgilandi!</b>",
                               parse_mode="HTML")
        await message.answer(f"✅ Foydalanuvchi ({user[2]}) balansi {amount} ballga muvaffaqiyatli o'zgartirildi!")
    except Exception:
        await message.answer(
            f"✅ Balans o'zgardi, lekin foydalanuvchi botni bloklagani uchun unga bildirishnoma bormadi.")
    await state.clear()


@dp.callback_query(F.data == "adm_download_db")
async def download_database_file(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    await call.answer()
    try:
        db_file = FSInputFile("grand_bot_database.db")
        await call.message.answer_document(document=db_file,
                                           caption="📁 Botning joriy SQLite3 to'liq ma'lumotlar bazasi fayli.")
    except Exception as e:
        await call.message.answer(f"Xatolik yuz berdi: {e}")


# ==================================================================
# 9. TIZIMNING PORT OCHISH VA POLLING ISHGA TUSHURILISHI (RENDER UCHUN)
# ==================================================================
PORT = int(os.environ.get("PORT", 8080))


async def handle(request):
    return web.Response(text="Bot ishlamoqda!")


async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Server {PORT} portida ishga tushdi!")


async def main():
    init_db()
    await start_web_server()

    print("[LOG] Bot muvaffaqiyatli start oldi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("[LOG] Bot faoliyati yakunlandi!")
