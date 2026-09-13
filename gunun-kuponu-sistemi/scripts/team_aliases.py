"""
Farklı veri kaynaklari ayni takima farkli isimler veriyor:
  football-data.co.uk (bizim modelimiz):  "Man United", "Nott'm Forest", "Wolves"
  API-Football:                            "Manchester United", "Nottingham Forest", "Wolverhampton Wanderers"

Bu dosya, API-Football isimlerini modelin bildigi isimlere cevirir.
Eslesme bulunamazsa None doner ve o mac atlanir (coupon.json icinde "skipped" listesine yazilir).
"""

import re

# API-Football takim adi (normalize edilmis) -> modelin kullandigi isim
ALIASES = {
    # --- Premier Lig ---
    "manchester united": "Man United",
    "manchester city": "Man City",
    "nottingham forest": "Nott'm Forest",
    "wolverhampton wanderers": "Wolves",
    "newcastle united": "Newcastle",
    "tottenham hotspur": "Tottenham",
    "west ham united": "West Ham",
    "brighton and hove albion": "Brighton",
    "brighton & hove albion": "Brighton",
    "crystal palace": "Crystal Palace",
    "aston villa": "Aston Villa",
    "afc bournemouth": "Bournemouth",
    "bournemouth": "Bournemouth",
    "leeds united": "Leeds",
    "leicester city": "Leicester",
    "ipswich town": "Ipswich",
    "sunderland": "Sunderland",
    "everton": "Everton",
    "fulham": "Fulham",
    "brentford": "Brentford",
    "arsenal": "Arsenal",
    "chelsea": "Chelsea",
    "liverpool": "Liverpool",
    "burnley": "Burnley",

    # --- La Liga ---
    "real madrid": "Real Madrid",
    "barcelona": "Barcelona",
    "atletico madrid": "Ath Madrid",
    "atlético madrid": "Ath Madrid",
    "athletic club": "Ath Bilbao",
    "athletic bilbao": "Ath Bilbao",
    "real sociedad": "Sociedad",
    "real betis": "Betis",
    "sevilla": "Sevilla",
    "valencia": "Valencia",
    "villarreal": "Villarreal",
    "celta vigo": "Celta",
    "rayo vallecano": "Vallecano",
    "getafe": "Getafe",
    "girona": "Girona",
    "osasuna": "Osasuna",
    "mallorca": "Mallorca",
    "real valladolid": "Valladolid",
    "valladolid": "Valladolid",
    "las palmas": "Las Palmas",
    "deportivo alaves": "Alaves",
    "deportivo alavés": "Alaves",
    "alaves": "Alaves",
    "espanyol": "Espanol",
    "leganes": "Leganes",
    "leganés": "Leganes",
    "elche": "Elche",
    "levante": "Levante",
    "real oviedo": "Oviedo",
    "oviedo": "Oviedo",

    # --- Serie A ---
    "inter": "Inter",
    "internazionale": "Inter",
    "ac milan": "Milan",
    "milan": "Milan",
    "juventus": "Juventus",
    "napoli": "Napoli",
    "roma": "Roma",
    "as roma": "Roma",
    "lazio": "Lazio",
    "atalanta": "Atalanta",
    "fiorentina": "Fiorentina",
    "bologna": "Bologna",
    "torino": "Torino",
    "udinese": "Udinese",
    "genoa": "Genoa",
    "cagliari": "Cagliari",
    "hellas verona": "Verona",
    "verona": "Verona",
    "lecce": "Lecce",
    "parma": "Parma",
    "como": "Como",
    "empoli": "Empoli",
    "venezia": "Venezia",
    "monza": "Monza",
    "sassuolo": "Sassuolo",
    "cremonese": "Cremonese",
    "pisa": "Pisa",

    # --- Bundesliga ---
    "bayern munich": "Bayern Munich",
    "fc bayern munich": "Bayern Munich",
    "borussia dortmund": "Dortmund",
    "rb leipzig": "RB Leipzig",
    "bayer leverkusen": "Leverkusen",
    "eintracht frankfurt": "Ein Frankfurt",
    "borussia monchengladbach": "M'gladbach",
    "borussia mönchengladbach": "M'gladbach",
    "vfl wolfsburg": "Wolfsburg",
    "wolfsburg": "Wolfsburg",
    "sc freiburg": "Freiburg",
    "freiburg": "Freiburg",
    "union berlin": "Union Berlin",
    "1. fc union berlin": "Union Berlin",
    "fc koln": "FC Koln",
    "fc köln": "FC Koln",
    "1. fc koln": "FC Koln",
    "mainz 05": "Mainz",
    "fsv mainz 05": "Mainz",
    "mainz": "Mainz",
    "vfb stuttgart": "Stuttgart",
    "stuttgart": "Stuttgart",
    "tsg hoffenheim": "Hoffenheim",
    "hoffenheim": "Hoffenheim",
    "werder bremen": "Werder Bremen",
    "fc augsburg": "Augsburg",
    "augsburg": "Augsburg",
    "vfl bochum": "Bochum",
    "bochum": "Bochum",
    "fc heidenheim": "Heidenheim",
    "1. fc heidenheim": "Heidenheim",
    "holstein kiel": "Holstein Kiel",
    "fc st. pauli": "St Pauli",
    "st pauli": "St Pauli",
    "hamburger sv": "Hamburg",
    "hamburg": "Hamburg",

    # --- Ligue 1 ---
    "paris saint germain": "Paris SG",
    "paris saint-germain": "Paris SG",
    "psg": "Paris SG",
    "olympique marseille": "Marseille",
    "marseille": "Marseille",
    "olympique lyonnais": "Lyon",
    "lyon": "Lyon",
    "as monaco": "Monaco",
    "monaco": "Monaco",
    "lille": "Lille",
    "losc lille": "Lille",
    "rc lens": "Lens",
    "lens": "Lens",
    "stade rennais": "Rennes",
    "rennes": "Rennes",
    "nice": "Nice",
    "ogc nice": "Nice",
    "toulouse": "Toulouse",
    "toulouse fc": "Toulouse",
    "stade brestois": "Brest",
    "brest": "Brest",
    "rc strasbourg": "Strasbourg",
    "strasbourg": "Strasbourg",
    "montpellier": "Montpellier",
    "nantes": "Nantes",
    "fc nantes": "Nantes",
    "angers": "Angers",
    "angers sco": "Angers",
    "le havre": "Le Havre",
    "le havre ac": "Le Havre",
    "auxerre": "Auxerre",
    "aj auxerre": "Auxerre",
    "as saint-etienne": "St Etienne",
    "saint-etienne": "St Etienne",
    "fc metz": "Metz",
    "metz": "Metz",
    "paris fc": "Paris FC",
    "reims": "Reims",
    "stade de reims": "Reims",
    "fc lorient": "Lorient",
    "lorient": "Lorient",
}


def _normalize(name: str) -> str:
    n = name.lower().strip()
    n = n.replace(".", "").replace("-", " ")
    n = re.sub(r"\s+", " ", n)
    return n


def to_model_name(api_football_name: str, model_teams=None):
    """API-Football takim adini modelin bildigi isme cevirir. Bulunamazsa None doner.

    model_teams verilirse, once dogrudan (normalize edilmis) eslesme denenir
    (orn. 'Arsenal' -> 'arsenal' -> 'Arsenal'), bulunamazsa ALIASES sozlugune bakilir.
    """
    n = _normalize(api_football_name)

    if model_teams:
        direct = {_normalize(t): t for t in model_teams}
        if n in direct:
            return direct[n]

    if n in ALIASES:
        candidate = ALIASES[n]
        if model_teams is None or candidate in model_teams:
            return candidate

    return None
