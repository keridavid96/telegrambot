import requests
import datetime
import pytz
import asyncio
import json
from dateutil import parser
from telegram import Bot
from telegram.constants import ParseMode

# Állítsd be az adataid!
BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '-1002892598463'
API_KEY = 'ce7d900780d35895f214463b4ce49a49'

HEADERS = {'x-apisports-key': API_KEY}

TIPPEK_NAPLO = 'tippek_naplo.json'

TOP_LEAGUE_IDS = [
    39, 78, 140, 135, 61, 266, 40, 79, 141, 136, 62, 88,
    94, 144, 203, 179, 218, 207, 106, 197, 2, 3, 848
]

def get_current_season(league_id):
    url = f"https://v3.football.api-sports.io/leagues?id={league_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return None
    for l in res.json()["response"]:
        if l["league"]["id"] == league_id:
            for season in l["seasons"]:
                if season["current"]:
                    return season["year"]
    return None

def get_today_fixtures():
    tz = pytz.timezone("Europe/Budapest")
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d")
    fixtures = []
    for league_id in TOP_LEAGUE_IDS:
        season = get_current_season(league_id)
        if not season:
            continue
        url = f"https://v3.football.api-sports.io/fixtures?date={today}&league={league_id}&season={season}"
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

def get_standings(league_id, season):
    url = f"https://v3.football.api-sports.io/standings?league={league_id}&season={season}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return None
    data = res.json()["response"]
    if not data: return None
    return data[0]["league"]["standings"][0]

def get_h2h(home_id, away_id):
    url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={home_id}-{away_id}&last=5"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return []
    return res.json()['response']

def get_odds(fixture_id):
    url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200 and res.json()['response']:
        try:
            bookmakers = res.json()['response'][0]['bookmakers']
            if not bookmakers: return None
            odds = {'1X2': {}, 'GG': {}, 'OU': {}}
            for bet in bookmakers[0]['bets']:
                if bet['name'] in ['Match Winner', '1X2', 'Win/Draw/Lose']:
                    for v in bet['values']:
                        if v['value'] in ['Home', '1']:
                            odds['1X2']['home'] = v['odd']
                        elif v['value'] in ['Away', '2']:
                            odds['1X2']['away'] = v['odd']
                        elif v['value'] in ['Draw', 'X']:
                            odds['1X2']['draw'] = v['odd']
                if bet['name'] == 'Both Teams to Score':
                    for v in bet['values']:
                        if v['value'] == 'Yes':
                            odds['GG']['yes'] = v['odd']
                        elif v['value'] == 'No':
                            odds['GG']['no'] = v['odd']
                if bet['name'] == 'Over/Under 2.5':
                    for v in bet['values']:
                        if v['value'] == 'Over 2.5':
                            odds['OU']['over'] = v['odd']
                        elif v['value'] == 'Under 2.5':
                            odds['OU']['under'] = v['odd']
            return odds
        except Exception as e:
            return None
    return None

def tipp_kategoria(home_stats, away_stats, odds, bettype, odd):
    kategoria = "Kockázatos tipp"
    indok = []

    try:
        # -- Eredmény tippek
        if bettype in ["Hazai győzelem", "Vendég győzelem"]:
            # Lazább: legalább 2 forma, helyezés különbség, odds max 2.30
            if ((bettype == "Hazai győzelem" and home_stats['forma'] >= 2 and home_stats['helyezes'] < away_stats['helyezes'])
                or (bettype == "Vendég győzelem" and away_stats['forma'] >= 2 and away_stats['helyezes'] < home_stats['helyezes'])):
                if float(odd) < 2.30:
                    kategoria = "Biztos tipp"
                    indok.append("Elfogadható forma és tabellahely, kedvező szorzó")
            if float(odd) > 2.4:
                indok.append("Magas szorzó")
        elif bettype == "Döntetlen":
            if float(odd) < 3.5:
                kategoria = "Biztos tipp"
                indok.append("Alacsonyabb döntetlen szorzó")
            else:
                indok.append("Nagyon magas szorzó")
        else:
            # -- Speciális: GG, Over/Under
            if float(odd) < 1.90:
                kategoria = "Biztos tipp"
                indok.append("Stabil statisztika, kedvező odds")
            elif float(odd) > 2.25:
                indok.append("Magas szorzó")
    except:
        pass

    return kategoria, ", ".join(indok) if indok else None

    except:
        pass
    return kategoria, ", ".join(indok) if indok else None

