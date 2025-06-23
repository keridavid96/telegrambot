import requests
import datetime
import os
import pytz
import telegram

# Konfiguráció
API_TOKEN = "402484016678a5bc1ccb125d96319634"
TELEGRAM_TOKEN = "8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk"
CHAT_ID = "1002892598463"

# Cél bajnokságok
LEAGUE_IDS = [106, 104, 87, 88, 39, 103, 62]  # példa: Írország, Svédország, Norvégia stb.

# Dátumkezelés (ma)
tz = pytz.timezone('Europe/Budapest')
today = datetime.datetime.now(tz).strftime("%Y-%m-%d")

# Küldésre készülő tippek
tips = []

for league_id in LEAGUE_IDS:
    url = f"https://v3.football.api-sports.io/fixtures?date={today}&league={league_id}&season=2024"
    headers = {
        "x-apisports-key": API_TOKEN
    }
    res = requests.get(url, headers=headers)

    if res.status_code == 200:
        data = res.json()
        for fixture in data['response']:
            home = fixture['teams']['home']['name']
            away = fixture['teams']['away']['name']
            fixture_id = fixture['fixture']['id']

            # Fogadási odds lekérés (1X2)
            odds_url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}&bookmaker=6"
            odds_res = requests.get(odds_url, headers=headers)

            if odds_res.status_code == 200:
                odds_data = odds_res.json()
                try:
                    # Kiválasztjuk az 1X2 piacot (ha van)
                    bets = odds_data['response'][0]['bookmakers'][0]['bets']
                    for bet in bets:
                        if bet['name'] == "Match Winner":
                            values = bet['values']
                            for v in values:
                                if v['value'] == "Away" and float(v['odd']) <= 1.80:
                                    tips.append(f"{home} - {away}: Vendég ({v['odd']})")
                                elif v['value'] == "Home" and float(v['odd']) <= 1.80:
                                    tips.append(f"{home} - {away}: Hazai ({v['odd']})")
                except Exception:
                    pass  # ha nincs odds adat, kihagyjuk

# Telegram küldés
if tips:
    message = f"🎯 **Mai tippek** – {today}\n\n"
    for t in tips:
        message += f"• {t}\n"

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=message, parse_mode=telegram.ParseMode.MARKDOWN)
else:
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text="⚠️ Ma nem található megfelelő tipp.", parse_mode=telegram.ParseMode.MARKDOWN)