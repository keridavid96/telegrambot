import requests
import datetime
import random
import pytz
from telegram import Bot
from telegram.constants import ParseMode
import asyncio

# --- CONFIG --- #
BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '-1002892598463'
API_KEY = 'ce7d900780d35895f214463b4ce49a49'

HEADERS = {
    'x-apisports-key': API_KEY
}

def get_today_matches():
    tz = pytz.timezone("Europe/Budapest")
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return []

    matches = []
    for item in response.json().get("response", []):
        home = item["teams"]["home"]["name"]
        away = item["teams"]["away"]["name"]
        fixture_id = item["fixture"]["id"]
        league_name = item["league"]["name"]

        # Random tipp-típus (ez helyettesíthető elemzéssel is!)
        tip_type = random.choice([
            ("Hazai győzelem", "Home", "Match Winner"),
            ("Vendég győzelem", "Away", "Match Winner"),
            ("Mindkét csapat szerez gólt", "Yes", "Both Teams To Score")
        ])
        tip_name, odds_key, odds_market = tip_type

        # Odds lekérés
        odds_url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
        odds_res = requests.get(odds_url, headers=HEADERS)
        odds_value = "n.a."
        if odds_res.status_code == 200:
            try:
                odds_data = odds_res.json()
                for bookmaker in odds_data['response'][0]['bookmakers']:
                    for bet in bookmaker['bets']:
                        if bet['name'] == odds_market:
                            for v in bet['values']:
                                if v['value'] == odds_key:
                                    odds_value = v['odd']
                                    raise StopIteration
            except Exception:
                pass

        matches.append((home, away, tip_name, odds_value, league_name))
        if len(matches) == 3:
            break
    return matches

def format_message(tips):
    tz = pytz.timezone("Europe/Budapest")
    today = datetime.datetime.now(tz).strftime('%Y.%m.%d')
    message = f"🔥 Mai Tippmix tippek – {today} 🔥\n"
    for home, away, bet, odd, league in tips:
        message += f"\n⚽️ {home} - {away} ({league})\n👉 Tipp: {bet} | Szorzó: {odd}"
    message += "\n\n📊 Tippmestertől, minden nap 11:00-kor!"
    return message

async def send_message(text):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.MARKDOWN)

async def main():
    tips = get_today_matches()
    if tips:
        msg = format_message(tips)
        await send_message(msg)

if __name__ == '__main__':
    asyncio.run(main())