def analyze_fixture(fx):
    #--- Alap adatok ---
    home = fx['teams']['home']['name']
    away = fx['teams']['away']['name']
    home_id = fx['teams']['home']['id']
    away_id = fx['teams']['away']['id']
    league = fx['league']['name']
    league_id = fx['league']['id']
    country = fx['league']['country']
    season = fx['league']['season']
    start_time = parser.isoparse(fx['fixture']['date']).astimezone(pytz.timezone("Europe/Budapest")).strftime("%Y-%m-%d %H:%M")
    fixture_id = fx['fixture']['id']

    odds = get_odds(fixture_id)
    if not odds:
        return []

    home_forma = get_form(home_id)
    away_forma = get_form(away_id)
    home_win = sum(1 for f in home_forma if f["teams"]["home"]["id"] == home_id and f["goals"]["home"] is not None and f["goals"]["away"] is not None and f["goals"]["home"] > f["goals"]["away"])
    away_win = sum(1 for f in away_forma if f["teams"]["away"]["id"] == away_id and f["goals"]["home"] is not None and f["goals"]["away"] is not None and f["goals"]["away"] > f["goals"]["home"])
    standings = get_standings(league_id, season)
    home_pos = None
    away_pos = None
    if standings:
        for t in standings:
            if t["team"]["id"] == home_id:
                home_pos = t["rank"]
            if t["team"]["id"] == away_id:
                away_pos = t["rank"]
    home_stats = {"forma": home_win, "helyezes": home_pos if home_pos else 99}
    away_stats = {"forma": away_win, "helyezes": away_pos if away_pos else 99}

    tipp_list = []

    # 1. Eredmény tipp: Hazai/vendég/döntetlen
    if all(k in odds['1X2'] for k in ('home','away','draw')):
        if home_win >= away_win and (home_pos or 99) < (away_pos or 99):
            bet = "Hazai győzelem"
            odd = odds['1X2']['home']
        elif away_win > home_win and (away_pos or 99) < (home_pos or 99):
            bet = "Vendég győzelem"
            odd = odds['1X2']['away']
        else:
            bet = "Döntetlen"
            odd = odds['1X2']['draw']
        kat, indok = tipp_kategoria(home_stats, away_stats, odds['1X2'], bet, odd)
        tipp_list.append({
            'home': home, 'away': away, 'league': league, 'country': country,
            'start_time': start_time, 'bet': bet, 'odd': odd, 'kat': kat, 'indok': indok, 'fixture_id': fixture_id
        })

    # 2. Mindkét csapat szerez gólt
    if 'yes' in odds['GG']:
        gg_bet = "Mindkét csapat szerez gólt"
        odd = odds['GG']['yes']
        kat, indok = tipp_kategoria(home_stats, away_stats, odds['GG'], gg_bet, odd)
        tipp_list.append({
            'home': home, 'away': away, 'league': league, 'country': country,
            'start_time': start_time, 'bet': gg_bet, 'odd': odd, 'kat': kat, 'indok': indok, 'fixture_id': fixture_id
        })
    # 3. Gól over/under
    if 'over' in odds['OU']:
        ou_bet = "Több mint 2.5 gól"
        odd = odds['OU']['over']
        kat, indok = tipp_kategoria(home_stats, away_stats, odds['OU'], ou_bet, odd)
        tipp_list.append({
            'home': home, 'away': away, 'league': league, 'country': country,
            'start_time': start_time, 'bet': ou_bet, 'odd': odd, 'kat': kat, 'indok': indok, 'fixture_id': fixture_id
        })
    if 'under' in odds['OU']:
        ou_bet = "Kevesebb mint 2.5 gól"
        odd = odds['OU']['under']
        kat, indok = tipp_kategoria(home_stats, away_stats, odds['OU'], ou_bet, odd)
        tipp_list.append({
            'home': home, 'away': away, 'league': league, 'country': country,
            'start_time': start_time, 'bet': ou_bet, 'odd': odd, 'kat': kat, 'indok': indok, 'fixture_id': fixture_id
        })
    return tipp_list

def select_best_tips(n=6, eredmeny_max=3, spec_max=3):
    fixtures = get_today_fixtures()
    eredmeny_tippek = []
    spec_tippek = []
    extra_tippek = []

    for fx in fixtures:
        try:
            tippek = analyze_fixture(fx)
            if tippek:
                for t in tippek:
                    if t['bet'] in ["Hazai győzelem", "Vendég győzelem", "Döntetlen"]:
                        if len(eredmeny_tippek) < eredmeny_max:
                            eredmeny_tippek.append(t)
                        else:
                            extra_tippek.append(t)
                    elif t['bet'] in ["Mindkét csapat szerez gólt", "Több mint 2.5 gól", "Kevesebb mint 2.5 gól"]:
                        if len(spec_tippek) < spec_max:
                            spec_tippek.append(t)
                        else:
                            extra_tippek.append(t)
        except Exception as e:
            continue

        if len(eredmeny_tippek) + len(spec_tippek) >= n:
            break

    # Pótlás: ha nincs elég speciális, töltse fel eredmény tippekkel, vagy fordítva
    while len(eredmeny_tippek) + len(spec_tippek) < n and extra_tippek:
        t = extra_tippek.pop(0)
        if t['bet'] in ["Hazai győzelem", "Vendég győzelem", "Döntetlen"]:
            eredmeny_tippek.append(t)
        else:
            spec_tippek.append(t)

    # Végső lista pontosan 6 tippel
    final_tippek = eredmeny_tippek + spec_tippek
    final_tippek = final_tippek[:n]

    # Napló statisztikához
    with open(TIPPEK_NAPLO, 'w', encoding='utf8') as f:
        json.dump(final_tippek, f, ensure_ascii=False, indent=2)

    return final_tippek

def format_message(tippek):
    today = datetime.datetime.now().strftime('%Y.%m.%d')
    message = f"🔥 Mai Tippmix tippek – {today} 🔥\n"
    for t in tippek:
        message += f"\n⚽️ {t['home']} - {t['away']} ({t['league']}, {t['country']})"
        message += f"\n🕒 Kezdés: {t['start_time']}"
        message += f"\n👉 Tipp: {t['bet']} | Szorzó: {t['odd']}"
        message += f"\n📊 Kategória: {t['kat']}"
        if t['indok']: message += f" ({t['indok']})"
        message += "\n"
    message += "\n📊 Tippmestertől, minden nap 11:00-kor!"
    return message

async def send_message(text):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.MARKDOWN)

async def main():
    tippek = select_best_tips(n=6)
    if tippek:
        msg = format_message(tippek)
        await send_message(msg)
        print(msg)
    else:
        await send_message("⚠️ Ma nincs megfelelő topligás meccs vagy odds a kínálatban!")
        print("⚠️ Ma nincs megfelelő topligás meccs vagy odds a kínálatban!")

if __name__ == '__main__':
    asyncio.run(main())
