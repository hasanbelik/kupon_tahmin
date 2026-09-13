# Günün Kuponu — Kantitatif Futbol Tahmin Sistemi

Dixon–Coles Poisson modeliyle 5 büyük Avrupa liginde (Premier Lig, La Liga, Serie A,
Bundesliga, Ligue 1) her gün otomatik olarak değerli (+EV) bahisleri tarayan,
tamamen ücretsiz ve otomatik çalışan bir sistem.

## Nasıl çalışır?

Her sabah (varsayılan: 08:00 Türkiye saati) GitHub Actions otomatik olarak:
1. `scripts/build_ratings.py` — geçmiş 6 sezonluk maç verisiyle takım reytinglerini günceller
2. `scripts/fetch_coupon.py` — API-Football'dan önümüzdeki 6 günün fikstür ve oranlarını çeker,
   modelle karşılaştırır, `docs/coupon.json` dosyasını üretir
3. Sonucu otomatik olarak repoya commit'ler

`docs/index.html` (GitHub Pages üzerinden yayınlanır) bu JSON dosyasını okuyup
"Günün Kuponu" butonuyla gösterir.

## Kurulum (tek seferlik)

### 1) API-Football anahtarı al
- https://dashboard.api-football.com/register adresinden ücretsiz kaydol (kredi kartı istemez)
- Dashboard'da "My Access" bölümünden API anahtarını kopyala
- Ücretsiz plan: günde 100 istek — bu sistem günde ~30-40 istek kullanır, yeterli

### 2) Bu dosyaları bir GitHub reposuna yükle
- GitHub'da yeni bir **public** repo oluştur (private repo'da Actions dakika limiti daha kısıtlı)
- Bu klasördeki tüm dosya ve klasörleri (scripts/, docs/, data/, .github/, requirements.txt)
  repoya yükle (GitHub web arayüzünde "Add file > Upload files" ile sürükle-bırak yeterli)

### 3) API anahtarını gizli bilgi (secret) olarak ekle
- Repo sayfasında **Settings > Secrets and variables > Actions > New repository secret**
- Name: `API_FOOTBALL_KEY`
- Value: (1. adımda aldığın anahtar)
- **Add secret**

### 4) GitHub Pages'i aç
- **Settings > Pages**
- Source: "Deploy from a branch"
- Branch: `main`, klasör: `/docs`
- Save

Birkaç dakika sonra siten şu adreste yayında olacak:
`https://<kullanici-adin>.github.io/<repo-adin>/`

### 5) İlk kuponu oluştur
- Repo sayfasında **Actions** sekmesi
- "Günün Kuponu - Günlük Güncelleme" workflow'unu seç
- **Run workflow** butonuna tıkla (elle tetikleme)
- ~1-2 dakika sonra `docs/coupon.json` güncellenmiş olacak

Bundan sonra sistem her gün otomatik çalışacak. Cron zamanını değiştirmek istersen
`.github/workflows/daily-coupon.yml` içindeki `cron: "0 5 * * *"` satırını düzenle
(UTC saatine göre; 5 = Türkiye saatiyle 08:00).

## Dosya yapısı

```
scripts/
  dixon_coles.py      -> Poisson/Dixon-Coles model sınıfı
  team_aliases.py      -> API-Football <-> model takım isim eşleştirmesi
  build_ratings.py     -> geçmiş verilerle takım reytinglerini eğitir
  fetch_coupon.py       -> günlük fikstür+oran çekip kupon üretir
data/
  ratings.json          -> güncel takım reytingleri (otomatik güncellenir)
docs/
  index.html            -> web arayüzü (GitHub Pages)
  coupon.json           -> günün kuponu (otomatik güncellenir)
  ratings.json          -> arayüzün manuel karşılaştırma sekmesi için kopya
.github/workflows/
  daily-coupon.yml      -> günlük otomasyon
```

## Önemli notlar

- **Yeni terfi eden takımlar** (üst lige yeni çıkan) için modelin geçmiş verisi yoksa
  o maç güvenlik amacıyla atlanır (tahmin uydurulmaz). `coupon.json` içindeki
  `skipped` listesinde görebilirsin.
- **"+EV" (değerli bahis)** etiketi kazanma garantisi değildir — sadece modelin
  hesapladığı olasılığın bahis şirketinin sunduğu oranın ima ettiği olasılıktan
  yüksek olduğu anlamına gelir. Uzun vadede istatistiksel bir kenardır.
- Backtest sonuçlarına göre model, ligine bağlı olarak %47-54 arası maç sonucu
  doğruluğu veriyor. Futbol yüksek varyanslı bir spordur; kısa vadede kayıp
  serileri normaldir.
- Bu araç bir yatırım/bahis tavsiyesi değildir.
