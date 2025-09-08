import requests
import datetime
import pytz
import asyncio
import json
from dateutil import parser
from telegram import Bot
from telegram.constants import ParseMode

# =======================
# KONFIG (töltsd ki!)
# =======================
BOT_TOKEN = '8056404497:AAHyVaYlus7U-kL1llG86u-H0huCvHGF6Gk'
CHAT_ID = '-1002892598463'
API_KEY = 'ce7d900780d35895f214463b4ce49a49'

HEADERS = {'x-apisports-key': API_KEY}
TIPPEK_NAPLO = 'tippek_naplo.json'

# Top ligák + kupák + válogatott tornák
TOP_LEAGUE_IDS = [
    # Top 5
    39,   # Premier League
    78,   # Bundesliga
    140,  # La Liga
    135,  # Serie A
    61,   # Ligue 1

    # Fontos ligák + régiónk
    266,  # NB I (Magyarország)
    40,   # Championship (ENG2)
    79,   # 2. Bundesliga
    141,  # La Liga 2
    136,  # Serie B
    62,   # Ligue 2
    88,   # Eredivisie
    94,   # Jupiler Pro League (Belgium)
    207,  # Bundesliga (Ausztria)
    218,  # Fortuna Liga (Csehország)
    106,  # Ekstraklasa (Lengyelország)
    179,  # Premiership (Skócia)
    203,  # Süper Lig (Törökország)

    # Nemzetközi kupák
    2,    # UEFA Champions League
    3,    # UEFA Europa League
    848,  # UEFA Europa Conference League

    # Válogatott tornák
    1,    # FIFA World Cup
    4,    # UEFA Euro Championship
    5     # UEFA Nations League
]

# =======================
# Duplázó szabályok
# =======================
# Össz-odds cél tartomány (duplázó)
TARGET_MIN_ODDS = 2.0
TARGET_MAX_ODDS = 3.0

# Egyes meccs max odds a duplázóban
SAFE_SINGLE_MAX = 1.65
# Preferált egyedi odds a duplázó lábakhoz (rendezési preferencia)
SAFE_SINGLE_PREF = 1.55

# =======================
# API segédek
# =======================

def get_current_season(league_id):
    url = f"https://v3.football.api-sports.io/leagues?id={league_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return None
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
    print(f"[Fixtures] Ma betöltve: {len(fixtures)} mérkőzés a kijelölt ligákból.")
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
    if res.status_code != 200:
        return None
    data = res.json().get("response", [])
    if not data:
        return None
    return data[0]["league"]["standings"][0]

def get_h2h(home_id, away_id):
    url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={home_id}-{away_id}&last=5"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return []
    return res.json().get('response', [])

