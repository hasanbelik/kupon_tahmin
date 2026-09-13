"""
Dixon-Coles tarzı futbol maç tahmin modeli.

Fikir:
- Her takımın bir HÜCUM (attack) ve SAVUNMA (defense) gücü var.
- Ev sahibi takım için ekstra bir "ev sahibi avantajı" parametresi var.
- Beklenen gol sayısı = takımın hücum gücü * rakibin savunma zayıflığı * (varsa ev avantajı)
- Goller Poisson dağılımına uyduğu varsayılır.
- Dixon-Coles düzeltmesi (rho), düşük skorlu maçlarda (0-0, 1-0, 0-1, 1-1) Poisson
  varsayımının yaptığı küçük hatayı düzeltir.
- Zamana bağlı ağırlıklandırma (xi): yakın zamandaki maçlar, eski maçlardan daha
  fazla ağırlık taşır (takımlar zamanla değişir).
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson


def dc_adjustment(x, y, lam, mu, rho):
    """Dixon-Coles low-score correlation adjustment (tau function)."""
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    elif x == 0 and y == 1:
        return 1 + lam * rho
    elif x == 1 and y == 0:
        return 1 + mu * rho
    elif x == 1 and y == 1:
        return 1 - rho
    else:
        return 1.0


class DixonColesModel:
    def __init__(self, xi=0.0018):
        """xi: zaman ağırlığı yarı-ömür katsayısı (günlük). Büyüdükçe eski maçlar
        daha hızlı unutulur. 0.0018 ~ yaklaşık 1 yıl yarı ömre denk gelir."""
        self.xi = xi
        self.teams = None
        self.params = None

    def _time_weight(self, dates, ref_date):
        days = (ref_date - dates).dt.days.values
        return np.exp(-self.xi * days)

    def fit(self, df, ref_date=None):
        """df: Date, HomeTeam, AwayTeam, FTHG, FTAG kolonlarını içermeli."""
        df = df.dropna(subset=["FTHG", "FTAG"]).copy()
        self.teams = sorted(set(df.HomeTeam) | set(df.AwayTeam))
        n = len(self.teams)
        idx = {t: i for i, t in enumerate(self.teams)}

        if ref_date is None:
            ref_date = df.Date.max()
        w = self._time_weight(df.Date, ref_date)

        home_idx = df.HomeTeam.map(idx).values
        away_idx = df.AwayTeam.map(idx).values
        fthg = df.FTHG.values.astype(float)
        ftag = df.FTAG.values.astype(float)

        # params: [attack_1..n, defense_1..n, home_adv, rho]
        # kimlik kısıtı: attack ortalaması 0 olsun (log-skalada)
        x0 = np.zeros(2 * n + 2)
        x0[-2] = 0.25  # home advantage baslangic
        x0[-1] = -0.05  # rho baslangic

        def neg_log_lik(params):
            attack = params[:n]
            defense = params[n:2 * n]
            home_adv = params[-2]
            rho = params[-1]

            a_h = attack[home_idx]
            d_h = defense[home_idx]
            a_a = attack[away_idx]
            d_a = defense[away_idx]

            lam = np.exp(home_adv + a_h + d_a)  # ev sahibi beklenen gol
            mu = np.exp(a_a + d_h)              # deplasman beklenen gol

            ll = poisson.logpmf(fthg, lam) + poisson.logpmf(ftag, mu)

            # dixon-coles duzeltmesi sadece dusuk skorlarda
            adj = np.array([
                dc_adjustment(int(h), int(a), l, m, rho)
                for h, a, l, m in zip(fthg, ftag, lam, mu)
            ])
            adj = np.clip(adj, 1e-6, None)
            ll = ll + np.log(adj)

            return -np.sum(w * ll)

        # attack ortalamasi 0 kisiti icin constraint yerine sonradan normalize edecegiz
        res = minimize(neg_log_lik, x0, method="L-BFGS-B",
                        options={"maxiter": 150, "ftol": 1e-6})
        params = res.x
        attack = params[:n]
        defense = params[n:2 * n]
        # normalize: ortalama hucum gucu 0 olsun (yorumlanabilirlik icin)
        shift = attack.mean()
        attack = attack - shift
        defense = defense + shift

        self.params = {
            "attack": dict(zip(self.teams, attack)),
            "defense": dict(zip(self.teams, defense)),
            "home_adv": params[-2],
            "rho": params[-1],
        }
        self.fit_success = res.success
        self.ref_date = ref_date
        return self

    def expected_goals(self, home_team, away_team):
        p = self.params
        lam = np.exp(p["home_adv"] + p["attack"][home_team] + p["defense"][away_team])
        mu = np.exp(p["attack"][away_team] + p["defense"][home_team])
        return lam, mu

    def predict_matrix(self, home_team, away_team, max_goals=8):
        lam, mu = self.expected_goals(home_team, away_team)
        rho = self.params["rho"]
        hg = np.arange(0, max_goals + 1)
        ag = np.arange(0, max_goals + 1)
        ph = poisson.pmf(hg, lam)
        pa = poisson.pmf(ag, mu)
        matrix = np.outer(ph, pa)
        # dixon-coles duzeltmesini uygula
        for h in range(2):
            for a in range(2):
                matrix[h, a] *= dc_adjustment(h, a, lam, mu, rho)
        matrix = matrix / matrix.sum()
        return matrix, lam, mu

    def predict_outcome(self, home_team, away_team, max_goals=8):
        matrix, lam, mu = self.predict_matrix(home_team, away_team, max_goals)
        p_home = np.tril(matrix, -1).sum()
        p_draw = np.trace(matrix)
        p_away = np.triu(matrix, 1).sum()
        # over/under 2.5
        total = np.add.outer(np.arange(matrix.shape[0]), np.arange(matrix.shape[1]))
        p_over25 = matrix[total > 2.5].sum()
        p_under25 = 1 - p_over25
        # both teams to score
        btts = matrix[1:, 1:].sum()
        return {
            "home_xg": lam, "away_xg": mu,
            "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
            "p_over25": p_over25, "p_under25": p_under25,
            "p_btts": btts,
        }
