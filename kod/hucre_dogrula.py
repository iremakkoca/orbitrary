# Developed with assistance from Claude (Anthropic).
# 17.4 sıra 12: kod\\dogrula.py + testler (belge 8.3 V1–V10; Q-3…Q-7). MAKALEYİ ETKİLER güncel kaydı.
import sys, json, importlib
from pathlib import Path
KOK = Path.home() / "orbitrary"; KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / "dogrula.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 8.3: istatistiksel testler V1–V10 (saf fonksiyonlar; hangi hedef/aday kümesi kullanılacağı kos.py'nin işi).

Onaylı kararlar (Sude): Q-3 V2 sınıf payı = pencere ortalaması MCD12C1 payı ≥ %90; Q-4 V4/V5 hedefleri 100 Ay + 100 Mars
ızgara penceresi (tohum 20261113, alt tohum V4/V5); Q-5 V5 tam sıralama topolojisiz; Q-6 V7 gürültü yalnız hedef + 20
komşusunun DEM'ine; Q-7 V6 çiftleri = liste hedefleri × E_K adayları (8 s_k'nin hepsi olan).
Doğrulama yüzdelikleri (Π) bütün E′ üzerinde ve topolojisizdir (belge 7.4).
"""
import numpy as np
from scipy.stats import chi2, mannwhitneyu, spearmanr

import ayar as A
import puan as Pn

ALFA = 0.05          # belge 8.3: α₀
BOOTSTRAP = 2000     # belge 8.3 V3
B_PRIME = 1000       # belge 8.3 V3: hedef başına E′'den 1000 rastgele pencere
V45_HEDEF = (100, 100)   # Q-4: 100 Ay + 100 Mars
SPEARMAN_ESIK = 0.8  # belge 8.3 V6
V4_TAU_ESIK = 0.9    # belge 8.3 V4 / K4


def _alt(ad):
    return int(A.ayar("alt_tohum")[ad])


# ------------------------------------------------------------------ V1, V2
def pi_degeri(P_E, P_analog, kapidan_kaldi=False):
    """V1: Π_a = #{E ∈ E′ : P(E; T_a) ≤ P(E_a; T_a)} / |E′|. P_E: bütün E′ puanları (NaN → sayılır, |E′| içinde).
    K14: analog kapıdan kaldıysa Π = 0 (ayrıca yazılır)."""
    P = np.asarray(P_E, float)
    if kapidan_kaldi:
        return 0.0
    with np.errstate(invalid="ignore"):
        return float(np.sum(P <= float(P_analog)) / len(P))


def fisher_v1(pi, n_E):
    """V1: X² = −2 Σ ln(1 − Π_a + 1/|E′|) ~ χ²_{2m} (H₀). Dönüş (X², p) — tek yönlü üst kuyruk."""
    pi = np.asarray(pi, float)
    X = float(-2 * np.sum(np.log(1 - pi + 1.0 / n_E)))
    return X, float(chi2.sf(X, 2 * len(pi)))


def fisher_v2(pi, n_E):
    """V2: X²₋ = −2 Σ ln(Π_b + 1/|E′|) ~ χ²_{2m_B} (H₀). Dönüş (X²₋, p)."""
    pi = np.asarray(pi, float)
    X = float(-2 * np.sum(np.log(pi + 1.0 / n_E)))
    return X, float(chi2.sf(X, 2 * len(pi)))


def v2_sec(pay_orman, pay_tarim, n_cift, esik=0.9):
    """V2 (D6, Q-3): her V1 çifti için bir yağmur ormanı (sınıf 2 payı ≥ %90) ve bir tarım (sınıf 12 ≥ %90) penceresi,
    tohum 20261113 (alt V2). Aynı pencere iki kez seçilmez. Dönüş (orman_idx (n_cift,), tarim_idx (n_cift,))."""
    rng = A.rng(_alt("V2"))
    o = np.flatnonzero(np.asarray(pay_orman, float) >= esik)
    t = np.flatnonzero(np.asarray(pay_tarim, float) >= esik)
    assert len(o) >= n_cift and len(t) >= n_cift, (len(o), len(t))
    return rng.choice(o, n_cift, replace=False), rng.choice(t, n_cift, replace=False)


# ------------------------------------------------------------------ V3
def auc(PA, PB):
    """V3: U = Σ_a Σ_b (1[P_a > P_b] + ½ 1[P_a = P_b]), AUC = U / (|A||B′|)."""
    a = np.sort(np.asarray(PA, float)); b = np.sort(np.asarray(PB, float))
    buyuk = np.searchsorted(b, a, side="left")
    esit = np.searchsorted(b, a, side="right") - buyuk
    return float((buyuk + 0.5 * esit).sum() / (len(a) * len(b)))


def v3(PA, PB):
    """V3: AUC, tek yönlü Mann–Whitney p (H₁: AUC > 0,5) [63], %95 GA 2000 bootstrap (yüzdelik yöntemi) [28], alt tohum V3.
    Bootstrap: A ve B′ ayrı ayrı yerine koyarak yeniden örneklenir."""
    PA = np.asarray(PA, float); PB = np.asarray(PB, float)
    a = auc(PA, PB)
    p = float(mannwhitneyu(PA, PB, alternative="greater").pvalue)
    rng = A.rng(_alt("V3"))
    bs = np.empty(BOOTSTRAP)
    for i in range(BOOTSTRAP):
        bs[i] = auc(rng.choice(PA, len(PA)), rng.choice(PB, len(PB)))
    return {"AUC": a, "p": p, "GA95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


def b_prime(n_E, n_hedef):
    """V3: her hedef için E′'den 1000 rastgele pencere (tohum 20261113, alt V3; hedef başına ayrı akış). (n_hedef, 1000)."""
    kok = np.random.SeedSequence(A.TOHUM, spawn_key=(_alt("V3"), 1))
    return np.stack([np.random.default_rng(c).choice(n_E, B_PRIME, replace=False) for c in kok.spawn(n_hedef)])


