import requests
import datetime
import random
import pytz
from telegram import Bot
from telegram.constants import ParseMode
import asyncio

# --- CONFIG --- #
BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '1002892598463'
API_KEY = 'ce7d900780d35895f214463b4ce49a49'

HEADERS = {
    'x-apisports-key': API_KEY
}

INTERESTING_LEAGUES = [
    "Allsvenskan", "Superettan", "Premier Division", "First Division", 
    "Veikkausliiga", "Eliteserien", "OBOS-ligaen", "Ykkosliiga"
]

def get_today_matches():
    tz = pytz.timezone("Europe/Budapest")
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return []

    matches = []
    for item in response.json().get("response", []):
        league = item["league"]["name"]
        if league not in INTERESTING_LEAGUES:
            continue
        home = item["teams"]["home"]["name"]
        away = item["teams"]["away"]["name"]
        match = f"{home} - {away}"
        tip = random.choice(["Hazai győzelem", "Vendég győzelem", "Mindkét csapat szerez gólt"])
        matches.append((match, tip))
    return matches[:3]

def format_message(tips):
    tz = pytz.timezone("Europe/Budapest")
    today = datetime.datetime.now(tz).strftime('%Y.%m.%d')
    message = f"🔥 Mai Tippmix tippek – {today} 🔥\n"
    for match, bet in tips:
        message += f"\n⚽ {match}\n👉 Tipp: {bet}"
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
