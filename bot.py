import requests
import datetime
import pytz
import asyncio
from dateutil import parser
from telegram import Bot
from telegram.constants import ParseMode
import unidecode
import difflib

# IDE Tedd a SAJÁT KULCSOKAT!
BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '-1002892598463'
API_KEY = 'ce7d900780d35895f214463b4ce49a49'

HEADERS = {'x-apisports-key': API_KEY}

TOP_LEAGUE_IDS = [
    39,   # Premier League
    78,   # Bundesliga
    140,  # La Liga
    135,  # Serie A
    61,   # Ligue 1
    266,  # NB I (Magyarország)
    40,   # Championship
    79,   # 2. Bundesliga
    141,  # La Liga 2
    136,  # Serie B
    62,   # Ligue 2
    88,   # Eredivisie
    94,   # Primeira Liga
    144,  # Jupiler Pro League
    203,  # Süper Lig
    179,  # Premiership (Skócia)
    218,  # Bundesliga (Ausztria)
    207,  # Super League (Svájc)
    106,  # Ekstraklasa (Lengyelország)
    197,  # Super League 1 (Görögország)
    2,    # Champions League
    3,    # Europa League
    848   # Conference League
]

def get_today_fixtures():
    tz = pytz.timezone("Europe/Budapest")
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    fixtures = []
    for league_id in TOP_LEAGUE_IDS:
        url = f"https://v3.football.api-sports.io/fixtures?date={today}&league={league_id}&season=2024"
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            fixtures += resp.json().get('response', [])
    return fixtures

def get_form(team_id):
    url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=5"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return []
    return res.json()['response']

def get_odds(fixture_id):
    url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200 and res.json()['response']:
        try:
            bets = res.json()['response'][0]['bookmakers'][0]['bets']
            for bet in bets:
                if bet['name'] in ['Match Winner', '1X2', 'Win/Draw/Lose']:
                    odds_dict = {}
                    for v in bet['values']:
                        if v['value'] in ['Home', '1']:
                            odds_dict['home'] = v['odd']
                        elif v['value'] in ['Away', '2']:
                            odds_dict['away'] = v['odd']
                        elif v['value'] in ['Draw', 'X']:
                            odds_dict['draw'] = v['odd']
                    return odds_dict
        except Exception:
            return None
    return None

def analyze_fixture(fx):
    home = fx['teams']['home']['name']
    away = fx['teams']['away']['name']
    league = fx['league']['name']
    country = fx['league']['country']
    start_time = parser.isoparse(fx['fixture']['date']).astimezone(pytz.timezone("Europe/Budapest")).strftime("%Y-%m-%d %H:%M")
    fixture_id = fx['fixture']['id']

    odds = get_odds(fixture_id)
    if not odds:
        return None

    # Elemzés: forma alapján tipp
    home_form = get_form(fx['teams']['home']['id'])
    away_form = get_form(fx['teams']['away']['id'])

    home_win = sum(1 for f in home_form if f["teams"]["home"]["id"] == fx['teams']['home']['id'] and f["goals"]["home"] is not None and f["goals"]["away"] is not None and f["goals"]["home"] > f["goals"]["away"])
    away_win = sum(1 for f in away_form if f["teams"]["away"]["id"] == fx['teams']['away']['id'] and f["goals"]["home"] is not None and f["goals"]["away"] is not None and f["goals"]["away"] > f["goals"]["home"])

    # Tippelési logika (bővíthető!): amelyik csapat jobban szerepel az utolsó 5 meccsen
    if home_win > away_win and float(odds['home']) >= 1.8:
        bet = "Hazai győzelem"
        odd = odds['home']
    elif away_win > home_win and float(odds['away']) >= 1.8:
        bet = "Vendég győzelem"
        odd = odds['away']
    else:
        # Ha nincs kiugró forma, a legmagasabb oddsot ajánlja
        best_key = max(odds, key=lambda k: float(odds[k]) if odds[k].replace('.', '', 1).isdigit() else 0)
        bet = {"home": "Hazai győzelem", "away": "Vendég győzelem", "draw": "Döntetlen"}[best_key]
        odd = odds[best_key]

    return {
        'home': home,
        'away': away,
        'league': league,
        'country': country,
        'start_time': start_time,
        'bet': bet,
        'odd': odd
    }

def select_best_tips(max_tips=3):
    fixtures = get_today_fixtures()
    tips = []
    for fx in fixtures:
        try:
            t = analyze_fixture(fx)
            if t and t['odd'] not in [None, '', 'n.a.']:
                tips.append(t)
            if len(tips) == max_tips:
                break
        except Exception:
            continue
    return tips

def format_message(tips):
    today = datetime.datetime.now().strftime('%Y.%m.%d')
    message = f"🔥 Mai Tippmix tippek – {today} 🔥\n"
    for t in tips:
        message += f"\n⚽️ {t['home']} - {t['away']} ({t['league']}, {t['country']})"
        message += f"\n🕒 Kezdés: {t['start_time']}"
        message += f"\n👉 Tipp: {t['bet']} | Szorzó: {t['odd']}\n"
    message += "\n📊 Tippmestertől, minden nap 11:00-kor!"
    return message

async def send_message(text):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.MARKDOWN)

async def main():
    tips = select_best_tips()
    if tips:
        msg = format_message(tips)
        await send_message(msg)
        print(msg)
    else:
        await send_message("⚠️ Ma nincs megfelelő topligás meccs vagy odds a kínálatban!")

if __name__ == '__main__':
    asyncio.run(main())