def get_odds(fixture_id):
    """
    Több bukmékert végigjárunk és a számunkra kedvezőbb értéket tartjuk meg.
    - 1X2, BTTS (GG), Over/Under 2.5 (OU)
    - Double Chance (DC: 1X/X2/12), Draw No Bet (DNB: home/away)
    """
    url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200 or not res.json().get('response'):
        return None
    try:
        odds = {'1X2': {}, 'GG': {}, 'OU': {}, 'DC': {}, 'DNB': {}}

        def keep(d, k, v, pick='min'):
            try:
                nv = float(v)
            except:
                return
            if k not in d:
                d[k] = v
            else:
                try:
                    cv = float(d[k])
                    if (pick == 'min' and nv < cv) or (pick == 'max' and nv > cv):
                        d[k] = v
                except:
                    d[k] = v

        for bk in res.json()['response'][0].get('bookmakers', []):
            for bet in bk.get('bets', []):
                name = bet.get('name', '')
                vals = bet.get('values', [])

                # 1X2
                if name in ['Match Winner', '1X2', 'Win/Draw/Lose']:
                    for v in vals:
                        val = v.get('value'); odd = v.get('odd')
                        if val in ['Home', '1']: keep(odds['1X2'], 'home', odd, 'max')
                        elif val in ['Away', '2']: keep(odds['1X2'], 'away', odd, 'max')
                        elif val in ['Draw', 'X']: keep(odds['1X2'], 'draw', odd, 'max')

                # BTTS (Both Teams to Score)
                elif name == 'Both Teams to Score':
                    for v in vals:
                        if v.get('value') == 'Yes': keep(odds['GG'], 'yes', v.get('odd'), 'max')
                        elif v.get('value') == 'No': keep(odds['GG'], 'no', v.get('odd'), 'max')

                # Over/Under 2.5
                elif name == 'Over/Under 2.5':
                    for v in vals:
                        if v.get('value') == 'Over 2.5': keep(odds['OU'], 'over', v.get('odd'), 'max')
                        elif v.get('value') == 'Under 2.5': keep(odds['OU'], 'under', v.get('odd'), 'max')

                # Double Chance
                elif name in ['Double Chance', 'Double chance']:
                    for v in vals:
                        m = v.get('value')  # '1X','12','X2'
                        if m in ['1X', '12', 'X2']:
                            keep(odds['DC'], m, v.get('odd'), 'min')  # duplázónál a kisebb odd a jobb "biztos" láb

                # Draw No Bet (DNB)
                elif name in ['Draw No Bet', 'DNB']:
                    for v in vals:
                        m = v.get('value')
                        if m in ['Home', '1']:
                            keep(odds['DNB'], 'home', v.get('odd'), 'min')
                        elif m in ['Away', '2']:
                            keep(odds['DNB'], 'away', v.get('odd'), 'min')

        return odds
    except Exception as e:
        print(f"[ODDS] Hiba feldolgozás közben: {e}")
        return None

# =======================
# Kategorizálás
# =======================

def tipp_kategoria(home_stats, away_stats, bettype, odd_str):
    """
    Lazább, több 'Biztos tipp'-et eredményező kategorizálás.
    DC/DNB piacokra is jól működik (alacsonyabb odd általában).
    """
    kategoria = "Kockázatos tipp"
    indok = []
    try:
        odd = float(odd_str)

        # Eredmény piacok
        if bettype in ["Hazai győzelem", "Vendég győzelem"]:
            if bettype == "Hazai győzelem":
                if home_stats['forma'] >= 2 and home_stats['helyezes'] < away_stats['helyezes'] and odd < 2.30:
                    kategoria = "Biztos tipp"; indok.append("Forma + tabellaelőny + kedvező odds")
            else:
                if away_stats['forma'] >= 2 and away_stats['helyezes'] < home_stats['helyezes'] and odd < 2.30:
                    kategoria = "Biztos tipp"; indok.append("Forma + tabellaelőny + kedvező odds")
            if odd >= 2.40:
                indok.append("Magas szorzó")

        elif bettype == "Döntetlen":
            if odd < 3.50:
                kategoria = "Biztos tipp"; indok.append("Relatíve alacsony döntetlen szorzó")
            else:
                indok.append("Nagyon magas szorzó")

        # Speciális piacok: GG/OU/DC/DNB
        else:
            if odd < 1.90:
                kategoria = "Biztos tipp"; indok.append("Stabil statisztika, kedvező odds")
            elif odd > 2.25:
                indok.append("Magas szorzó")

    except:
        pass
    return kategoria, (", ".join(indok) if indok else None)

