import os
import time
import psutil
import requests
import logging
import hashlib
from threading import Thread
from flask import Flask

# --- WEB SERVER (Render uchun) ---
app = Flask(__name__)


@app.route('/')
def home():
    return "Cyber Guard is running!"


def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# --- LOG TIZIMI ---
logging.basicConfig(
    filename="cyber_guard_security.log",
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s")

# --- XAVFSIZLIK SOZLAMALARI ---
TOKEN = "8933798485:AAEMnMrd_2oXKUsKNuKBu9Zk2N3zCYgNbzM"
CHAT_ID = "7578712290"

CRITICAL_BLACK_LIST = [
    "miner.exe", "ransomware.exe", "trojan.exe", "keylogger.exe",
    "mimikatz.exe", "nc.exe", "netcat.exe", "virus.bat"
]

KNOWN_VIRUS_HASHES = [
    "44d88612fea8a8f36de82e1278abb02f",
    "5e8841671c6ecb5803974c5284178dd2",
    "8bccf2791696238380fb600df8b7ec6f"
]

SUSPICIOUS_TOOLS = ["powershell.exe", "cmd.exe", "wscript.exe", "cscript.exe"]
DANGEROUS_PATHS = ["\\appdata\\local\\temp", "\\appdata\\roaming", "\\users\\public"]


def get_file_hash(file_path):
    hash_md5 = hashlib.md5()
    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
    except Exception as e:
        logging.error(f"Xesh hisoblashda xatolik ({file_path}): {e}")
    return None


def send_critical_alert(proc_name, pid, path, reason, file_hash=None):
    f_hash = file_hash if file_hash else "Aniqlanmadi"
    text = (
        f"🚨 <b>[CYBER GUARD: CRITICAL INCIDENT]</b> 🚨\n\n"
        f"⚠️ <b>Xavf turi:</b> Zararli dastur bloklandi\n"
        f"🔥 <b>Dastur nomi:</b> <code>{proc_name}</code> (PID: {pid})\n"
        f"🛡️ <b>Asos:</b> {reason}\n"
        f"🔑 <b>MD5 Hash:</b> <code>{f_hash}</code>\n"
        f"📍 <b>Manba yo'li:</b> <code>{path}</code>\n\n"
        f"✅ <b>Holat:</b> Jarayon xotiradan o'chirildi, tizim barqaror."
    )
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})
    except Exception as e:
        logging.error(f"Telegram ogohlantirishida xatolik: {e}")


def enforce_security():
    logging.info("Cyber Guard xavfsizlik yadrosi muvaffaqiyatli ishga tushdi.")
    while True:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                proc_name = proc.info['name'].lower()
                proc_pid = proc.info['pid']
                proc_exe = proc.info['exe']
                if not proc_exe: continue
                proc_exe_lower = proc_exe.lower()
                triggered = False
                reason = ""
                current_hash = get_file_hash(proc_exe)

                if current_hash in KNOWN_VIRUS_HASHES:
                    triggered = True
                    reason = "MD5 Hash viruslar bazasiga tushdi!"
                elif proc_name in CRITICAL_BLACK_LIST:
                    triggered = True
                    reason = "Blacklistga tushdi."
                elif proc_name in SUSPICIOUS_TOOLS:
                    parent = psutil.Process(proc_pid).parent()
                    if parent and parent.name().lower() not in ["explorer.exe", "pycharm64.exe", "python.exe"]:
                        triggered = True
                        reason = "Shubhali fondagi skript faolligi."

                if triggered:
                    p = psutil.Process(proc_pid)
                    p.kill()
                    send_critical_alert(proc_name, proc_pid, proc_exe, reason, current_hash)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        time.sleep(0.5)


if __name__ == "__main__":
    # Veb-serverni ishga tushiramiz
    server_thread = Thread(target=run_server)
    server_thread.start()

    # Xavfsizlik yadrosini ishga tushiramiz
    enforce_security()
