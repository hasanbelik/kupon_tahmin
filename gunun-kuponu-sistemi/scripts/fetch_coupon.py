"""
GUNLUK KUPON URETICI
Her gun GitHub Actions tarafindan calistirilir:
  1) data/ratings.json'daki guncel takim reytinglerini okur
  2) API-Football'dan onumuzdeki N gunun fikstur + oranlarini ceker
  3) Dixon-Coles modeliyle her mac icin olasilik hesaplar
  4) Bahis oranlariyla karsilastirip "deger" (value/+EV) tespiti yapar
  5) docs/coupon.json dosyasina yazar (frontend bunu okur)

Gerekli ortam degiskeni: API_FOOTBALL_KEY  (api-football.com ucretsiz plan)
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from dixon_coles import DixonColesModel
from team_aliases import to_model_name

API_KEY = os.environ.get("API_FOOTBALL_KEY", "").strip()
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

DAYS_AHEAD = 6          # kac gun ilerisine kadar mac taranacak
MIN_EDGE = 0.03         # value bet sayilmasi icin min. olasilik farki (%3)
MAX_COUPON_SIZE = 5      # kupon'a giren en degerli bahis sayisi


def api_get(path, params, retries=2):
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"{BASE_URL}/{path}", headers=HEADERS, params=params, timeout=25)
            data = r.json()
            if data.get("errors"):
                print(f"  [uyari] {path} -> {data['errors']}")
            return data
        except Exception as e:
            print(f"  [hata] {path} basarisiz ({e}), tekrar deneniyor...")
            time.sleep(2)
    return {"response": []}


def current_season_year():
    today = datetime.utcnow()
    return today.year if today.month >= 7 else today.year - 1


def implied_probs_devigged(odds_h, odds_d, odds_a):
    """Bookmaker oranlarindaki komisyonu (overround) orantili olarak temizler."""
    raw = [1 / odds_h, 1 / odds_d, 1 / odds_a]
    s = sum(raw)
    return [x / s for x in raw]


def extract_1x2_odds(odds_response):
    """API-Football /odds cevabindan Match Winner (1X2) oranlarini cikartir.
    Birden fazla bahis sirketi varsa medyan oran kullanilir (tek bir siteye bagli kalmamak icin)."""
    home_odds, draw_odds, away_odds = [], [], []
    for item in odds_response:
        for bookmaker in item.get("bookmakers", []):
            for bet in bookmaker.get("bets", []):
                if bet.get("name") not in ("Match Winner", "1X2"):
                    continue
                values = {v["value"]: float(v["odd"]) for v in bet.get("values", [])}
                if "Home" in values and "Draw" in values and "Away" in values:
                    home_odds.append(values["Home"])
                    draw_odds.append(values["Draw"])
                    away_odds.append(values["Away"])
    if not home_odds:
        return None
    home_odds.sort(); draw_odds.sort(); away_odds.sort()
    mid = len(home_odds) // 2
    return {
        "home": home_odds[mid],
        "draw": draw_odds[mid],
        "away": away_odds[mid],
        "n_bookmakers": len(home_odds),
    }


def predict_match(league_data, home, away, max_goals=8):
    import numpy as np
    from scipy.stats import poisson

    def dc_adj(x, y, lam, mu, rho):
        if x == 0 and y == 0: return 1 - lam * mu * rho
        if x == 0 and y == 1: return 1 + lam * rho
        if x == 1 and y == 0: return 1 + mu * rho
        if x == 1 and y == 1: return 1 - rho
        return 1.0

    lam = float(np.exp(league_data["home_adv"] + league_data["attack"][home] + league_data["defense"][away]))
    mu = float(np.exp(league_data["attack"][away] + league_data["defense"][home]))
    rho = league_data["rho"]

    matrix = np.zeros((max_goals + 1, max_goals + 1))
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson.pmf(h, lam) * poisson.pmf(a, mu)
            if h < 2 and a < 2:
                p *= dc_adj(h, a, lam, mu, rho)
            matrix[h, a] = p
    matrix /= matrix.sum()

    p_home = float(np.tril(matrix, -1).sum())
    p_draw = float(np.trace(matrix))
    p_away = float(np.triu(matrix, 1).sum())
    return {"home_xg": lam, "away_xg": mu, "p_home": p_home, "p_draw": p_draw, "p_away": p_away}


def main():
    if not API_KEY:
        print("HATA: API_FOOTBALL_KEY ortam degiskeni bulunamadi.")
        Path("docs").mkdir(exist_ok=True)
        with open("docs/coupon.json", "w", encoding="utf-8") as f:
            json.dump({"error": "API_FOOTBALL_KEY eksik. GitHub repo secrets'a eklendiginden emin olun.",
                       "generated_at": datetime.now(timezone.utc).isoformat()}, f, ensure_ascii=False, indent=2)
        return

    ratings = json.load(open("data/ratings.json", encoding="utf-8"))
    leagues = ratings["leagues"]
    season = current_season_year()

    today = datetime.now(timezone.utc).date()
    date_from = today.isoformat()
    date_to = (today + timedelta(days=DAYS_AHEAD)).isoformat()

    all_matches = []
    skipped = []

    for slug, league_data in leagues.items():
        league_id = league_data["api_football_id"]
        print(f"\n[{league_data['label']}] fikstur cekiliyor...")
        fx = api_get("fixtures", {
            "league": league_id, "season": season,
            "from": date_from, "to": date_to,
        })
        fixtures = fx.get("response", [])
        print(f"  {len(fixtures)} mac bulundu.")

        for item in fixtures:
            fixture_id = item["fixture"]["id"]
            status = item["fixture"]["status"]["short"]
            if status not in ("NS", "TBD"):  # sadece henuz oynanmamis maclar
                continue

            api_home = item["teams"]["home"]["name"]
            api_away = item["teams"]["away"]["name"]
            model_home = to_model_name(api_home, league_data["teams"])
            model_away = to_model_name(api_away, league_data["teams"])

            if not model_home or not model_away:
                skipped.append({
                    "league": league_data["label"], "home": api_home, "away": api_away,
                    "reason": "Takim modelde bulunamadi (muhtemelen yeni terfi eden takim, yeterli veri yok)."
                })
                continue

            pred = predict_match(league_data, model_home, model_away)

            odds_resp = api_get("odds", {"fixture": fixture_id})
            odds = extract_1x2_odds(odds_resp.get("response", []))

            match_entry = {
                "league": league_data["label"],
                "fixture_id": fixture_id,
                "date": item["fixture"]["date"],
                "home": model_home,
                "away": model_away,
                "prediction": {
                    "p_home": round(pred["p_home"], 4),
                    "p_draw": round(pred["p_draw"], 4),
                    "p_away": round(pred["p_away"], 4),
                    "home_xg": round(pred["home_xg"], 2),
                    "away_xg": round(pred["away_xg"], 2),
                },
                "odds": odds,
                "value_bets": [],
            }

            if odds:
                imp_h, imp_d, imp_a = implied_probs_devigged(odds["home"], odds["draw"], odds["away"])
                candidates = [
                    ("H", model_home + " kazanır", pred["p_home"], imp_h, odds["home"]),
                    ("D", "Beraberlik", pred["p_draw"], imp_d, odds["draw"]),
                    ("A", model_away + " kazanır", pred["p_away"], imp_a, odds["away"]),
                ]
                for code, label, model_p, implied_p, odd in candidates:
                    edge = model_p - implied_p
                    if edge >= MIN_EDGE:
                        match_entry["value_bets"].append({
                            "selection": code, "label": label,
                            "model_prob": round(model_p, 4),
                            "implied_prob": round(implied_p, 4),
                            "edge": round(edge, 4),
                            "odd": odd,
                            "ev_pct": round((model_p * odd - 1) * 100, 1),
                        })

            all_matches.append(match_entry)
            time.sleep(0.3)  # gereksiz hiz limiti asimini onlemek icin

    # gunun en degerli bahislerini topla (tum liglerden, edge'e gore)
    coupon = []
    for m in all_matches:
        for vb in m["value_bets"]:
            coupon.append({**vb, "league": m["league"], "home": m["home"], "away": m["away"],
                           "date": m["date"], "fixture_id": m["fixture_id"]})
    coupon.sort(key=lambda x: x["edge"], reverse=True)
    coupon = coupon[:MAX_COUPON_SIZE]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date_range": {"from": date_from, "to": date_to},
        "leagues_covered": [l["label"] for l in leagues.values()],
        "gunun_kuponu": coupon,
        "all_matches": all_matches,
        "skipped": skipped,
    }

    Path("docs").mkdir(exist_ok=True)
    with open("docs/coupon.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # frontend'in manuel karsilastirma bolumu icin reytingleri de docs'a kopyala
    with open("docs/ratings.json", "w", encoding="utf-8") as f:
        json.dump(ratings, f, ensure_ascii=False, indent=2)

    print(f"\nTamamlandi: {len(all_matches)} mac degerlendirildi, {len(coupon)} deger bahis bulundu, "
          f"{len(skipped)} mac atlandi.")


if __name__ == "__main__":
    main()
