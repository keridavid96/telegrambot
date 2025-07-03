import requests
from bs4 import BeautifulSoup
import datetime
import pytz
from telegram import Bot
from telegram.constants import ParseMode
import asyncio
from dateutil import parser

BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '6908414952'
API_KEY = '402484016678a5bc1ccb125d96319634'

HEADERS = {'x-apisports-key': API_KEY}

def get_eredmenyek_matches():
    url = "https://www.eredmenyek.com/foci/"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    matches = []
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'html.parser')
        for row in soup.select('.event__match--scheduled'):
            try:
                home = row.select_one('.event__participant--home').text.strip()
                away = row.select_one('.event__participant--away').text.strip()
                start_time = row.select_one('.event__time').text.strip()
                # Mostani nap, vagy ha éjfél utánra esik, akkor másnap!
                today = datetime.datetime.now()
                match_dt = datetime.datetime.strptime(f"{today.year}.{today.month}.{today.day} {start_time}", "%Y.%m.%d %H:%M")
                if match_dt < today - datetime.timedelta(hours=6):
                    match_dt += datetime.timedelta(days=1)
                # 1X2 szorzók
                odds_1 = row.select_one('.event__odd--1')
                odds_x = row.select_one('.event__odd--x')
                odds_2 = row.select_one('.event__odd--2')
                if odds_1 and odds_x and odds_2:
                    matches.append({
                        'home': home,
                        'away': away,
                        'start_time': match_dt.strftime('%Y-%m-%dT%H:%M'),
                        'odds': {
                            'home': odds_1.text.strip().replace(',', '.'),
                            'draw': odds_x.text.strip().replace(',', '.'),
                            'away': odds_2.text.strip().replace(',', '.')
                        }
                    })
            except Exception:
                continue
    return matches

def analyze_fixture(fixture, eredmenyek_matches):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    start_utc = fixture["fixture"]["date"]
    tz = pytz.timezone("Europe/Budapest")
    start_dt = parser.isoparse(start_utc).astimezone(tz)
    start_time_str = start_dt.replace(second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M')

    # Párosítás (név/idő rugalmas egyezés)
    match = None
    for m in eredmenyek_matches:
        if (home.lower() in m['home'].lower() or m['home'].lower() in home.lower()) and \
           (away.lower() in m['away'].lower() or m['away'].lower() in away.lower()):
            scraped_time = datetime.datetime.strptime(m['start_time'], '%Y-%m-%dT%H:%M')
            delta = abs((start_dt - scraped_time).total_seconds())
            if delta < 1800:
                match = m
                break
    if not match:
        return None

    odds = match['odds']
    # Egyszerű logika: ha hazai odds >=2, azt tippeli, különben vendég, különben döntetlen
    if float(odds['home']) >= 2.0:
        bet = "Hazai győzelem"
        odd = odds['home']
    elif float(odds['away']) >= 2.0:
        bet = "Vendég győzelem"
        odd = odds['away']
    else:
        bet = "Döntetlen"
        odd = odds['draw']

    league_name = fixture["league"]["name"]
    return (home, away, bet, odd, league_name, start_time_str)

def get_today_tips(max_tips=3):
    eredmenyek_matches = get_eredmenyek_matches()
    tz = pytz.timezone("Europe/Budapest")
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return []
    tips = []
    for fixture in res.json().get("response", []):
        tipp = analyze_fixture(fixture, eredmenyek_matches)
        if tipp:
            tips.append(tipp)
            if len(tips) == max_tips:
                break
    return tips

def format_message(tips):
    today = datetime.datetime.now().strftime('%Y.%m.%d')
    message = f"🔥 Mai Tippmix tippek – {today} 🔥\n"
    for home, away, bet, odd, league, start_time in tips:
        message += f"\n⚽️ {home} - {away} ({league})\n🕒 Kezdés: {start_time}\n👉 Tipp: {bet} | Szorzó: {odd}"
    message += "\n\n📊 Tippmestertől, minden nap 11:00-kor!"
    return message

async def send_message(text):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.MARKDOWN)

async def main():
    tips = get_today_tips()
    if tips:
        msg = format_message(tips)
        await send_message(msg)
    else:
        await send_message("⚠️ Ma nincs megfelelő meccs vagy odds az eredmenyek.com-on!")

if __name__ == '__main__':
    asyncio.run(main())
