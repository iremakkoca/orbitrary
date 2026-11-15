# Developed with assistance from Claude (Anthropic).
# Sude kararları (12:04): MI aralığı kaydı + D2.csv kontrolü; I⊕ üst sınırı max C₁/0,02 ≈ 82,1; ΔTg ≤ 0 ayları NaN (assert, sayılar);
# I⊕ ÖLÇÜMLERİ (yöntem değişmez, yalnız ölçülür): en büyük ayın payı, |u_ort − u_ortanca|, en büyük farkın 10 pikseli.
# Ayrıca: bugünkü MAKALEYİ ETKİLER toplu kaydı kayit\\makaleyi_etkiler_14_kasim.md.
import sys, json, datetime, importlib, warnings
from pathlib import Path
import numpy as np, pandas as pd

KOK = Path.home() / "orbitrary"; KOD, KAYIT, ARA = KOK / "kod", KOK / "kayit", KOK / "ara"
(KOD / "testler" / "test_ozellik_diger_gercek.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""ozellik_diger gerçek temiz\\ verisiyle: CMG türetilmiş ızgaralar, türetilmiş katmanlar, birim kontrolleri,
referanslar (küçük örnek), gerçek pencere temsilleri. Mars jeoloji sözlüğü Sude doldurana kadar bilerek FAIL verir."""
import math
import json
import numpy as np
import pytest
import ayar as A
import katman as K
import ozellik_diger as O
import uzaklik as U


def test_dunya_cmg_turetilmis():
    yol = O.dunya_cmg()
    # Aralıklar verinin kendi sınırlarından türetilir (14 Kasım; ilk sürümdeki elle konmuş MI ve I⊕ sınırları yanlıştı):
    # MI = ε₁₂ε₁₄³/ε₁₃⁴, ε ∈ [0,604; 1] (D2'de ölçülen) → [0,604⁴; 1/0,604⁴] = [0,133; 7,5]
    # I⊕ = C₁(1 − α)/ΔTg, ΔTg ≥ 0,02 K (LST ölçeği); C₁'in en büyüğü ε = 23,44°'de 1,6426 (φ ≈ ±28°, δ = ±23,44°)
    #   → (0; ≈ 82,1] (Sude, 14 Kasım; aşağıda C₁ formülünden hesaplanır)
    # LST: geçerli aralık 7500–65535 × 0,02 K = 150–1310,7 K (dosya valid_range)
    eps = A.ayar("cisim.eksen_egikligi_der")["dunya"]
    c1max = float(np.nanmax(O.C1(np.radians(np.linspace(-90, 90, 18001))[:, None],
                                 np.radians(np.linspace(-eps, eps, 4689))[None, :])))
    assert abs(c1max - 1.6426) < 1e-3, c1max
    aralik = {"tmax": (150, 1310.7), "tort": (150, 1310.7), "tgece": (150, 1310.7),
              "mi": (0.604 ** 4, 1 / 0.604 ** 4), "iarti": (0, c1max / 0.02)}
    for ad, (lo, hi) in aralik.items():
        j = json.loads(yol[ad].with_suffix(".json").read_text(encoding="utf-8"))
        assert j["gecerli"] > 1_000_000, (ad, j["gecerli"])
        assert lo <= j["en_kucuk"] and j["en_buyuk"] <= hi, (ad, j["en_kucuk"], j["en_buyuk"])
    t = json.loads(yol["iarti"].with_suffix(".json").read_text(encoding="utf-8"))["aylar"]
    d = [t[f"ay_{m:02d}"]["deklinasyon_der"] for m in range(1, 13)]
    assert max(d) > 23 and min(d) < -23  # haziran/aralık


@pytest.mark.parametrize("ad", ["cmg_mi", "cmg_tmax", "cmg_tort", "cmg_tgece", "cmg_iarti", "perm_sifir", "siltkil",
                                "berger_dunya", "berger_ay", "berger_mars", "ay_tgece", "hidrojen_th", "pgda", "mars_hcp"])
def test_turetilmis_katman_acilir(ad):
    k = O.ac(ad)
    v = k.ornekle(np.array([-85.0, 0.0, 45.0, 85.0]), np.array([30.0, 10.0, -100.0, 100.0]))
    assert v.shape == (4,)


def test_toryum_birim_ve_esik():
    # belge 6.6: Th ≥ 4,56 ppm = Ay'ın en yüksek toryumlu %10'u → alanca düzgün örnekte pay ≈ 0,10
    th = K.ac("lpgrs_w_th")
    lat, lon = U.kure_noktalari(np.random.default_rng(11), 200000)
    v = th.ornekle(lat, lon)
    assert np.nanmin(v) >= -1 and np.nanmax(v) < 30, (np.nanmin(v), np.nanmax(v))
    pay = float(np.mean(v >= A.ayar("su_buz.ay_toryum_ppm")))
    assert 0.08 <= pay <= 0.12, pay


def test_sifir_kurali_gercek():
    p = O.ac("perm_sifir")
    lat, lon = U.kure_noktalari(np.random.default_rng(12), 200000, -30, 30)
    v = p.ornekle(lat, lon)
    kara = np.isfinite(v)
    assert kara.mean() > 0.15 and np.mean(v[kara] == 0) > 0.99  # tropik karada permafrost yok → 0


@pytest.mark.parametrize("govde,oz", sorted(O.OZELLIK))
def test_referans_kucuk(govde, oz):
    s = O.sira(govde, oz, n_en_fazla=20000, onbellek=False)
    assert s.n > 1000, s.n
    if O.OZELLIK[(govde, oz)][2] == "u+":
        assert 0 <= s.sifir_orani < 1


@pytest.mark.parametrize("govde,lat,lon,kat", [("dunya", 35.58223, -111.63182, (3, 4, 5, 6, 7, 8)),   # 9.3 SP Crater
                                               ("ay", -85.399, 31.180, (3, 4, 5, 6, 7, 8)),         # B5 A3-05
                                               ("ay", 26.13239, 3.63330, (3, 4, 5, 6, 7, 8)),       # 9.1 M-A15
                                               ("mars", 18.44, 77.45, (4, 5, 6, 7, 8))])            # 9.2 R-JEZ
def test_gercek_pencere_temsili(govde, lat, lon, kat):
    T = O.pencere_temsili(govde, [math.radians(lat)], [math.radians(lon)], kategoriler=kat, n_ref=20000)
    if 3 in kat:
        assert abs(np.nansum(T["q3"][0]) - 1) < 1e-6 and T["q3_gecerli"][0] > 0.5
    # Q6: Ay'da toryum maskesi (Th ≥ 4,56 ppm) bütün pencereyi düşürebilir (ör. Imbrium çevresi); orada yalnız
    # "ya tamamen sonlu ya tamamen null" kontrol edilir.
    beklenen = {"Q4": True, "Q8": True, "Q7": not (govde == "ay" and abs(lat) > 70),
                "Q6": True if govde != "ay" else None}
    for k, sonlu in beklenen.items():
        hepsi, hic = np.isfinite(T[k]).all(), (~np.isfinite(T[k])).all()
        assert hepsi or hic, (k, "kısmi null")
        if sonlu is not None:
            assert hepsi == sonlu, (k, govde, lat)
    for f in O.termal_ozellikleri(govde, lat):
        assert np.isfinite(T[f"Q5_{f}"]).all(), f
    if govde != "dunya":
        assert "pi_arti" in T


def test_mars_jeoloji_sozlugu_tam():
    # Sude jeoloji_sozluk.csv'de Mars'ın 44 biriminin grubunu doldurunca geçer (belge 6.3, 15.1)
    G = O.sozluk_matrisi("mars", list(O.ac("sim3292").siniflar))
    assert G.shape == (44, 6)
    T = O.pencere_temsili("mars", [math.radians(18.44)], [math.radians(77.45)], kategoriler=(3,), n_ref=20000)
    assert abs(np.nansum(T["q3"][0]) - 1) < 1e-6
''', encoding="utf-8")
(KAYIT / "makaleyi_etkiler_14_kasim.md").write_text(r'''# MAKALEYİ ETKİLER — 14 Kasım 2026 (kod günü) toplu kayıt

Orbitrary · belge v1.2 (+ v1.2.1 talimatları). Kod yazılırken çıkan, makaleye giren her şey.
Kaynak: `kayit\degisiklik.md` (tarihli satırlar). Durum sütunu: **kaynaklı** = dış kaynağa dayanıyor; **onaylı** = ekip onayladı; **onay bekliyor** = proje kararı, dış kaynağı yok.

## 1. Parametre ve veri

| # | Ne değişti / netleşti | Belge bölümü | Durum | Makaleye not (Emir / Sude) |
|---|---|---|---|---|
| 1 | σv Ay = 10 m, Mars = 1 m (belgede değer yoktu; Dünya 7,17 m aynı) | 4.1, 8.4, T2 | kaynaklı: [105] Smith ve ark. 2010 "~10 m radial"; [104] Smith ve ark. 2001 "~1 m vertical" | T2'de σv = 7,17 / 10 / 1 m; Method'da iki kaynağa bu değerlerle atıf |
| 2 | MI geçerlilik aralığı [0,133; 7,5] = yayınım aralığından (0,604–1,000) türetilmiş matematiksel sınır | 6.4, 10.1 | onaylı (Sude) | ASTER en küçük yayınım 0,604 (belge 0,61 diyordu; talimat 7 UYARI) |
| 3 | I⊕ üst sınırı ≈ 82,1 = max C₁ (1,6426, ε = 23,44°) / 0,02 K | 6.5 | onaylı (Sude) | ölçülen en büyük 75,3 |

## 2. Yöntemin okunuşu (formül aynı, belgede tek anlama inmeyen yer netleşti)

| # | Karar | Belge bölümü | Durum | Makaleye not |
|---|---|---|---|---|
| 4 | P_f,B: "rastgele piksel" yerine alanca düzgün rastgele noktaların piksel değerleri (≤ 10⁶, tohum 20261113) | 5.2 | onay bekliyor | "area-uniform random sample"; neden: enlem-boylam pikseli kutbu 1/cos φ ağırlıklandırır |
| 5 | Dünya Tmax = aylık gündüz LST'nin en büyüğü; T̄ = aylık (gündüz+gece)/2 yıllık ortalaması; Tgece = aylık gece yıllık ortalaması | 6.5 | onay bekliyor | dayanak 6.5 "Aqua öğleden sonra geçişi maksimuma yakın" |
| 6 | I⊕ aylık; C₁ = 0 ve ΔTg ≤ 0 ayları ortalamaya girmez (ΔTg ≤ 0 NaN, assert ve sayılar kayıtta) | 6.5 | ΔTg ≤ 0: onaylı (Sude); yıllık ortalama belgedeki gibi kalır | δ⊙: Michalsky 1988 (Astronomical Almanac düşük duyarlıklı algoritma) |
| 7 | ASTER MI her bandın 12 aylık ortalamasından | 6.4 | onay bekliyor | — |
| 8 | Ay aydınlanması: |φ| ≥ 65° PGDA ve < 65° Berger hücreleri kendi kapsamlarında ayrı sıralanır | 6.8 | onay bekliyor | iki büyüklük farklı birimde |
| 9 | Sıfır kuralında kara hücresi = MCD12C1 kara payı ≥ 0,5 | 6.6 | onay bekliyor | — |
| 10 | Ay π⁺: hücrenin alt örneklerinin ≥ yarısında ice_depth ≠ −999 ise hücre pozitif | 6.6 | onay bekliyor | — |

## 3. Test tanımı

| # | Ne | Belge bölümü | Not |
|---|---|---|---|
| 11 | "Halka ızgarası" testi: formül aralıkları her halkada 20 km ± %5; gerçek komşu uzaklığı kutup ilk halkası (m = 3, ~17,3 km) dışında ± %5; ≤ 5 km sapan tıklama kendi penceresi = en yakın merkez; her nokta kendi hücresine eşlenir, merkeze uzaklık hücre köşe uzaklığını aşmaz (kutup halka 0: 17,3 km, halka 1: 15,6 km, diğer ≤ 14,7 km); en yakın merkeze uzaklık < 15 km | 8.3, T5 | formülün en yakın merkezi verme oranı %96,2 (`kayit\izgara_bilgi.json`) |
| 12 | K12 kontrolü: belgedeki SW (1/π, yarım çember) = Carrière ve ark. (1/2π, S¹); sabit aynı, K12 tetiklenmedi, Ψ₂ değişmez | 6.2, 8.1, 11 | test: `test_sw_tek_nokta_analitik_ve_K12` |

## 4. Hedefler, jeoloji, doğrulama (Sude dönüşü)

| # | Ne | Belge bölümü | Not |
|---|---|---|---|
| 13 | R-UTO ikiye ayrıldı: R-UTO Viking 2 (47,64 / 134,29, NSSDCA), R-ZHU Zhurong (25,066 / 109,925, Liu ve ark. 2022) | 9.2 | iki iniş yeri ~1600 km uzak |
| 14 | R-OLY = IAU Gazetteer özellik merkezi; sitede "feature centre" | 9.2 | "zirve" denmez |
| 15 | R-JEZ belge değeri 18,44 / 77,45 kaldı (Wikipedia hassas değeri kullanılmadı) | 9.2 | kaynak: JPL basın kiti + belge |
| 16 | GLiM pb = gabro, norit, peridotit (Hartmann & Moosdorf 2012, Ek A4.1.4, para. [71]); anortozit geçmez; Ay → pb eşlemesi değişmez, gerekçe cümlesi düzeltildi | 6.3, 13.3 | açık kontrol kısmen kapandı |
| 17 | lApd (kutup kumulları), Hpe (kutup yapıları), Nhe (yayla yapıları) ön kayıtlı kurala göre gruplandı (DMU tanımından farklı) | 6.3, L12 | Limitations cümlesi |
| 18 | V1: 11 çiftin hepsi kaynakla tutuyor; JETT5 NTRS kimliği doğrulanamadı (USGS kaynağı eklendi); Dumont Dunes 11 Mayıs haber tarihi; JETT1 kesin tarih yok | 9.3 | — |

## 5. Implementation (yöntem aynı; makale Bölüm 8 için)

- Hücre ortalaması (4.4): hücreden ince katmanda hücre içinde s × s alt nokta (piksel kenarı başına ≥ 2, s ≤ 10) → alan ağırlıklı piksel ortalaması.
- Vektör jeoloji (4.4): her pencerede hücre başına 5 × 5 nokta, poligon içi testi (shapely, hazırlanmış poligon). GLiM rasterleştirilmedi.
- Topografya (6.1): "2 hücre dışarıdan" her ölçekte → DEM 8 ince hücre dışından okunur (2 km'de 2 blok).
- F⁻¹ (5.1): ECDF genelleştirilmiş tersi, k = ⌈n(2m − 1)/2M⌉ tam sayı aritmetiğiyle.
- SW doğrultuları orta nokta θ_j = −π/2 + (j − ½)π/Mθ.
- Diviner PRP hücreye: en yakın üçgen merkezi, ortanca komşu aralığının 3 katı eşik (proje kararı), arama eşikle sınırlı.
- H₀: GUDHI CubicalComplex; bağımsız union-find (8-komşuluk) ile 203 pencerede birebir aynı.
- Berger f(φ): 0,001° tablo + doğrusal ara değer (ölçülen en büyük hata 1,2e-9).

## 6. Bekleyen ölçüm (Sude Limitations cümlesini yazacak)

- I⊕: ΔTg < 1 K olan geçerli ayı bulunan piksel oranı 0,329 (2 913 886 / 8 638 888). I⊕ yüzdelikleri: %1 0,0112; %50 0,0541; %99 0,5152; %99,9 3,9962 (`kayit\iarti_teshis.json`).
- Ek ölçümler (en büyük ayın yıllık toplamdaki payı; |u_ort − u_ortanca|; en büyük farkın 10 pikseli) → `kayit\iarti_olcum.json`.
''', encoding="utf-8")
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import katman as K, ozellik_diger as O, test_kos
importlib.reload(K); importlib.reload(O); importlib.reload(test_kos)

# --- 1. D2.csv: en küçük ASTER yayınımı 0,604 yazılı mı (talimat 7)
d2 = pd.read_csv(KAYIT / "D2.csv", dtype=str, encoding="utf-8-sig").fillna("")
bulunan = d2[d2.apply(lambda r: r.str.contains("0.604|0,604").any(), axis=1)]
if len(bulunan):
    print("1) D2.csv'de 0,604 zaten yazılı:"); print(bulunan.to_string(index=False)[:800])
else:
    yeni = {c: "" for c in d2.columns}
    metin = ("E4 ASTER GED en küçük yayınım 0,604 (< 0,61): talimat 7 UYARI; MI geçerlilik aralığı [0,133; 7,5] "
             "bu yayınım aralığından (0,604–1,000) türetilmiş matematiksel sınır (Sude onayı, 14 Kasım)")
    for c in d2.columns:
        cl = c.lower()
        if "set" in cl or cl in ("kod", "veri"): yeni[c] = "E4"
        elif "durum" in cl or "sonuc" in cl: yeni[c] = "UYARI"
        elif "deger" in cl or "olcul" in cl: yeni[c] = "0.604"
        elif "not" in cl or "aciklama" in cl or "kaynak" in cl: yeni[c] = metin
    if not any(v == metin for v in yeni.values()): yeni[d2.columns[-1]] = metin
    pd.concat([d2, pd.DataFrame([yeni])]).to_csv(KAYIT / "D2.csv", index=False, encoding="utf-8-sig")
    print("1) D2.csv'ye eklendi:", yeni)

# --- 2. I⊕ aylık: ΔTg ≤ 0 NaN (assert) ve sayılar; ölçümler
gun = {O._tarih(a).month: a for a in K.aylik("E5", "lst_gunduz")}
gec = {O._tarih(a).month: a for a in K.aylik("E5", "lst_gece")}
alb = {O._tarih(a).month: a for a in K.aylik("E6", "albedo_wsa")}
lat_c = 90.0 - (np.arange(3600) + 0.5) * 0.05
lon_c = -180.0 + (np.arange(7200) + 0.5) * 0.05
Iay = np.full((12, 3600, 7200), np.nan, np.float32)
dT_negatif = {}
for ay in range(1, 13):
    D = np.asarray(K.ac(gun[ay]).kaynak, np.float32); N = np.asarray(K.ac(gec[ay]).kaynak, np.float32)
    a = np.asarray(K.ac(alb[ay]).kaynak, np.float32)
    _, d = O.gunes_boylami_ve_deklinasyon(datetime.date(2023, ay, 15))
    c1 = O.C1(np.radians(lat_c), d)[:, None]
    dT = D - N
    Im = O.I_arti_ay(c1, a, dT).astype(np.float32)
    kotu = (c1 > 0) & np.isfinite(dT) & (dT <= 0) & np.isfinite(a)
    assert np.isnan(Im[kotu]).all(), ay          # Sude: ΔTg ≤ 0 → NaN
    dT_negatif[f"{ay:02d}"] = int(kotu.sum())
    Iay[ay - 1] = Im
    print(f"   ay {ay:02d}: ΔTg ≤ 0 ve C₁ > 0 piksel {dT_negatif[f'{ay:02d}']:,}", flush=True)
with warnings.catch_warnings():
    warnings.simplefilter("ignore", RuntimeWarning)
    n_ay = np.isfinite(Iay).sum(0)
    ort = np.nanmean(Iay, 0)
    med = np.nanmedian(Iay, 0)
    pay = np.nanmax(Iay, 0) / np.nansum(Iay, 0)
cmg = np.load(ARA / "cmg_iarti.npy")
assert np.allclose(ort, cmg, rtol=1e-4, equal_nan=True), "yıllık ortalama ara\\cmg_iarti.npy ile tutmuyor"

def agirlikli_sira(x, w):
    """Alan ağırlıklı ECDF ile cisim içi sıra (belge 5.2 biçimi): u = (W_<x + ½ W_=x) / W. Ağırlık cos φ;
    P_f,B alanca düzgün örneklemin örnekleme gürültüsüz karşılığı."""
    g = np.isfinite(x)
    xv, wv = x[g].astype(np.float64), w[g]
    uniq, ters = np.unique(xv, return_inverse=True)
    ws = np.bincount(ters, weights=wv)
    once = np.concatenate([[0.0], np.cumsum(ws)[:-1]])
    u = np.full(x.shape, np.nan); u[g] = ((once + 0.5 * ws) / wv.sum())[ters]
    return u

w = np.broadcast_to(np.cos(np.radians(lat_c))[:, None], ort.shape)
ortak = np.isfinite(ort) & np.isfinite(med)
u_ort = agirlikli_sira(np.where(ortak, ort, np.nan), w)
u_med = agirlikli_sira(np.where(ortak, med, np.nan), w)
fark = np.abs(u_ort - u_med)
def ozet(v): v = v[np.isfinite(v)]; return {"ortanca": round(float(np.median(v)), 4), "yuzde95": round(float(np.percentile(v, 95)), 4), "en_buyuk": round(float(v.max()), 4)}
en10 = np.argsort(np.where(np.isfinite(fark), fark, -1).ravel())[::-1][:10]
r, c = np.unravel_index(en10, fark.shape)
olcum = {
    "tanim": {"I_yillik": "belge 6.5: geçerli ayların ortalaması (değişmedi)",
              "pay": "piksel başına en büyük aylık I⊕ / geçerli ayların toplamı",
              "fark": "|u(yıllık ortalama) − u(aylık ortanca)|, u = cos φ ağırlıklı ECDF sırası (belge 5.2 biçimi), ortak geçerli pikseller"},
    "dTg_negatif_ay_piksel": dT_negatif, "dTg_negatif_toplam": int(sum(dT_negatif.values())),
    "gecerli_piksel": int(ortak.sum()), "gecerli_ay_sayisi_ortanca": int(np.median(n_ay[ortak])),
    "en_buyuk_ayin_payi": ozet(pay[ortak]),
    "sira_farki": ozet(fark),
    "en_buyuk_fark_10_piksel": [{"enlem": round(float(lat_c[i]), 3), "boylam": round(float(lon_c[j]), 3),
                                 "fark": round(float(fark[i, j]), 4), "gecerli_ay": int(n_ay[i, j]),
                                 "I_ort": round(float(ort[i, j]), 5), "I_ortanca": round(float(med[i, j]), 5)} for i, j in zip(r, c)],
}
(KAYIT / "iarti_olcum.json").write_text(json.dumps(olcum, ensure_ascii=False, indent=1), encoding="utf-8")
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | Sude kararları: MI aralığı [0,133; 7,5] yayınım aralığından (0,604–1,000) türetilmiş matematiksel sınır (onaylı); "
            "I⊕ üst sınırı max C₁ (1,6426)/0,02 ≈ 82,1; ΔTg ≤ 0 ayları NaN (assert, sayılar kayit\\iarti_olcum.json); "
            "belge 6.5 yıllık ortalama aynen kalır, ortanca/eşik yok | etkisi: Limitations (Sude yazar)\n")
print("\n2) I⊕ ölçümleri:"); print(json.dumps(olcum, ensure_ascii=False, indent=1))

# --- 3. CMG testi (yeni sınır)
test_kos.calistir("D4_test_cmg_sinir", "testler/test_ozellik_diger_gercek.py", ek=["-k", "cmg"])
