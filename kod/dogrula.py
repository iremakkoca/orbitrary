# Developed with assistance from Claude (Anthropic).
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


def tau_ortak(kimlik1, P1, kimlik2, P2):
    """Q-15 (Sude): iki sıralama arasında τb yalnız ortak aday kümesinde (kimlik kesişimi). Dönüş (τb, kesişim boyutu)."""
    k1 = np.asarray(kimlik1); k2 = np.asarray(kimlik2)
    ortak, i1, i2 = np.intersect1d(k1, k2, assume_unique=True, return_indices=True)
    return Pn.kendall_tau_b(np.asarray(P1, float)[i1], np.asarray(P2, float)[i2]), int(len(ortak))


def v4_ozet(s, s2, tau, kesisim=None):
    """V4: ortalama |s_k − s′_k| (kategori başına, NaN çiftler dışarıda) ve τb. Belge K4: τ̄b (ortalama) < 0,9 →
    |R| iki katı, bir kez. Q-15: ozet.json'a τb ortancası ve %5–%95 aralığı; kesişim boyutları kayda."""
    s = np.asarray(s, float); s2 = np.asarray(s2, float)
    with np.errstate(invalid="ignore"):
        fark = np.nanmean(np.abs(s - s2), axis=0)
    ta = np.asarray(tau, float)
    t = float(np.nanmean(ta))
    o = {"ortalama_fark": [None if np.isnan(f) else float(f) for f in np.atleast_1d(fark)], "tau_ort": t,
         "tau_ortanca": float(np.nanmedian(ta)), "tau_y5": float(np.nanpercentile(ta, 5)),
         "tau_y95": float(np.nanpercentile(ta, 95)), "K4_tetiklendi": bool(t < V4_TAU_ESIK)}
    if kesisim is not None:
        k = np.asarray(kesisim, int)
        o["kesisim"] = {"en_kucuk": int(k.min()), "ortanca": float(np.median(k)), "en_buyuk": int(k.max())}
    return o


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
