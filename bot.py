import requests
import datetime
import pytz
import asyncio
import json
from dateutil import parser
from telegram import Bot
from telegram.constants import ParseMode

# --- KONFIG ---
BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '-1002892598463'
API_KEY = 'ce7d900780d35895f214463b4ce49a49'

HEADERS = {'x-apisports-key': API_KEY}
TIPPEK_NAPLO = 'tippek_naplo.json'

# Topligák + európai kupák (jó eséllyel Tippmixpro-n is vannak)
TOP_LEAGUE_IDS = [
    39, 78, 140, 135, 61, 266, 40, 79, 141, 136, 62, 88,
    94, 144, 203, 179, 218, 207, 106, 197, 2, 3, 848
]

# Duplázó cél intervallum
TARGET_MIN_ODDS = 2.0
TARGET_MAX_ODDS = 2.6

# --- API segédek ---

def get_current_season(league_id):
    url = f"https://v3.football.api-sports.io/leagues?id={league_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return None
    for l in res.json().get("response", []):
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
    return res.json().get('response', [])

def get_standings(league_id, season):
    url = f"https://v3.football.api-sports.io/standings?league={league_id}&season={season}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return None
    data = res.json().get("response", [])
    if not data: return None
    return data[0]["league"]["standings"][0]

def get_h2h(home_id, away_id):
    url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={home_id}-{away_id}&last=5"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200: return []
    return res.json().get('response', [])

def get_odds(fixture_id):
    url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200 and res.json().get('response'):
        try:
            bookmakers = res.json()['response'][0]['bookmakers']
            if not bookmakers: return None
            # vegyük az első bukit konzisztensen
            odds = {'1X2': {}, 'GG': {}, 'OU': {}}
            for bet in bookmakers[0]['bets']:
                name = bet.get('name')
                if name in ['Match Winner', '1X2', 'Win/Draw/Lose']:
                    for v in bet['values']:
                        if v['value'] in ['Home', '1']:
                            odds['1X2']['home'] = v['odd']
                        elif v['value'] in ['Away', '2']:
                            odds['1X2']['away'] = v['odd']
                        elif v['value'] in ['Draw', 'X']:
                            odds['1X2']['draw'] = v['odd']
                if name == 'Both Teams to Score':
                    for v in bet['values']:
                        if v['value'] == 'Yes':
                            odds['GG']['yes'] = v['odd']
                        elif v['value'] == 'No':
                            odds['GG']['no'] = v['odd']
                if name == 'Over/Under 2.5':
                    for v in bet['values']:
                        if v['value'] == 'Over 2.5':
                            odds['OU']['over'] = v['odd']
                        elif v['value'] == 'Under 2.5':
                            odds['OU']['under'] = v['odd']
            return odds
        except Exception:
            return None
    return None

# --- Kategorizálás (lazább "Biztos tipp" feltételekkel) ---

def tipp_kategoria(home_stats, away_stats, bettype, odd_str):
    kategoria = "Kockázatos tipp"
    indok = []
    try:
        odd = float(odd_str)
        if bettype in ["Hazai győzelem", "Vendég győzelem"]:
            # Legalább 2 nyert az utolsó 5-ből + jobb tabella + 2.30 alatti odds -> Biztos
            if bettype == "Hazai győzelem":
                if home_stats['forma'] >= 2 and home_stats['helyezes'] < away_stats['helyezes'] and odd < 2.30:
                    kategoria = "Biztos tipp"
                    indok.append("Forma + tabellaelőny + kedvező odds")
            else:
                if away_stats['forma'] >= 2 and away_stats['helyezes'] < home_stats['helyezes'] and odd < 2.30:
                    kategoria = "Biztos tipp"
                    indok.append("Forma + tabellaelőny + kedvező odds")
            if odd >= 2.40:
                indok.append("Magas szorzó")
        elif bettype == "Döntetlen":
            if odd < 3.50:
                kategoria = "Biztos tipp"
                indok.append("Relatíve alacsony döntetlen szorzó")
            else:
                indok.append("Nagyon magas szorzó")
        else:
            # Speciális piacok
            if odd < 1.90:
                kategoria = "Biztos tipp"
                indok.append("Stabil statisztika, kedvező odds")
            elif odd > 2.25:
                indok.append("Magas szorzó")
    except:
        pass
    return kategoria, (", ".join(indok) if indok else None)

# --- Egy meccs teljes elemzése -> javasolt tippek listája ---

