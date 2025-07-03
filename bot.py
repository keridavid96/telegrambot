import requests
import datetime
import pytz
from telegram import Bot
from telegram.constants import ParseMode
import asyncio

BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '-1002892598463'
API_KEY = 'ce7d900780d35895f214463b4ce49a49'

HEADERS = {'x-apisports-key': API_KEY}

def recent_results(team_id, n=5):
    # Lekéri az utolsó n meccset, visszaadja a nyeréseket/gólokat
    url = f'https://v3.football.api-sports.io/fixtures?team={team_id}&last={n}'
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return []
    return res.json()['response']

def analyze_fixture(fixture):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    home_id = fixture["teams"]["home"]["id"]
    away_id = fixture["teams"]["away"]["id"]
    fixture_id = fixture["fixture"]["id"]
    league_name = fixture["league"]["name"]

    # Adatokat kérünk a csapatokról
    home_results = recent_results(home_id)
    away_results = recent_results(away_id)
    if len(home_results) < 3 or len(away_results) < 3:
        return None  # túl kevés adat

    # Hazai győzelem analízis
    home_wins = sum(1 for f in home_results if f["teams"]["home"]["id"] == home_id and f["goals"]["home"] > f["goals"]["away"])
    away_losses = sum(1 for f in away_results if f["teams"]["away"]["id"] == away_id and f["goals"]["away"] < f["goals"]["home"])
    if home_wins >= 3 and away_losses >= 3:
        bet, odds_key, market = "Hazai győzelem", "Home", "Match Winner"
    # Vendég győzelem analízis
    elif sum(1 for f in away_results if f["teams"]["away"]["id"] == away_id and f["goals"]["away"] > f["goals"]["home"]) >= 3 and \
         sum(1 for f in home_results if f["teams"]["home"]["id"] == home_id and f["goals"]["home"] < f["goals"]["away"]) >= 3:
        bet, odds_key, market = "Vendég győzelem", "Away", "Match Winner"
    # Mindkét csapat gól elemzés
    elif sum(1 for f in home_results if f["goals"]["home"] > 0 and f["goals"]["away"] > 0) >= 3 and \
         sum(1 for f in away_results if f["goals"]["home"] > 0 and f["goals"]["away"] > 0) >= 3:
        bet, odds_key, market = "Mindkét csapat szerez gólt", "Yes", "Both Teams To Score"
    else:
        return None  # Nincs elég minta, vagy nincs erős trend

    # Odds lekérdezés
    odds_url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
    odds_res = requests.get(odds_url, headers=HEADERS)
    odds_value = "n.a."
    if odds_res.status_code == 200:
        try:
            odds_data = odds_res.json()
            for bookmaker in odds_data['response'][0]['bookmakers']:
                for betm in bookmaker['bets']:
                    if betm['name'] == market:
                        for v in betm['values']:
                            if v['value'] == odds_key:
                                odds_value = v['odd']
                                raise StopIteration
        except Exception:
            pass

    return (home, away, bet, odds_value, league_name)

def get_today_tips(max_tips=3):
    tz = pytz.timezone("Europe/Budapest")
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return []
    tips = []
    for fixture in res.json().get("response", []):
        tipp = analyze_fixture(fixture)
        if tipp:
            tips.append(tipp)
            if len(tips) == max_tips:
                break
    return tips

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
    tips = get_today_tips()
    if tips:
        msg = format_message(tips)
        await send_message(msg)
    else:
        await send_message("⚠️ Ma nincs megfelelő meccs elemzés vagy odds!")

if __name__ == '__main__':
    asyncio.run(main())