# =======================
# Elemzés egy mérkőzésre (javasolt tippek)
# =======================

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
    if '1X2' in odds and all(k in odds['1X2'] for k in ('home', 'away', 'draw')):
        if (home_win > away_win and home_pos < away_pos):
            bet, odd = "Hazai győzelem", odds['1X2']['home']
        elif (away_win > home_win and away_pos < home_pos):
            bet, odd = "Vendég győzelem", odds['1X2']['away']
        else:
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
    if 'GG' in odds and 'yes' in odds['GG']:
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
    if 'OU' in odds and 'over' in odds['OU']:
        bet, odd = "Több mint 2.5 gól", odds['OU']['over']
        kat, indok = tipp_kategoria(home_stats, away_stats, bet, odd)
        tips.append({
            'fixture_id': fixture_id,
            'home': home, 'away': away,
            'league': league, 'country': country,
            'start_time': start_time,
            'bet': bet, 'odd': odd, 'kat': kat, 'indok': indok
        })
    if 'OU' in odds and 'under' in odds['OU']:
        bet, odd = "Kevesebb mint 2.5 gól", odds['OU']['under']
        kat, indok = tipp_kategoria(home_stats, away_stats, bet, odd)
        tips.append({
            'fixture_id': fixture_id,
            'home': home, 'away': away,
            'league': league, 'country': country,
            'start_time': start_time,
            'bet': bet, 'odd': odd, 'kat': kat, 'indok': indok
        })

    # Double Chance (1X/X2/12)
    if 'DC' in odds and odds['DC']:
        for key, label in [('1X', 'Dupla esély 1X'),
                           ('X2', 'Dupla esély X2'),
                           ('12', 'Dupla esély 12')]:
            if key in odds['DC']:
                bet, odd = label, odds['DC'][key]
                kat, indok = tipp_kategoria(home_stats, away_stats, bet, odd)
                tips.append({
                    'fixture_id': fixture_id,
                    'home': home, 'away': away,
                    'league': league, 'country': country,
                    'start_time': start_time,
                    'bet': bet, 'odd': odd, 'kat': kat, 'indok': indok
                })

    # Draw No Bet (DNB)
    if 'DNB' in odds and odds['DNB']:
        for key, label in [('home', 'Hazai DNB'), ('away', 'Vendég DNB')]:
            if key in odds['DNB']:
                bet, odd = label, odds['DNB'][key]
                kat, indok = tipp_kategoria(home_stats, away_stats, bet, odd)
                tips.append({
                    'fixture_id': fixture_id,
                    'home': home, 'away': away,
                    'league': league, 'country': country,
                    'start_time': start_time,
                    'bet': bet, 'odd': odd, 'kat': kat, 'indok': indok
                })

    return tips

# =======================
# Duplázó építő (≤1.65 / össz-odds 2–3)
# =======================

def build_safe_acca(all_tips):
    """
    Duplázó (2–3 meccs):
      - minden láb oddsa <= 1.65
      - össz-odds 2.00–3.00 között
      - előnyben a 'Biztos tipp', majd ha kevés, alacsony odd-ú 'Kockázatos tipp'
    """
    cands = []
    for t in all_tips:
        try:
            o = float(t['odd'])
        except:
            continue
        if o <= SAFE_SINGLE_MAX:
            weight = 0 if t.get('kat') == "Biztos tipp" else 1
            score = (weight, abs(SAFE_SINGLE_PREF - o))
            cands.append((score, t))

    if not cands:
        print("[Duplázó] Nincs jelölt láb (≤1.65).")
        return []

    cands.sort(key=lambda x: x[0])
    picks = [t for _, t in cands][:30]
    print(f"[Duplázó] jelöltek (≤{SAFE_SINGLE_MAX}): {len(picks)}")

    def prod_odds(arr):
        p = 1.0
        for a in arr:
            try:
                p *= float(a['odd'])
            except:
                return 0.0
        return p

    # 2-es kombó
    best = None
    for i in range(len(picks)):
        for j in range(i+1, len(picks)):
            combo = [picks[i], picks[j]]
            val = prod_odds(combo)
            if TARGET_MIN_ODDS <= val <= TARGET_MAX_ODDS:
                best = combo
                break
        if best:
            break

    # 3-as kombó
    if not best:
        for i in range(len(picks)):
            for j in range(i+1, len(picks)):
                for k in range(j+1, len(picks)):
                    combo = [picks[i], picks[j], picks[k]]
                    val = prod_odds(combo)
                    if TARGET_MIN_ODDS <= val <= TARGET_MAX_ODDS:
                        best = combo
                        break
                if best:
                    break
            if best:
                break

    # legközelebbi
    if not best:
        target_mid = (TARGET_MIN_ODDS + TARGET_MAX_ODDS) / 2.0
        best_combo = None
        best_diff = 1e9

        # 2-es
        for i in range(len(picks)):
            for j in range(i+1, len(picks)):
                combo = [picks[i], picks[j]]
                val = prod_odds(combo)
                diff = abs(val - target_mid)
                if diff < best_diff:
                    best_diff = diff
                    best_combo = combo

        # 3-as
        for i in range(len(picks)):
            for j in range(i+1, len(picks)):
                for k in range(j+1, len(picks)):
                    combo = [picks[i], picks[j], picks[k]]
                    val = prod_odds(combo)
                    diff = abs(val - target_mid)
                    if diff < best_diff:
                        best_diff = diff
                        best_combo = combo

        best = best_combo

    return best or []