# ------------------------------------------------------------------ V4, V5
def rastgele_hedefler(n_ay, n_mars, alt):
    """Q-4: 100 Ay + 100 Mars ızgara penceresi, tohum 20261113, alt tohum (V4 ya da V5). Dönüş (ay_idx, mars_idx)."""
    rng = A.rng(_alt(alt))
    return np.sort(rng.choice(n_ay, V45_HEDEF[0], replace=False)), np.sort(rng.choice(n_mars, V45_HEDEF[1], replace=False))


def v4_ozet(s, s2, tau):
    """V4: ortalama |s_k − s′_k| (kategori başına, NaN çiftler dışarıda) ve τ̄b. τ̄b < 0,9 → K4 (|R| iki katı, bir kez)."""
    s = np.asarray(s, float); s2 = np.asarray(s2, float)
    with np.errstate(invalid="ignore"):
        fark = np.nanmean(np.abs(s - s2), axis=0)
    t = float(np.nanmean(np.asarray(tau, float)))
    return {"ortalama_fark": [None if np.isnan(f) else float(f) for f in np.atleast_1d(fark)], "tau_ort": t,
            "K4_tetiklendi": bool(t < V4_TAU_ESIK)}


def recall(top3_tam, E_K):
    """V5: |Top-3_{E′}(T) ∩ E_K(T)| / 3."""
    return len(set(map(int, top3_tam)) & set(map(int, E_K))) / 3.0


# ------------------------------------------------------------------ V6
def spearman_matris(S):
    """V6: S (n_çift, 8) s_k değerleri; her (k, l) için iki değeri de olan çiftlerde Spearman r_S (eşitlerde ortalama sıra).
    Dönüş (r (8, 8), n (8, 8), |r| > 0,8 çiftleri [(k, l, r)] 1 tabanlı)."""
    S = np.asarray(S, float); K = S.shape[1]
    r = np.full((K, K), np.nan); n = np.zeros((K, K), int)
    for k in range(K):
        for l in range(K):
            m = np.isfinite(S[:, k]) & np.isfinite(S[:, l])
            n[k, l] = int(m.sum())
            if m.sum() >= 3 and np.ptp(S[m, k]) > 0 and np.ptp(S[m, l]) > 0:
                r[k, l] = float(spearmanr(S[m, k], S[m, l]).statistic) if k != l else 1.0
    yuksek = [(k + 1, l + 1, float(r[k, l])) for k in range(K) for l in range(k + 1, K)
              if np.isfinite(r[k, l]) and abs(r[k, l]) > SPEARMAN_ESIK]
    return r, n, yuksek


# ------------------------------------------------------------------ V7
def v7_ozet(taular, jaccardlar):
    """V7: 20 tekrarın τb ve Top-3 Jaccard'ı → ortanca (ozet.json) ve dağılım (F11)."""
    t = np.asarray(taular, float); j = np.asarray(jaccardlar, float)
    return {"tau_ortanca": float(np.nanmedian(t)), "jaccard_ortanca": float(np.nanmedian(j)),
            "tau": t.tolist(), "jaccard": j.tolist()}


# ------------------------------------------------------------------ V8
def ablasyon(s, z, w, kapi):
    """V8: kategori k çıkarılınca (s_k ve ζ_k null) P ile tam P arasında τb, k = 1…8. Dönüş (8,)."""
    s = np.asarray(s, float); z = np.asarray(z, float)
    P0, _ = Pn.P_Q(s, z, w, kapi)
    out = np.full(s.shape[1], np.nan)
    for k in range(s.shape[1]):
        s2 = s.copy(); z2 = z.copy(); s2[:, k] = np.nan; z2[:, k] = np.nan
        Pk, _ = Pn.P_Q(s2, z2, w, kapi)
        out[k] = Pn.kendall_tau_b(P0, Pk)
    return out


# ------------------------------------------------------------------ V9
def holm(p, alfa=ALFA):
    """V9 Holm [49]: p₍₁₎ ≤ … ≤ p₍M₎; H₍i₎ reddedilir ⇔ her j ≤ i için p₍j₎ ≤ α₀/(M − j + 1).
    Dönüş (red (M,) bool, düzeltilmiş p (M,))."""
    p = np.asarray(p, float); M = len(p)
    o = np.argsort(p, kind="stable")
    esik = alfa / (M - np.arange(M))
    gec = p[o] <= esik
    red_s = np.cumprod(gec).astype(bool)
    red = np.zeros(M, bool); red[o] = red_s
    duz_s = np.minimum(1.0, np.maximum.accumulate(p[o] * (M - np.arange(M))))
    duz = np.empty(M); duz[o] = duz_s
    return red, duz


