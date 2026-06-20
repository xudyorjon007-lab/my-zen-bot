import asyncio
import socket
import uuid
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode

# 1. SOZLAMALAR
TOKEN = "8643100353:AAF9xqtfoWHgKktRbVP6EsVODsaozOiYOdg"
bot = Bot(token=TOKEN)
dp = Dispatcher()


# 2. SKANERLASH FUNKSIYALARI
async def check_port(target, port):
    try:
        # Portga ulanishni asinxron tekshirish
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(target, port),
            timeout=2.0
        )
        writer.close()
        await writer.wait_closed()
        return port
    except:
        return None


async def scan_target(target):
    # Asosiy portlar ro'yxati
    ports_to_check = [21, 22, 23, 25, 53, 80, 110, 143, 443, 3306, 3389, 8080, 8443]
    tasks = [check_port(target, p) for p in ports_to_check]
    results = await asyncio.gather(*tasks)
    return [p for p in results if p is not None]


# 3. MENYU
menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔍 Skanerlashni boshlash")]],
    resize_keyboard=True
)


# 4. HANDLERLAR
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Xush kelibsiz! Tarmoq xavfsizligini tekshirish uchun tugmani bosing.", reply_markup=menu)


@dp.message(F.text == "🔍 Skanerlashni boshlash")
async def ask_target(message: types.Message):
    await message.answer("Skanerlamoqchi bo'lgan domen yoki IP manzilni yuboring:")


@dp.message()
async def process_scan(message: types.Message):
    target = message.text.strip()
    if target.startswith("/"):
        return

    session_id = str(uuid.uuid4())[:8].upper()
    status_msg = await message.answer(f"🔍 <b>{target}</b> skanerlanmoqda...", parse_mode=ParseMode.HTML)

    try:
        # Sinxron gethostbyname'ni asinxron fonda ishga tushiramiz (bot qotib qolmasligi uchun)
        loop = asyncio.get_event_loop()
        ip_addr = await loop.run_in_executor(None, socket.gethostbyname, target)

        # Portlarni skanerlash
        open_ports = await scan_target(ip_addr)

        if open_ports:
            ports_str = ", ".join(map(str, sorted(open_ports)))
            result_text = (
                f"✅ <b>Skanerlash natijasi</b>\n\n"
                f"🌐 Target: <code>{target}</code>\n"
                f"📍 IP: <code>{ip_addr}</code>\n"
                f"🔓 Ochiq portlar: <code>{ports_str}</code>\n\n"
                f"🆔 Session ID: <code>{session_id}</code>"
            )
        else:
            result_text = (
                f"⚠️ <b>Skanerlash natijasi</b>\n\n"
                f"🌐 Target: <code>{target}</code>\n"
                f"📍 IP: <code>{ip_addr}</code>\n"
                f"🚫 Ochiq portlar topilmadi.\n\n"
                f"🆔 Session ID: <code>{session_id}</code>"
            )
    except Exception as e:
        result_text = f"❌ Xatolik: <code>{target}</code> manzilini aniqlab bo'lmadi.\nSabab: <code>{e}</code>"

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        text=result_text,
        parse_mode=ParseMode.HTML
    )


# 5. ISHGA TUSHIRISH
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if name == "__main__":
    asyncio.run(main())