# =======================
# Kockázatos egyes tippek
# =======================

def build_risky_singles(all_tips, count=3):
    """
    Kockázatos egyesek:
      - preferált: 'Kockázatos tipp'
      - odd >= 2.30
      - ha kevés, engedünk 2.10+-t is
    """
    risky = []
    for t in all_tips:
        try:
            o = float(t['odd'])
            if t.get('kat') == "Kockázatos tipp" and o >= 2.30:
                risky.append((o, t))
        except:
            continue
    if len(risky) < count:
        for t in all_tips:
            try:
                o = float(t['odd'])
                if t.get('kat') == "Kockázatos tipp" and o >= 2.10:
                    risky.append((o, t))
            except:
                continue
    risky.sort(key=lambda x: x[0], reverse=True)
    picked = [t for _, t in risky[:count]]
    print(f"[Risky] kiválasztva: {len(picked)}")
    return picked

# =======================
# Napi kiválasztás + naplózás
# =======================

def select_daily_bundles():
    fixtures = get_today_fixtures()
    all_tips = []
    for fx in fixtures:
        try:
            tips = analyze_fixture(fx)
            all_tips.extend(tips)
        except Exception as e:
            print(f"[Analyze] Hiba egy fixture-nél: {e}")
            continue

    print(f"[Tips] Összes javaslat: {len(all_tips)}")

    # Duplázó (≤1.65, össz 2–3)
    safe_acca = build_safe_acca(all_tips)

    # Kockázatos egyesek
    risky_singles = build_risky_singles(all_tips, count=3)

    # Napló az esti statnak
    to_log = []
    for t in (safe_acca + risky_singles):
        to_log.append(t)
    with open(TIPPEK_NAPLO, 'w', encoding='utf8') as f:
        json.dump(to_log, f, ensure_ascii=False, indent=2)

    return safe_acca, risky_singles

# =======================
# Üzenet
# =======================

def format_message(safe_acca, risky_singles):
    today = datetime.datetime.now().strftime('%Y.%m.%d')
    msg = f"🔥 Mai Tippmix ajánlat – {today} 🔥\n"

    def prod_odds(arr):
        p = 1.0
        for a in arr:
            try:
                p *= float(a['odd'])
            except:
                return 0.0
        return p

    # Duplázó blokk
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
        msg += "\n✅ Duplázó szelvény: ma nem találtunk megfelelő biztonságú kombinációt.\n"

    # Kockázatos egyesek blokk
    if risky_singles:
        msg += "\n⚡️ *Kockázatos egyes tippek* (külön-külön téttel)\n"
        for t in risky_singles:
            msg += f"\n⚽️ {t['home']} - {t['away']} ({t['league']}, {t['country']})"
            msg += f"\n🕒 Kezdés: {t['start_time']}"
            msg += f"\n👉 Tipp: {t['bet']} | Szorzó: {t['odd']}"
            msg += f"\n📊 Kategória: {t['kat']}"
            if t['indok']: msg += f" ({t['indok']})"
            msg += "\n"
    else:
        msg += "\n⚡️ Kockázatos egyes tippek: ma nem találtunk jó értékű lehetőséget.\n"

    msg += "\nℹ️ Duplázó szabály: minden egyes tipp ≤ 1.65 szorzó, az össz-szorzó 2.00–3.00 között.\n"
    msg += "📊 Tippmestertől, minden nap 11:00-kor!"
    return msg

# =======================
# Küldés
# =======================

async def send_message(text):
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=ParseMode.MARKDOWN)

# =======================
# Main
# =======================

async def main():
    safe_acca, risky_singles = select_daily_bundles()
    msg = format_message(safe_acca, risky_singles)
    await send_message(msg)
    print(msg)

if __name__ == '__main__':
    asyncio.run(main())
