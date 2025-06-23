import requests
import datetime
import random

# --- CONFIG --- #
BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '6908414952'
API_KEY = '402484016678a5bc1ccb125d96319634'

HEADERS = {
    'x-apisports-key': API_KEY
}

INTERESTING_LEAGUES = [
    "Allsvenskan", "Superettan", "Premier Division", "First Division", 
    "Veikkausliiga", "Eliteserien", "OBOS-ligaen"
]

def get_today_matches():
    today = datetime.date.today().strftime("%Y-%m-%d")
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
    today = datetime.date.today().strftime('%Y.%m.%d')
    message = f"🔥 Mai Tippmix tippek – {today} 🔥\n"
    for match, bet in tips:
        message += f"\n⚽ {match}\n👉 Tipp: {bet}"
    message += "\n\n📊 Tippmestertől, minden nap 11:00-kor!"
    return message

def send_message(text):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown'
    }
    requests.post(url, data=payload)

if __name__ == '__main__':
    tips = get_today_matches()
    if tips:
        msg = format_message(tips)
        send_message(msg)
