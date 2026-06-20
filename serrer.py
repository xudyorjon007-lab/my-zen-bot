import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

# --- SOZLAMALAR ---
BOT_TOKEN = "8904307795:AAGipj9PJzimAu8bzxypDTLqiYaqHAsiXHI"
ADMIN_ID = 7578712290  # O'zingizning Telegram ID-ingiz

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- MA'LUMOTLAR BAZASI (SQLITE) ---
def init_db():
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    # Foydalanuvchilar jadvali (ID, balans va kim taklif qilgani)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            balance REAL DEFAULT 0.0,
            referred_by INTEGER DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def register_user(user_id, full_name, referrer_id=None):
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (user_id, full_name, referred_by) VALUES (?, ?, ?)",
            (user_id, full_name, referrer_id)
        )
        conn.commit()
        # Agar taklif qilgan odam bo'lsa, uning balansiga pul (M-n: 500 so'm) qo'shish
        if referrer_id:
            cursor.execute("UPDATE users SET balance = balance + 500 WHERE user_id = ?", (referrer_id,))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        pass  # Foydalanuvchi allaqachon ro'yxatdan o'tgan
    finally:
        conn.close()
    return False


def get_all_users_count():
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_all_user_ids():
    conn = sqlite3.connect("referral_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ids


# --- KLAVIATURA ---
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Mening balansim"), KeyboardButton(text="🔗 Taklifnoma (Link)")],
            [KeyboardButton(text="🎁 Pullik Premium funksiyalar"), KeyboardButton(text="📊 Statistika")]
        ],
        resize_keyboard=True
    )


# --- HANDLERLAR ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name

    # Start komandasi ichidan referal ID ni ajratib olish (M-n: /start 1234567)
    args = message.text.split()
    referrer_id = None

    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        # O'zini o'zi taklif qilishni oldini olish
        if referrer_id == user_id:
            referrer_id = None

    # Foydalanuvchini bazadan tekshirish
    user_exists = get_user(user_id)

    if not user_exists:
        # Yangi foydalanuvchini ro'yxatga olish
        bonus_given = register_user(user_id, full_name, referrer_id)
        if bonus_given and referrer_id:
            try:
                # Taklif qilgan odamga xabar yuborish
                await bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 Tabriklaymiz! Do'stingiz {full_name} sizning havolangiz orqali kirdi. Balansingizga 100 so'm qo'shildi!"
                )
            except Exception:
                pass
        await message.answer(
            f"👋 Salom {full_name}! Botimizga xush kelibsiz. Do'stlashtirish tizimi orqali pul ishlang!",
            reply_markup=main_keyboard())
    else:
        await message.answer(f"Siz allaqachon ro'yxatdan o'tgansiz. Menyudan foydalaning:",
                             reply_markup=main_keyboard())


@dp.message(F.text == "💰 Mening balansim")
async def check_balance(message: Message):
    user = get_user(message.from_user.id)
    balance = user[2] if user else 0.0
    await message.answer(
        f"💵 **Sizning balansingiz:** {balance} so'm\n\n"
        f"💡 Pul chiqarish minimal miqdori: 50,000 so'm.\n"
        f"Pulni yechish uchun adminga yozing: @@murod_9992"
    )


@dp.message(F.text == "🔗 Taklifnoma (Link)")
async def get_link(message: Message):
    bot_info = await bot.get_me()
    # Shaxsiy referal link yaratish
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"

    await message.answer(
        f"🤝 **Sizning shaxsiy taklifnoma havolangiz:**\n\n`{ref_link}`\n\n"
        f"Ushbu linkni do'stlaringizga tarqating. Botga kirgan har bir aktiv do'stingiz uchun **100 so'm** olasiz!"
    )


@dp.message(F.text == "🎁 Pullik Premium funksiyalar")
async def premium_features(message: Message):
    await message.answer(
        "💎 **Premium Bo'lim (Tez kunda):**\n\n"
        "Bu bo'limda yig'ilgan pullaringiz evaziga yopiq kanallarga kirish, "
        "foydali kurslarni sotib olish yoki maxsus pullik bot xizmatlaridan foydalanishingiz mumkin bo'ladi."
    )


@dp.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    count = get_all_users_count()
    await message.answer(f"📊 **Botning umumiy foydalanuvchilari:** {count} ta odam.")


# --- ADMIN PANEL (REKLAMA SOTISH) ---
@dp.message(F.text.startswith("/reklama"))
async def send_global_ad(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    ad_text = message.text.replace("/reklama", "").strip()
    if not ad_text:
        await message.answer("Xato! Foydalanish: `/reklama Reklama matni`")
        return

    await message.answer("📢 Reklama barcha foydalanuvchilarga tarqatilmoqda...")

    user_ids = get_all_user_ids()
    success = 0

    for u_id in user_ids:
        try:
            await bot.send_message(chat_id=u_id, text=ad_text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(f"✅ Reklama yakunlandi. {success} ta odamga muvaffaqiyatli yetib bordi.")


# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    init_db()  # Bazani yaratish
    print("🚀 Referal tizimli pul boti ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())