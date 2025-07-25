import requests
import datetime
import pytz
import json
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
CHAT_ID = 'YOUR_TELEGRAM_CHAT_ID'
API_KEY = 'YOUR_FOOTBALL_API_KEY'

HEADERS = {'x-apisports-key': API_KEY}
TIPPEK_NAPLO = 'tippek_naplo.json'

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

def format_stat_message(tippek, stat):
    today = datetime.datetime.now().strftime('%Y.%m.%d')
    msg = f"📈 Napi Tippmix statisztika – {today}\n\n"
    found = stat['talalt']
    fail = stat['hibas']
    arany = f"{(found / (found+fail))*100:.1f}%" if (found+fail) else "0%"
    msg += f"Tippek száma: {found+fail}\n"
    msg += f"Talált: {found}\n"
    msg += f"Hibás: {fail}\n"
    msg += f"Találati arány: {arany}\n"
    msg += f"Összesített szorzó: {stat['ossz_odds']:.2f}\n"
    msg += f"Nyerhető 1000 Ft tétre: {stat['nyeremeny']:.0f} Ft\n"
    msg += "\nTippenként:\n"
    for idx, t in enumerate(tippek, 1):
        ered = "✅" if t['talalt'] else "❌"
        msg += f"{ered} {t['home']} - {t['away']} | {t['bet']} | Szorzó: {t['odd']} | Eredmény: {t['g1']}-{t['g2']}\n"
    return msg

def main():
    # 1. Olvasd be a naplózott tippeket
    try:
        with open(TIPPEK_NAPLO, 'r', encoding='utf8') as f:
            tippek = json.load(f)
    except:
        tippek = []

    stat = {'talalt': 0, 'hibas': 0, 'ossz_odds': 1.0, 'nyeremeny': 1000}
    for t in tippek:
        g1, g2 = get_fixture_result(t['fixture_id'])
        t['g1'] = g1
        t['g2'] = g2
        ered = check_tipp(t, (g1, g2))
        t['talalt'] = ered is True
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

    msg = format_stat_message(tippek, stat)

    # 2. Küldd el Telegramra
    bot = Bot(token=BOT_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
    print(msg)

if __name__ == '__main__':
    main()