def analyze_fixture(fx):
    home = fx['teams']['home']['name']
    away = fx['teams']['away']['name']
    home_id = fx['teams']['home']['id']
    away_id = fx['teams']['away']['id']
    league = fx['league']['name']
    league_id = fx['league']['id']
    country = fx['league']['country']
    season = fx['league']['season']
    start_time = parser.isoparse(fx['fixture']['date']).astimezone(
        pytz.timezone("Europe/Budapest")
    ).strftime("%Y-%m-%d %H:%M")
    fixture_id = fx['fixture']['id']

    odds = get_odds(fixture_id)
    if not odds:
        return []

    # formák
    home_forma = get_form(home_id)
    away_forma = get_form(away_id)
    home_win = sum(1 for f in home_forma if f["teams"]["home"]["id"] == home_id and f["goals"]["home"] is not None and f["goals"]["away"] is not None and f["goals"]["home"] > f["goals"]["away"])
    away_win = sum(1 for f in away_forma if f["teams"]["away"]["id"] == away_id and f["goals"]["home"] is not None and f["goals"]["away"] is not None and f["goals"]["away"] > f["goals"]["home"])

    # tabella
    standings = get_standings(league_id, season)
    home_pos = 99
    away_pos = 99
    if standings:
        for t in standings:
            if t["team"]["id"] == home_id:
                home_pos = t["rank"]
            if t["team"]["id"] == away_id:
                away_pos = t["rank"]

    home_stats = {"forma": home_win, "helyezes": home_pos}
    away_stats = {"forma": away_win, "helyezes": away_pos}

    tips = []

    # 1X2
    if all(k in odds['1X2'] for k in ('home', 'away', 'draw')):
        # egyszerű favorit logika
        if (home_win > away_win and home_pos < away_pos):
            bet, odd = "Hazai győzelem", odds['1X2']['home']
        elif (away_win > home_win and away_pos < home_pos):
            bet, odd = "Vendég győzelem", odds['1X2']['away']
        else:
            # kiegyenlített -> döntetlenre is rá lehet nézni
            bet, odd = "Döntetlen", odds['1X2']['draw']
        kat, indok = tipp_kategoria(home_stats, away_stats, bet, odd)
        tips.append({
            'fixture_id': fixture_id,
            'home': home, 'away': away,
            'league': league, 'country': country,
            'start_time': start_time,
            'bet': bet, 'odd': odd, 'kat': kat, 'indok': indok
        })

    # BTTS (GG)
    if 'yes' in odds['GG']:
        bet, odd = "Mindkét csapat szerez gólt", odds['GG']['yes']
        kat, indok = tipp_kategoria(home_stats, away_stats, bet, odd)
        tips.append({
            'fixture_id': fixture_id,
            'home': home, 'away': away,
            'league': league, 'country': country,
            'start_time': start_time,
            'bet': bet, 'odd': odd, 'kat': kat, 'indok': indok
        })

    # Over/Under 2.5
    if 'over' in odds['OU']:
        bet, odd = "Több mint 2.5 gól", odds['OU']['over']
        kat, indok = tipp_kategoria(home_stats, away_stats, bet, odd)
        tips.append({
            'fixture_id': fixture_id,
            'home': home, 'away': away,
            'league': league, 'country': country,
            'start_time': start_time,
            'bet': bet, 'odd': odd, 'kat': kat, 'indok': indok
        })
    if 'under' in odds['OU']:
        bet, odd = "Kevesebb mint 2.5 gól", odds['OU']['under']
        kat, indok = tipp_kategoria(home_stats, away_stats, bet, odd)
        tips.append({
            'fixture_id': fixture_id,
            'home': home, 'away': away,
            'league': league, 'country': country,
            'start_time': start_time,
            'bet': bet, 'odd': odd, 'kat': kat, 'indok': indok
        })

    return tips

# --- Választás duplázóhoz és kockázatos egyesekhez ---

def build_safe_acca(all_tips):
    """
    Biztosabb duplázó:
      - preferált: 'Biztos tipp'
      - odd per tipp ~ 1.35–1.85 (reálisan 1.45–1.80 a legjobb)
      - 2 vagy 3 esemény úgy, hogy össz-odds a TARGET_MIN_ODDS–TARGET_MAX_ODDS sávban legyen
    """
    # szűrés biztosnak jelöltekre és ésszerű odd tartományra
    candidates = []
    for t in all_tips:
        try:
            o = float(t['odd'])
            if t['kat'] == "Biztos tipp" and 1.35 <= o <= 1.95:
                candidates.append((abs(1.7 - o), t))  # 1.7 körül szeretjük
        except:
            continue
    # ha kevés a "Biztos tipp", engedjünk be néhány "Kockázatos tipp"-et alacsony odddal
    if len(candidates) < 3:
        for t in all_tips:
            try:
                o = float(t['odd'])
                if t['kat'] != "Biztos tipp" and 1.35 <= o <= 1.80:
                    candidates.append((abs(1.65 - o), t))
            except:
                continue
    # rendezzük 1.7 körüli preferenciával
    candidates.sort(key=lambda x: x[0])
    picks = [t for _, t in candidates][:6]  # vegyünk egy bővebb listát, amiből keresünk kombinációt

    # próbáljunk 2-es, majd 3-as kombinációt találni a cél sávra
    def prod(arr):
        p = 1.0
        for a in arr:
            try: p *= float(a['odd'])
            except: return 0.0
        return p

    # 2-es kombi
    best = None
    for i in range(len(picks)):
        for j in range(i+1, len(picks)):
            combo = [picks[i], picks[j]]
            val = prod(combo)
            if TARGET_MIN_ODDS <= val <= TARGET_MAX_ODDS:
                best = combo
                break
        if best: break

    # 3-as kombi, ha 2-es nem talált
    if not best:
        for i in range(len(picks)):
            for j in range(i+1, len(picks)):
                for k in range(j+1, len(picks)):
                    combo = [picks[i], picks[j], picks[k]]
                    val = prod(combo)
                    if TARGET_MIN_ODDS <= val <= TARGET_MAX_ODDS:
                        best = combo
                        break
                if best: break
            if best: break

    # ha még így sincs, válasszunk a legközelebbi 2-est
    if not best and len(picks) >= 2:
        best = [picks[0], picks[1]]

    return best or []

