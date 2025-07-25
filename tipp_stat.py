import requests
import datetime
import pytz
import json
import os
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '-1002892598463'
API_KEY = 'ce7d900780d35895f214463b4ce49a49'

HEADERS = {'x-apisports-key': API_KEY}
TIPPEK_NAPLO = 'tippek_naplo.json'
HETI_FILE = "heti_tippek.json"

def get_fixture_result(fixture_id):
    url = f"https://v3.football.api-sports.io/fixtures?id={fixture_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200 and res.json()['response']:
        fx = res.json()['response'][0]
        g1 = fx['goals']['home']
        g2 = fx['goals']['away']
        return g1, g2
    return None, None

def check_tipp(tipp, eredmeny):
    g1, g2 = eredmeny
    if g1 is None or g2 is None:
        return None  # Eredmény nincs
    if tipp['bet'] == "Hazai győzelem":
        return g1 > g2
    if tipp['bet'] == "Vendég győzelem":
        return g2 > g1
    if tipp['bet'] == "Döntetlen":
        return g1 == g2
    if tipp['bet'] == "Mindkét csapat szerez gólt":
        return g1 > 0 and g2 > 0
    if tipp['bet'] == "Több mint 2.5 gól":
        return g1 + g2 > 2.5
    if tipp['bet'] == "Kevesebb mint 2.5 gól":
        return g1 + g2 < 2.5
    return None

def format_stat_message(tippek, stat, biztos_lista, kock_lista):
    today = datetime.datetime.now().strftime('%Y.%m.%d')
    found = stat['talalt']
    fail = stat['hibas']
    arany = f"{(found / (found+fail))*100:.1f}%" if (found+fail) else "0%"
    msg = f"📈 Napi Tippmix statisztika – {today}\n\n"
    msg += f"Tippek száma: {found+fail}\n"
    msg += f"Talált: {found}\n"
    msg += f"Hibás: {fail}\n"
    msg += f"Találati arány: {arany}\n"
    msg += f"Összesített szorzó: {stat['ossz_odds']:.2f}\n"
    msg += f"Nyerhető 1000 Ft tétre: {stat['nyeremeny']:.0f} Ft\n\n"

    # Biztos tippek részletes
    msg += f"✅ Biztos tippek ({len(biztos_lista)}):\n"
    if biztos_lista:
        talalt = sum(1 for t in biztos_lista if t['talalt'])
        hibas = len(biztos_lista) - talalt
        arany = f"{(talalt/len(biztos_lista))*100:.1f}%" if biztos_lista else "0%"
        ossz_odds = 1.0
        for t in biztos_lista:
            if t['talalt']:
                try: ossz_odds *= float(t['odd'])
                except: pass
        nyer = int(1000 * ossz_odds) if talalt else 0
        msg += f"  Talált: {talalt}, Hibás: {hibas}, Találati arány: {arany}\n"
        msg += f"  Szorzó: {ossz_odds:.2f}, Nyeremény: {nyer} Ft\n"
        for t in biztos_lista:
            e = "✅" if t['talalt'] else "❌"
            msg += f"   {e} {t['home']} - {t['away']} | {t['bet']} | Szorzó: {t['odd']} | Eredmény: {t['g1']}-{t['g2']}\n"
    else:
        msg += "  Nincs biztos tipp a mai napon.\n"

    msg += f"\n⚠️ Kockázatos tippek ({len(kock_lista)}):\n"
    if kock_lista:
        talalt = sum(1 for t in kock_lista if t['talalt'])
        hibas = len(kock_lista) - talalt
        arany = f"{(talalt/len(kock_lista))*100:.1f}%" if kock_lista else "0%"
        ossz_odds = 1.0
        for t in kock_lista:
            if t['talalt']:
                try: ossz_odds *= float(t['odd'])
                except: pass
        nyer = int(1000 * ossz_odds) if talalt else 0
        msg += f"  Talált: {talalt}, Hibás: {hibas}, Találati arány: {arany}\n"
        msg += f"  Szorzó: {ossz_odds:.2f}, Nyeremény: {nyer} Ft\n"
        for t in kock_lista:
            e = "✅" if t['talalt'] else "❌"
            msg += f"   {e} {t['home']} - {t['away']} | {t['bet']} | Szorzó: {t['odd']} | Eredmény: {t['g1']}-{t['g2']}\n"
    else:
        msg += "  Nincs kockázatos tipp a mai napon.\n"

    return msg

def naplozz_heti_tippek(tippek):
    hetifile = HETI_FILE
    if os.path.exists(hetifile):
        with open(hetifile, "r", encoding="utf8") as f:
            hetitippek = json.load(f)
    else:
        hetitippek = []
    hetitippek += tippek
    with open(hetifile, "w", encoding="utf8") as f:
        json.dump(hetitippek, f, ensure_ascii=False, indent=2)

def main():
    # 1. Olvasd be a naplózott tippeket
    try:
        with open(TIPPEK_NAPLO, 'r', encoding='utf8') as f:
            tippek = json.load(f)
    except:
        tippek = []

    stat = {'talalt': 0, 'hibas': 0, 'ossz_odds': 1.0, 'nyeremeny': 1000}
    biztos_lista = []
    kock_lista = []

    for t in tippek:
        g1, g2 = get_fixture_result(t['fixture_id'])
        t['g1'] = g1
        t['g2'] = g2
        ered = check_tipp(t, (g1, g2))
        t['talalt'] = ered is True
        if t['kat'] == "Biztos tipp":
            biztos_lista.append(t)
        else:
            kock_lista.append(t)
        if ered is True:
            stat['talalt'] += 1
            try:
                stat['ossz_odds'] *= float(t['odd'])
            except:
                pass
        elif ered is False:
            stat['hibas'] += 1
    if stat['talalt'] > 0:
        stat['nyeremeny'] = 1000 * stat['ossz_odds']
    else:
        stat['nyeremeny'] = 0

    msg = format_stat_message(tippek, stat, biztos_lista, kock_lista)

    # 2. Küldd el Telegramra
    bot = Bot(token=BOT_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
    print(msg)

    # 3. Napi naplózás heti fájlba (heti_tippek.json)
    naplozz_heti_tippek(tippek)

if __name__ == '__main__':
    main()
