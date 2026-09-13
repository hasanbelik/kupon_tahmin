"""
Guncel takim reytinglerini uretir.
Veri kaynagi: github.com/datasets/football-datasets (football-data.co.uk'nin gunluk
guncellenen aynasi). Son 5 sezon kullanilir, yakin maclara daha fazla agirlik verilir
(Dixon-Coles zaman agirligi).

Cikti: data/ratings.json  -- fetch_coupon.py bu dosyayi okur.
"""
import io
import json
import sys
import pandas as pd
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dixon_coles import DixonColesModel

LEAGUES = {
    "premier-league": {"label": "Premier Lig (İngiltere)", "api_football_id": 39},
    "la-liga": {"label": "La Liga (İspanya)", "api_football_id": 140},
    "serie-a": {"label": "Serie A (İtalya)", "api_football_id": 135},
    "bundesliga": {"label": "Bundesliga (Almanya)", "api_football_id": 78},
    "ligue-1": {"label": "Ligue 1 (Fransa)", "api_football_id": 61},
}

RAW_BASE = "https://raw.githubusercontent.com/datasets/football-datasets/main/datasets"
HEADERS = {"User-Agent": "futbol-kupon-bot"}


def _season_codes(n_seasons=6):
    """Son n_seasons sezonun dosya kodlarini uretir (orn. '2425', '2526', '2627').
    Agustos sonrasi yeni sezon basladigi varsayilir. GitHub API'ye hic gerek yok,
    boylece rate-limit sorunu yasanmaz."""
    import datetime
    today = datetime.date.today()
    start_year = today.year if today.month >= 7 else today.year - 1
    codes = []
    for i in range(n_seasons, -1, -1):
        y = start_year - i
        codes.append(f"{y % 100:02d}{(y + 1) % 100:02d}")
    return codes


def load_league_df(slug, seasons_back=6):
    dfs = []
    for code in _season_codes(seasons_back):
        url = f"{RAW_BASE}/{slug}/season-{code}.csv"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException:
            continue
        if r.status_code != 200:
            continue
        try:
            d = pd.read_csv(io.StringIO(r.text), usecols=["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"])
        except Exception:
            continue
        dfs.append(d)
    if not dfs:
        return None
    df = pd.concat(dfs, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "FTHG", "FTAG"]).sort_values("Date").reset_index(drop=True)
    return df


def main():
    out = {"leagues": {}, "backtests": {}}

    for slug, meta in LEAGUES.items():
        print(f"[{slug}] veri indiriliyor...")
        df = load_league_df(slug)
        if df is None or len(df) < 200:
            print(f"[{slug}] YETERSIZ VERI, atlaniyor.")
            continue

        model = DixonColesModel(xi=0.0018).fit(df)

        # sadece son 400 gunde oynamis (aktif) takimlari tut
        recent_cut = df.Date.max() - pd.Timedelta(days=400)
        recent_teams = sorted(set(df[df.Date >= recent_cut].HomeTeam) | set(df[df.Date >= recent_cut].AwayTeam))

        out["leagues"][slug] = {
            "label": meta["label"],
            "api_football_id": meta["api_football_id"],
            "teams": recent_teams,
            "attack": {t: model.params["attack"][t] for t in recent_teams},
            "defense": {t: model.params["defense"][t] for t in recent_teams},
            "home_adv": model.params["home_adv"],
            "rho": model.params["rho"],
            "as_of": str(df.Date.max().date()),
            "n_matches": len(df),
        }
        print(f"[{slug}] tamam: {len(recent_teams)} takim, veri {df.Date.max().date()} tarihine kadar.")

    Path("data").mkdir(exist_ok=True)
    with open("data/ratings.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nKaydedildi: data/ratings.json")


if __name__ == "__main__":
    main()