def build_risky_singles(all_tips, count=3):
    """
    Kockázatos egyesek:
      - preferált: 'Kockázatos tipp'
      - odd >= 2.30
      - ha nincs elég, engedjünk be 2.10+-t is
    """
    risky = []
    for t in all_tips:
        try:
            o = float(t['odd'])
            if t['kat'] == "Kockázatos tipp" and o >= 2.30:
                risky.append((o, t))
        except:
            continue
    # ha kevés
    if len(risky) < count:
        for t in all_tips:
            try:
                o = float(t['odd'])
                if t['kat'] == "Kockázatos tipp" and o >= 2.10:
                    risky.append((o, t))
            except:
                continue
    # rendezzük szorzó szerint csökkenőben (legizgalmasabb elöl)
    risky.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in risky[:count]]

# --- Fő kiválasztó: begyűjti az összes jelölt tippet, és két csomagot készít ---

def select_daily_bundles():
    fixtures = get_today_fixtures()
    all_tips = []
    for fx in fixtures:
        try:
            tips = analyze_fixture(fx)
            all_tips.extend(tips)
        except Exception:
            continue

    # duplázó pakk
    safe_acca = build_safe_acca(all_tips)

    # kockázatos egyesek
    risky_singles = build_risky_singles(all_tips, count=3)

    # naplózáshoz (esti stat)
    to_log = []
    for t in (safe_acca + risky_singles):
        to_log.append(t)
    with open(TIPPEK_NAPLO, 'w', encoding='utf8') as f:
        json.dump(to_log, f, ensure_ascii=False, indent=2)

    return safe_acca, risky_singles

# --- Üzenet formázás és küldés ---

def format_message(safe_acca, risky_singles):
    today = datetime.datetime.now().strftime('%Y.%m.%d')
    msg = f"🔥 Mai Tippmix ajánlat – {today} 🔥\n"

    # Duplázó rész
    def prod_odds(arr):
        p = 1.0
        for a in arr:
            try: p *= float(a['odd'])
            except: return 0.0
        return p

    if safe_acca:
        msg += "\n✅ *Duplázó szelvény* (2–3 tipp, egy szelvényre)\n"
        for t in safe_acca:
            msg += f"\n⚽️ {t['home']} - {t['away']} ({t['league']}, {t['country']})"
            msg += f"\n🕒 Kezdés: {t['start_time']}"
            msg += f"\n👉 Tipp: {t['bet']} | Szorzó: {t['odd']}"
            msg += f"\n📊 Kategória: {t['kat']}"
            if t['indok']: msg += f" ({t['indok']})"
            msg += "\n"
        msg += f"\n🧮 Össz-szorzó: *{prod_odds(safe_acca):.2f}*\n"
    else:
        msg += "\n✅ *Duplázó szelvény*: ma nem találtunk megfelelő biztonságú kombinációt.\n"

    # Kockázatos egyesek
    if risky_singles:
        msg += "\n⚡ *Kockázatos egyes tippek* (külön-külön téttel)\n"
        for t in risky_singles:
            msg += f"\n⚽️ {t['home']} - {t['away']} ({t['league']}, {t['country']})"
            msg += f"\n🕒 Kezdés: {t['start_time']}"
            msg += f"\n👉 Tipp: {t['bet']} | Szorzó: {t['odd']}"
            msg += f"\n📊 Kategória: {t['kat']}"
            if t['indok']: msg += f" ({t['indok']})"
            msg += "\n"
    else:
        msg += "\n⚡ *Kockázatos egyes tippek*: ma nem találtunk jó értékű lehetőséget.\n"

    msg += "\nℹ️ A duplázó célössz-szorzó: 2.00–2.60 között.\n"
    msg += "📊 Tippmestertől, minden nap 11:00-kor!"
    return msg

async def send_message(text):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.MARKDOWN)

async def main():
    safe_acca, risky_singles = select_daily_bundles()
    msg = format_message(safe_acca, risky_singles)
    await send_message(msg)
    print(msg)

if __name__ == '__main__':
    asyncio.run(main())