# ------------------------------------------------------------------ V10
def v10(uzman_sira, bizim_P):
    """V10 (yalnız rapor): Lambert & Reimold sırası ile Geology P'si arasında Spearman r_S; hipotez testi yok.
    uzman_sira: 1 = en iyi; P büyük = iyi → r_S, P sırasına (1 = en büyük P) göre hesaplanır."""
    u = np.asarray(uzman_sira, float); P = np.asarray(bizim_P, float)
    m = np.isfinite(u) & np.isfinite(P)
    return float(spearmanr(u[m], -P[m]).statistic)
''', encoding="utf-8")
(KOD / "testler" / "test_dogrula.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 8.3 V1–V10 istatistik fonksiyonları."""
import numpy as np
import pytest
from scipy.stats import chi2, mannwhitneyu, spearmanr

import dogrula as D
import puan as Pn


def test_pi_ve_K14():
    P = np.array([0.1, 0.5, 0.5, 0.9, np.nan])
    assert D.pi_degeri(P, 0.5) == pytest.approx(3 / 5)
    assert D.pi_degeri(P, 0.95) == pytest.approx(4 / 5)
    assert D.pi_degeri(P, 0.5, kapidan_kaldi=True) == 0.0


def test_fisher_elle():
    pi = np.full(11, 0.5); n = 1000
    X, p = D.fisher_v1(pi, n)
    assert X == pytest.approx(-2 * 11 * np.log(0.5 + 1e-3)) and p == pytest.approx(chi2.sf(X, 22))
    X2, p2 = D.fisher_v2(np.full(22, 0.5), n)
    assert X2 == pytest.approx(-2 * 22 * np.log(0.5 + 1e-3))


def test_fisher_H0_altinda_duzgun():
    # Π ~ U(0,1) iken p ≈ U(0,1): ortalama 0,5, P(p < 0,05) ≈ 0,05 (büyük |E′|)
    rng = np.random.default_rng(1)
    p1 = np.array([D.fisher_v1(rng.random(11), 10 ** 7)[1] for _ in range(4000)])
    p2 = np.array([D.fisher_v2(rng.random(22), 10 ** 7)[1] for _ in range(4000)])
    for p in (p1, p2):
        assert abs(p.mean() - 0.5) < 0.02 and abs(np.mean(p < 0.05) - 0.05) < 0.012


def test_fisher_yon():
    # V1: analoglar üstte (Π büyük) → p küçük; V2: negatif kontroller altta (Π küçük) → X²₋ büyük → p küçük
    assert D.fisher_v1(np.full(11, 0.99), 10 ** 6)[1] < 1e-6
    assert D.fisher_v2(np.full(22, 0.01), 10 ** 6)[1] < 1e-6


def test_auc_kaba_kuvvet_ve_mw():
    rng = np.random.default_rng(2)
    a = rng.integers(0, 10, 11).astype(float); b = rng.integers(0, 10, 3000).astype(float)
    U = sum((x > y) + 0.5 * (x == y) for x in a for y in b)
    assert D.auc(a, b) == pytest.approx(U / (11 * 3000))
    assert D.auc(a, b) * 11 * 3000 == pytest.approx(mannwhitneyu(a, b).statistic)


def test_v3_tekrar_ve_GA():
    rng = np.random.default_rng(3)
    a = rng.random(11) + 0.3; b = rng.random(11000)
    r1, r2 = D.v3(a, b), D.v3(a, b)
    assert r1 == r2
    assert r1["GA95"][0] <= r1["AUC"] <= r1["GA95"][1] and r1["p"] < 0.05


def test_b_prime_ve_hedefler():
    B = D.b_prime(50000, 11)
    assert B.shape == (11, 1000) and all(len(set(r)) == 1000 for r in B)
    np.testing.assert_array_equal(B, D.b_prime(50000, 11))
    ay, ma = D.rastgele_hedefler(95000, 361000, "V5")
    assert len(ay) == len(set(ay)) == 100 and len(ma) == 100
    np.testing.assert_array_equal(ay, D.rastgele_hedefler(95000, 361000, "V5")[0])
    assert not np.array_equal(ay, D.rastgele_hedefler(95000, 361000, "V2")[0])   # farklı alt tohum → farklı küme


def test_v2_sec():
    rng = np.random.default_rng(5)
    o = rng.random(5000); t = rng.random(5000)
    oi, ti = D.v2_sec(o, t, 11)
    assert len(set(oi)) == 11 and np.all(o[oi] >= 0.9) and np.all(t[ti] >= 0.9)
    np.testing.assert_array_equal(oi, D.v2_sec(o, t, 11)[0])


def test_recall():
    assert D.recall([1, 2, 3], [3, 2, 9, 10]) == pytest.approx(2 / 3)
    assert D.recall([1, 2, 3], [1, 2, 3]) == 1.0


def test_spearman_matris():
    rng = np.random.default_rng(6)
    x = rng.random(500)
    S = np.column_stack([x, x ** 3, rng.random(500), -x, x, x, x, x])
    S[:50, 2] = np.nan
    r, n, yuksek = D.spearman_matris(S)
    assert r[0, 1] == pytest.approx(1) and r[0, 3] == pytest.approx(-1) and n[0, 2] == 450
    m = np.isfinite(S[:, 2])
    assert r[0, 2] == pytest.approx(spearmanr(S[m, 0], S[m, 2]).statistic)
    assert (1, 2, pytest.approx(1.0)) in [(k, l, v) for k, l, v in yuksek] and all(k != 3 and l != 3 for k, l, _ in yuksek)


def test_holm_elle():
    red, duz = D.holm([0.01, 0.04, 0.03, 0.005])
    np.testing.assert_array_equal(red, [True, False, False, True])
    np.testing.assert_allclose(duz, [0.03, 0.06, 0.06, 0.02])


def test_ablasyon_sabit_kategori():
    rng = np.random.default_rng(7)
    s = rng.random((300, 8)); s[:, 4] = 0.5
    z = rng.random((300, 8))
    t = D.ablasyon(s, z, Pn.kademeli_agirlik([5, 6, 8]), np.ones(300, bool))
    assert t[4] == pytest.approx(1.0) and np.all(t[[5, 7]] < 1)


def test_v4_v7_ozet():
    o = D.v4_ozet([[0.5, np.nan], [0.2, 0.3]], [[0.4, 0.1], [0.2, 0.5]], [0.95, 0.8])
    assert o["ortalama_fark"] == pytest.approx([0.05, 0.2]) and o["tau_ort"] == pytest.approx(0.875) and o["K4_tetiklendi"]
    v = D.v7_ozet([0.9, 0.8, 1.0], [1, 0.5, 0.5])
    assert v["tau_ortanca"] == 0.9 and v["jaccard_ortanca"] == 0.5


def test_v10_yon():
    assert D.v10([1, 2, 3, 4], [0.9, 0.7, 0.5, 0.1]) == pytest.approx(1.0)
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
| 4 | P_f,B: "rastgele piksel" yerine alanca düzgün rastgele noktaların piksel değerleri (≤ 10⁶, tohum 20261113) | 5.2 | onaylı (Sude, 12:17) | "area-uniform random sample"; neden: enlem-boylam pikseli kutbu 1/cos φ ağırlıklandırır |
| 5 | Dünya Tmax = aylık gündüz LST'nin en büyüğü; T̄ = aylık (gündüz+gece)/2 yıllık ortalaması; Tgece = aylık gece yıllık ortalaması | 6.5 | onaylı (Sude, 12:17) | dayanak 6.5 "Aqua öğleden sonra geçişi maksimuma yakın" — veri MYD11C3 = Aqua (kaynak dosya MYD11C3.A2023…hdf; belge D1); Aqua ~13:30 / ~01:30 (NASA MODIS teknik sayfası). Sude'nin 'Terra ~10:30' düzeltmesi uygulanmadı: veri Terra değil |
| 6 | I⊕ aylık; C₁ = 0 ve ΔTg ≤ 0 ayları ortalamaya girmez (ΔTg ≤ 0 NaN, assert ve sayılar kayıtta) | 6.5 | ΔTg ≤ 0: onaylı (Sude); yıllık ortalama belgedeki gibi kalır | δ⊙: Michalsky 1988 (Astronomical Almanac düşük duyarlıklı algoritma) |
| 7 | ASTER MI her bandın 12 aylık ortalamasından; ortalamaya yalnız geçerli aylar (0 = yok → NaN) girer | 6.4 | onaylı (Sude, 12:17) | — |
| 8 | Ay aydınlanması: |φ| ≥ 65° PGDA ve < 65° Berger hücreleri kendi kapsamlarında ayrı sıralanır | 6.8 | onaylı (Sude, 12:17) | iki büyüklük farklı birimde; Limitations'a bir cümle |
| 9 | Sıfır kuralında kara hücresi = MCD12C1 kara payı ≥ 0,5 | 6.6 | onaylı, proje kararı (Sude, 12:17) | kar/buz < 0,5 ile aynı çoğunluk mantığı |
| 10 | Ay π⁺: hücrenin alt örneklerinin ≥ yarısında ice_depth ≠ −999 ise hücre pozitif | 6.6 | onaylı, proje kararı (Sude, 12:17) | — |

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
| 18 | V1: 11 çiftin hepsi kaynakla tutuyor; JETT5 NTRS kimliği doğrulanamadı → makalede yalnız USGS kaynağıyla atıf; Dumont Dunes 11 Mayıs haber tarihi; JETT1 kesin tarih yok | 9.3 | onaylı (Sude) |

## 5. Implementation (yöntem aynı; makale Bölüm 8 için)

- Hücre ortalaması (4.4): hücreden ince katmanda hücre içinde s × s alt nokta (piksel kenarı başına ≥ 2, s ≤ 10) → alan ağırlıklı piksel ortalaması.
- Vektör jeoloji (4.4): her pencerede hücre başına 5 × 5 nokta, poligon içi testi (shapely, hazırlanmış poligon). GLiM rasterleştirilmedi.
- Topografya (6.1): "2 hücre dışarıdan" her ölçekte → DEM 8 ince hücre dışından okunur (2 km'de 2 blok).
- F⁻¹ (5.1): ECDF genelleştirilmiş tersi, k = ⌈n(2m − 1)/2M⌉ tam sayı aritmetiğiyle.
- SW doğrultuları orta nokta θ_j = −π/2 + (j − ½)π/Mθ.
- Diviner PRP hücreye: en yakın üçgen merkezi, ortanca komşu aralığının 3 katı eşik (proje kararı, onaylı Sude 12:17), arama eşikle sınırlı.
- H₀: GUDHI CubicalComplex; bağımsız union-find (8-komşuluk) ile 203 pencerede birebir aynı.
- Berger f(φ): 0,001° tablo + doğrusal ara değer (ölçülen en büyük hata 1,2e-9).

## 6. Bekleyen ölçüm (Sude Limitations cümlesini yazacak)

- I⊕: ΔTg < 1 K olan geçerli ayı bulunan piksel oranı 0,329 (2 913 886 / 8 638 888). I⊕ yüzdelikleri: %1 0,0112; %50 0,0541; %99 0,5152; %99,9 3,9962 (`kayit\iarti_teshis.json`).
- Ek ölçümler (en büyük ayın yıllık toplamdaki payı; |u_ort − u_ortanca|; en büyük farkın 10 pikseli) → `kayit\iarti_olcum.json`.

## 7. Son gönderimden sonra eklenenler (12:17'den itibaren)

| # | Ne | Belge bölümü | Durum | Not |
|---|---|---|---|---|
| 19 | Madde 5 "Terra ~10:30" düzeltmesi önerildi, uygulanmadı: veri MYD11C3 (Aqua, ~13:30 / ~01:30) | 6.5, D1 | Sude'ye bildirildi | Limitations'taki I⊕ cümlesinde Terra etkisi yazılmaz |
| 20 | K-1: kapılarda W° "kara hücresi" = kara payı ≥ 0,5 (madde 9 ile aynı) | 7.2 | onaylı, proje kararı (Sude) | — |
| 21 | K-2: Pv için 12 aylık ASTER NDVI → yıllık ortalama (geçerli aylar) → Pv; pencerede **ortanca** (belge 7.2 açıkça "medyan_{W°} P_v" diyor) | 7.2 | onaylı (Sude) | yıllık en büyük kullanılmaz (yağmur sonrası yeşeren çöller) |
| 22 | K-3: Geology kapısında kar/buz payı = W° üzerinde ortalama | 7.2 | onaylı (Sude) | alan payının beklenen değeri |
| 23 | K-4: hedefte verisi olmayan kategori iki taraftan da çıkar; "en fazla 1 eksik" yalnız hedefin verisi olan kategoriler üzerinden | 7.2 | onaylı (Sude) | — |
| 24 | K-5: X'in leave-one-out'u yalnız V1'in kendi Geology satırlarında; diğer hedeflerde X = 7 Geology çiftinin hepsiyle | 7.2, D7 | onaylı (Sude) | — |
| 25 | Gözlem: Ice kapısı (G_buz) yalnız permafrost ortalaması; kar/buz < 0,5 şartı yalnız Geology'de. Grönland/Antarktika içi (kar/buz ≥ 0,5 hücreleri sıfır kuralında hesap dışı) Ice'ta "could not be checked" ile geçer (belge 7.2 kural 2) | 7.2 | kayda yazıldı, değişiklik yok | sonuç tablosunda görünecek |

## 8. Açık sorular (onele / puan / teorem / dogrula) — 12:25 soruldu, 12:33 cevaplandı

Hepsi KAYNAK YOK — onay gerekir. Öneri İrem/Claude'un; karar ekibin.

| # | Soru | Belge | Öneri | Karar |
|---|---|---|---|---|
| Q-1 | z'de MAD = 0 ise | 7.1 | O bileşende Rousseeuw–Croux Qn [96]; Qn de 0 ise bileşen çıkar | **Değişti (Sude):** Qn kullanılmaz (Qn'nin de dayanma sınırı %50, aynı durumda 0 çıkar); MAD = 0 olan bileşen z'den çıkar, kayda yazılır. z yalnız ön elemede; kaybı V5 ölçer |
| Q-2 | Kategori şampiyonu hangi kümeden | 7.4 | E_K(T, g) içindeki uygun adaylar; k = 2 için son 30 aday | onaylı (Sude) |
| Q-3 | V2 "sınıf 2 ≥ %90" düzeyi | 8.3, D6 | Pencere ortalaması MCD12C1 sınıf payı ≥ %90 | onaylı (Sude) |
| Q-4 | V4/V5 "rastgele 200 hedef" cismi | 8.3 | 100 Ay + 100 Mars ızgara penceresi, tohum 20261113 (alt tohum V4/V5) | onaylı (Sude) |
| Q-5 | V5 tam sıralama topoloji dahil mi | 8.3, 7.4 | Topolojisiz (V1 gibi), iki taraf aynı puan | onaylı (Sude) |
| Q-6 | V7 gürültü nereye | 8.3 | Yalnız hedef + 20 komşusunun DEM'i; Dünya tarafı sabit; liste hedeflerinin hepsi | onaylı (Sude) |
| Q-7 | V6 "bütün (E, T) çiftleri" | 8.3 | Liste hedefleri × E_K adayları (8 s_k'nin hepsi olan) | onaylı (Sude) |
| Q-8 | ε* ikiye bölme hassasiyeti | 8.1 | 0,01 m; aralık σv'den başlayıp ikiye katlanır (≤ 10⁵ m) | onaylı (Sude); sınıra kadar bulunamazsa kayda "bulunamadı" |

## 9. Dış inceleme (12:33) — maddeler ve durumu

| # | Bulgu | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 26 | Makale v0.5'te "I⊕ = C₁/ΔT (MOD11C3 in v1.0)", "Aqua replaces Terra", "Replaces MOD11C3 (Terra) of v1.0" yazıyor; belge D1 ise bunu kaynakça hatası diyor. Bugünkü koşu MYD11C3 (testle doğrulandı). | D1, D12 | Hayır | Makaledeki sonuçlar v1.2 koşusundan gelecek; D12 gereği v1.0 karşılaştırma cümleleri makaleden çıkar (Emir/Sude) |
| 27 | Aqua gece geçişi 01:30, günlük minimum gün doğumuna yakın → ΔTg = T₁₃:₃₀ − T₀₁:₃₀ < T_max − T_min → I⊕ olduğundan büyük | 6.5 | Hayır | Limitations cümlesi sapmanın yönünü söyler (Sude) |
| 28 | Puan sıra tabanlı: her yerde aynı oranda sapma sırayı değiştirmez; etkiyi yalnız yerden yere değişen sapma yapar (tarama açısı, enlem, açık gün seçimi) | 5.2, 6.5 | Hayır | Limitations cümlesi "olduğundan büyük" yerine bunu söyler (Sude) |
| 29 | I⊕ yıllık değeri: oranların ortalaması (belge) küçük paydalı aylara duyarlı. **Karar (Sude, 12:57; D8'den önce, sonuçlara bakılmadan):** ortalamaların oranı, I⊕ = Σ C₁(1 − α) / Σ ΔTg, toplam C₁ > 0, ΔTg > 0 (ve α var) olan geçerli aylar üzerinden. Cebirsel olarak aylık I⊕'nin ΔTg ağırlıklı ortalaması; ΔTg ≈ 0 olan ay yıllık değeri ele geçiremez. MI'deki "önce ortalama" (madde 7) ile tutarlı | 6.5 | Evet: yalnız ozellik_diger yıllık I⊕ (`I_arti_yillik`) ve ara\cmg_iarti.npy yeniden üretildi; sınır (≤ 82,1) aynı | uygulandı; gerekçe büyüklüğü `kayit\iarti_olcum.json` (|u_eski − u_yeni|: ortanca, %95, en büyük); Sude gerekçe cümlesini yazdı (13:14): sıra farkı ortanca 0,021, %95 0,228 |
| 30 | Pv'de ortanca: Pv NDVI'nin azalmayan fonksiyonu → medyan Pv < 0,5 ⇔ medyan NDVI < 0,2 + 0,3√0,5 ≈ 0,412; belgedeki "NDVI < 0,41" cümlesi tam doğru | 7.2 | Hayır | Method'a gerekçe olarak (Emir) |
| 31 | Buz tabakası pencereleri Ice kapısından "could not be checked" geçer, s₆ tanımsız, ağırlık termal/aydınlanmaya kayar → Ay kutup hedeflerinde üst sıralara çıkabilir. Kavramsal soru: buz tabakası "donmuş zemin" mi? | 6.6, 7.2 | Şimdi hayır | Koşudan sonra Ice Top-3/ilk 10'da "could not be checked" oranı ozet.json'a otomatik yazılır; yorum ekip |
| 32 | Madde 8 (PGDA/Berger) gerekçesi: bu "cisim içi sıra"nın kendisi değil; Ay iki referansa bölünüyor, 65°'de süreksizlik (64,9° ve 65,1° çok farklı sıra alabilir) | 6.8 | Hayır | Limitations cümlesi süreksizliği açıkça söyler (Sude) |
| 33 | Sude'nin numaralandırması kayıttakiyle farklı ("6. MI" = madde 7, "7. aydınlanma" = 8, "8." = 9 ve 10) | — | Hayır | Bu belgede numaralar düzeltilmiş halde |

## 10. teorem.py (12:45)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 34 | Lemma 1 (a)–(e), Ψ₁, Ψ₂ ve Teorem 1 sayısal testten geçti (rastgele DEM + |e| ≤ ε; sınırlar her tekrarda tuttu; 0,9·ε* gürültüde s₁ sırası değişmedi). **Erken uyarı:** sentetik arazide ε*₁ ≈ 0,02–2 mm (σv = 7,17 m). Ψ₁'i H₄ terimi büyütüyor (IQR_T(H₄) ~1e-5). Gerçek dağılım D6/uzun koşuda (F15) | 8.1 | Hayır | Emir: "güvenli hata yarıçapı ölçülür ve raporlanır" cümlesini büyüklükten bağımsız doğru kalacak biçimde yazar; sayılar ozet.json'dan |
| 35 | ε* < 0,01 m (Q-8 hassasiyeti) ise kayda "0,01 m'den küçük" yazılır (0 yalnız gerçek eşitlikte) | 8.1, Q-8 | Hayır (kayıt biçimi) | — |

## 11. onele.py (12:55)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 36 | Q-1 uygulandı: MAD = 0 olan z bileşeni çıkar; hangi bileşenin çıktığı `ozet.json`'a yazılır. **Olası durum:** n↓ ve n↑ sayım; Dünya pencerelerinin yarısından fazlasında aynı değer (ör. 0) çıkarsa MAD = 0 olur ve bileşen düşer. Sonuç P4'te görülür | 7.1, Q-1 | Hayır (karar onaylı) | makalede "z'den çıkan bileşenler" cümlesi ozet.json'dan |
| 37 | Okuma (formül aynı): z'si eksik (NaN) Dünya penceresi KD-ağacına girmez, sayısı kayda yazılır. Bu yalnız DEM'i eksik pencerelerde olur; bunlar topoloji kategorisi olmadığı için zaten uygun değil (7.2). Aynı uzaklıkta pencere kimliği küçük olan önce | 7.1, 7.2 | Hayır | kayda yazıldı |
| 38 | **Q-9 (onaylı, proje kararı, Sude 12:51):** V5'te {100, 200, 400, 800} hiçbiri ortalama recall ≥ 0,9 sağlamazsa Kön = 800 (denenenlerin en büyüğü), koşu durmaz. Listeye yeni değer eklenmez (sonuçtan sonra ayarı genişletmek önceden kilitleme ilkesine aykırı) | 7.1, 8.3 V5 | onele.kon_sec → (K, eşik sağlandı mı) | makaleye "recall did not reach 0.9 (mean ± CI)" sınırlılığı; ozet.json'da bayrak |
| 39 | **Q-10 (onaylı, proje kararı, Sude 12:51):** şart ortalama recall'a (r̄) uygulanır. GA = r̄ ± 1,96 s_d/√200 (s_d örneklem std, ddof = 1) hesaplanır, ozet.json'a yazılır; r̄ ≥ 0,9 ama alt uç < 0,9 ise makalede tek cümleyle belirtilir | 8.3 V5 | onele.recall_ozet | — |
| 40 | Hedef penceresinin z'sinde (tutulan bileşende) NaN varsa ön eleme yapılmaz, hata verir (sessiz karar yok). Ay/Mars DEM'leri küresel tam olduğu için beklenmiyor; olursa pilotta görülür | 7.1 | Hayır | kayda yazıldı |

## 12. I⊕ formülü uygulaması (13:10)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 41 | **(1 − α) çarpanı kaldı.** Sude'nin notunda "21 sette Dünya albedosu yok, çarpan alınmayacak" deniyor; ama belge 6.5'teki formül I⊕ = C₁(1 − α)/ΔTg, veri tablosunda MCD43C3 beyaz gök albedo (E6, 2023'ün her ayının 15'i) var, set temiz\ altında (P0 24/24 PASS) ve kod 13 Kasım'dan beri çarpanı kullanıyor. Çarpanı atmak belgeden sapma olurdu. v1.0'daki seçim gerekçe olamaz (D12: eski sürümle karşılaştırma yok) | 6.5, 10.1 | Hayır (zaten öyleydi) | Sude'ye bildirildi; makalede formül belge 6.5'teki gibi (1 − α)'lı yazılır, albedo kaynağı [67] |
| 42 | Yalnız yıllık I⊕ değişti; Tmax, T̄, Tgece, MI dosyaları yeniden yazılmadı (değiştirilmedikleri kontrol edildi). I⊕'nin cisim içi sıra referansı (ara\ref_dunya_iarti.npy) silinip yeni değerden üretilir | 6.5, 5.2 | iç iş | — |

## 13. puan.py (13:25)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 43 | **Q-11 (onaylı, proje kararı, Sude 13:14; öneri değişti):** ζ_k'nın paydası (R_k uzaklıklarının ortancası) 0 ise d = 0 → **ζ = 1**, d > 0 → ζ = +∞. Payda 0 iken referansların yarıdan fazlası hedefe tam eşit uzaklıktadır; d = 0 olan pencere istisnai değil, tipik bir referans kadar yakındır (s_k'nin ½ eşitlik sayımıyla tutarlı). Paydası 0 olan aday sayısı kayda/ozet.json'a | 5.4, 7.4 | Evet: puan.zeta_k (uygulandı) | — |
| 44 | **Q-12 (onaylı, proje kararı, Sude 13:14):** 100 km kuralı sitedeki ilk 10 listesine de uygulanır; Top-3 = ilk 10'un ilk üçü | 7.4, 17.6 | Yalnız kos.py | — |
| 45 | **Q-13 (onaylı, proje kararı, Sude 13:14):** τb ana koşunun son 30 adayı üzerinden; alternatif şemada (eşit ağırlık, geometrik ortalama) aynı 30 aday yeniden puanlanır, iki sıralama aynı küme üzerinde karşılaştırılır. Top-3 Jaccard'da üç sıralamaya da 100 km kuralı | 7.4 | Yalnız kos.py | — |
| 46 | Okuma: eşitlik kırıcı zinciri P azalan → Q artan → **pencere kimliği artan** (belge 8.3 "tekrar koşuda aynı" şartı; Q de eşitse sıra yine deterministik) | 7.4, 8.3 | Hayır | kayda yazıldı |
| 47 | Okuma: "en az 100 km" ≥ 100 km (tam 100 km olan aday alınır) | 7.4 | Hayır | kayda yazıldı |
| 48 | Test tanımı: 8.2 "sıra biçimi N = 5, (1, 2, 2, 3, 4)" satırı formül sınaması; |R_k| < 100 → null kuralı bu testte devre dışı (en_az = 1), kural ayrı testte (8.3 "99 / 100") | 5.4, 8.2 | Hayır | T5 tablosunda not |
| 49 | Görev ağırlıkları belge 7.3 formülünden (0,80/m, 0,20/(n − m)) üretilir; tablo testle doğrulandı. kos.py çalışırken ayar.json'daki ağırlıklarla birebir aynı olduğunu assert eder | 7.3 | Hayır | — |
| 50 | puan.py sabitleri ayar.json'dan okunur ve belge 8.4 ile assert edilir: referans.en_kucuk 100, siralama.top3_en_az_km 100, topoloji.aday_sayisi 30, agirlik.ana_pay 0,8; ana kategoriler belge 7.3 tablosuyla testte karşılaştırıldı | 8.4, 7.3 | Hayır | — |

## 14. dogrula.py (13:40)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 51 | V1–V3, V6, V9 formülleri belge 8.3'teki gibi; H₀ altında (Π ~ U(0, 1)) Fisher p-değerinin düzgün dağıldığı 4000 tekrarlı testle doğrulandı. V1 kapıdan kalan analog Π = 0 (K14). V3 p-değeri tek yönlü Mann–Whitney [63] | 8.3 | Hayır | — |
| 52 | Okuma: V3 %95 GA = 2000 bootstrap, A ve B′ ayrı ayrı yerine koyarak yeniden örneklenir, yüzdelik yöntemi (Efron & Tibshirani [28]); alt tohum V3. B′ hedef başına ayrı rastgele akış | 8.3 V3 | Hayır | kayda yazıldı |
| 53 | Okuma: V2'de aynı pencere iki çiftte seçilmez (22 farklı pencere); alt tohum V2 | 8.3 V2, D6 | Hayır | kayda yazıldı |
| 54 | **Q-14 (KAYNAK YOK — onay gerekir):** Q-4 "alt tohum V4/V5" diyor; ayar.json'da V5 var ama V4 hedefleri için alt tohum yok (`V4_ikinci_R` = 4 ikinci referans örneği için). **Öneri:** ayar.json'a `alt_tohum.V4_hedef = 6` (boş numara) eklenir, D8'de kilitlenir; V4 ve V5'in 200 hedefi ayrı kümeler olur | 8.3 V4, Q-4 | Yalnız ayar.json + kos.py | ekip kararı |
| 55 | **Q-15 (KAYNAK YOK — onay gerekir):** V4'teki "Top-3 sıralamaları arasındaki Kendall τb" hangi kümede? Üç elemanlı iki listede τb ancak elemanlar aynıysa tanımlı. **Öneri:** rastgele 200 hedefte τb, E_K adaylarının R ve R′ ile hesaplanan iki topolojisiz sıralaması arasında (V5/Q-5 ile aynı küme); Katman A–B karşılaştırmasında liste hedeflerinin son 30 adayı üzerinden (Q-13 ile aynı). Top-3 değişimi ayrıca Jaccard ile yazılır | 8.3 V4 | Yalnız kos.py | ekip kararı |
''', encoding="utf-8")
at = json.load(open(KOD / "ayar.json", encoding="utf-8"))["parametreler"]["alt_tohum"]["deger"]
print("ayar.json alt_tohum:", at)
for k in ("V2", "V3", "V5"): assert k in at, k
yol = KOD / "FONKSIYONLAR.md"; metin = yol.read_text(encoding="utf-8")
bas, son = "<!-- dogrula.py -->", "<!-- /dogrula.py -->"
blok = bas + "\n## dogrula.py\n" + "\n".join("- " + s for s in [
    "8.3 V1 Π_a → `dogrula.pi_degeri`; X² ve p → `dogrula.fisher_v1`",
    "8.3 V2 X²₋ ve p → `dogrula.fisher_v2`; çift seçimi (Q-3) → `dogrula.v2_sec`",
    "8.3 V3 U, AUC → `dogrula.auc`; Mann–Whitney p, bootstrap GA → `dogrula.v3`; B′ → `dogrula.b_prime`",
    "8.3 V4 → `dogrula.v4_ozet`; V4/V5 hedefleri (Q-4) → `dogrula.rastgele_hedefler`",
    "8.3 V5 recall → `dogrula.recall` (r̄ ± GA ve Kön: `onele.recall_ozet`, `onele.kon_sec`)",
    "8.3 V6 r_S matrisi → `dogrula.spearman_matris`",
    "8.3 V7 τb, J → `puan.kendall_tau_b`, `puan.jaccard`; özet → `dogrula.v7_ozet`",
    "8.3 V8 ablasyon → `dogrula.ablasyon`",
    "8.3 V9 Holm → `dogrula.holm`",
    "8.3 V10 r_S → `dogrula.v10`"]) + "\n" + son
metin = (metin.split(bas)[0] + blok + metin.split(son)[1]) if bas in metin else (metin.rstrip() + "\n\n" + blok + "\n")
yol.write_text(metin, encoding="utf-8")
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | dogrula.py: V1–V10 fonksiyonları; Fisher H₀ altında düzgün (testle); V3 bootstrap okuması; V2 farklı pencereler | Q-14 (V4 hedef alt tohumu), Q-15 (V4 τb kümesi) ekibe | etkisi: MAKALEYİ ETKİLER 51–55\n")
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_dogrula", "testler/test_dogrula.py")
