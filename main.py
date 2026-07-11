import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
import asyncio

# 1. Log yuritish (tizim xatolarini kuzatish uchun)
logging.basicConfig(level=logging.INFO)


# 2. SQLite bazasini sozlash (Kinolarni saqlash uchun)
def setup_db():
    conn = sqlite3.connect("kinolar.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kino (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT UNIQUE,
            nomi TEXT,
            file_id TEXT
        )
    """)
    # Baza to'ldirilgan bo'lsa, standart test ma'lumotini qo'shish
    cursor.execute("INSERT OR IGNORE INTO kino (kod, nomi, file_id) VALUES (?, ?, ?)",
                   ("500", "Inception", "CQACAgIAAxkBAA..."))
    conn.commit()
    conn.close()


# 3. Bot va Dispatcher
TOKEN = "8787086359:AAH4S9mSSjHYrfEUkNP8P7DaDU_OYGZ19Sk"
bot = Bot(token=TOKEN)
dp = Dispatcher()


# 4. Kino qidirish funksiyasi
def get_kino_from_db(kod):
    conn = sqlite3.connect("kinolar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT nomi, file_id FROM kino WHERE kod = ?", (kod,))
    result = cursor.fetchone()
    conn.close()
    return result


# 5. Handlerlar
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Xush kelibsiz! Kino kodini yuboring.")


@dp.message(F.text)
async def handle_kino(message: Message):
    kod = message.text.strip()
    kino = get_kino_from_db(kod)

    if kino:
        await message.answer_video(video=kino[1], caption=f"Topildi: {kino[0]}")
    else:
        await message.answer("Kino topilmadi. Kodni tekshiring.")


# --- Bu yerda siz yuzlab kinolarni qo'shish uchun funksiyalar,
# --- admin buyruqlar, statistikani hisoblash funksiyalari va
# --- boshqa yordamchi modullarni yozib, kod hajmini oshirishingiz mumkin. ---

async def main():
    setup_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())