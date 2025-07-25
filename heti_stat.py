import json
import datetime
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
CHAT_ID = 'YOUR_TELEGRAM_CHAT_ID'

HETI_FILE = "heti_tippek.json"

def load_heti_tippek():
    try:
        with open(HETI_FILE, "r", encoding="utf8") as f:
            hetitippek = json.load(f)
    except:
        hetitippek = []
    return hetitippek

def heti_stat_tipus_szerint(hetitippek, tipus):
    talalt = sum(1 for t in hetitippek if t["kat"] == tipus and t.get("talalt"))
    hibas = sum(1 for t in hetitippek if t["kat"] == tipus and not t.get("talalt"))
    ossz_odds = 1.0
    for t in hetitippek:
        if t["kat"] == tipus and t.get("talalt"):
            try: ossz_odds *= float(t["odd"])
            except: pass
    return talalt, hibas, ossz_odds

def format_heti_stat(hetitippek):
    n = len(hetitippek)
    talalt = sum(1 for t in hetitippek if t.get("talalt"))
    hibas = n - talalt
    arany = f"{(talalt/n)*100:.1f}%" if n else "0%"
    ossz_odds = 1.0
    for t in hetitippek:
        if t.get("talalt"):
            try: ossz_odds *= float(t["odd"])
            except: pass
    nyeremeny = 1000 * ossz_odds if talalt else 0

    # Külön biztos/kockázatos stat
    biztos_talalt, biztos_hibas, biztos_odds = heti_stat_tipus_szerint(hetitippek, "Biztos tipp")
    kock_talalt, kock_hibas, kock_odds = heti_stat_tipus_szerint(hetitippek, "Kockázatos tipp")
    biztos_arany = f"{(biztos_talalt/(biztos_talalt+biztos_hibas))*100:.1f}%" if (biztos_talalt+biztos_hibas) else "0%"
    kock_arany = f"{(kock_talalt/(kock_talalt+kock_hibas))*100:.1f}%" if (kock_talalt+kock_hibas) else "0%"

    week = datetime.date.today().isocalendar()[1]

    msg = f"📊 *Heti Tippmix statisztika* (Week {week})\n\n"
    msg += f"Összes tipp: {n}\n"
    msg += f"Talált: {talalt}\n"
    msg += f"Hibás: {hibas}\n"
    msg += f"Találati arány: {arany}\n"
    msg += f"Összesített szorzó: {ossz_odds:.2f}\n"
    msg += f"Elméleti nyeremény 1000 Ft-ra: {nyeremeny:.0f} Ft\n\n"

    msg += f"• *Biztos tippek*: {biztos_talalt+biztos_hibas} db | {biztos_arany} | Szorzó: {biztos_odds:.2f}\n"
    msg += f"• *Kockázatos tippek*: {kock_talalt+kock_hibas} db | {kock_arany} | Szorzó: {kock_odds:.2f}\n"

    return msg

def main():
    hetitippek = load_heti_tippek()
    msg = format_heti_stat(hetitippek)
    bot = Bot(token=BOT_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
    print(msg)

    # Hét után ürítsd a heti fájlt:
    with open(HETI_FILE, "w", encoding="utf8") as f:
        json.dump([], f)

if __name__ == '__main__':
    main()
