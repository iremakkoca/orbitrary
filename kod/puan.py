# Developed with assistance from Claude (Anthropic).
"""Belge 5.4, 7.3–7.4: yüzdelik kalibrasyon s_k, eşitlik kırıcı ζ_k, P_g, Q_g, sıralama, aralıklı liste (Top-3, 100 km),
kategori şampiyonları, kademeli ağırlık, duyarlılık (eşit ağırlık, ağırlıklı geometrik ortalama, Kendall τb, Jaccard).

Bütün fonksiyonlar saftır: girdiler uzaklık / puan dizileri, ağırlık vektörü ve maskeler. Hangi adayın, hangi referansın,
hangi görevin kullanılacağı kos.py'nin işidir.

Onaylı kararlar: Q-2 (Sude) şampiyon E_K(T, g) içindeki uygun adaylardan, k = 2 için son 30 adaydan seçilir (maske kos.py'den).
Eşitlik kırıcı zinciri: P azalan → Q artan → pencere kimliği artan (belge 7.4 "tekrar koşuda aynı" şartı için son halka).
"""
import math

import numpy as np
from scipy.stats import kendalltau

import ayar as A

N_KATEGORI = 8
EN_AZ_REFERANS = int(A.ayar("referans.en_kucuk"))           # belge 5.4: |R_k(T, E)| < 100 → null
TOP3_EN_AZ_KM = float(A.ayar("siralama.top3_en_az_km"))     # belge 7.4 / 8.4: en az 100 km (proje kararı); Q-12: ilk 10'a da
TOPOLOJI_ADAY = int(A.ayar("topoloji.aday_sayisi"))         # belge 7.4 / 8.4: topoloji ilk 30 adayda
ANA_PAY = float(A.ayar("agirlik.ana_pay"))                  # belge 7.3: kademeli 80/20
assert (EN_AZ_REFERANS, TOP3_EN_AZ_KM, TOPOLOJI_ADAY, ANA_PAY) == (100, 100.0, 30, 0.8)  # belge 8.4


# ------------------------------------------------------------------ 7.3 ağırlık
def kademeli_agirlik(ana, n=N_KATEGORI):
    """Belge 7.3: w_k = 0,80/m (k ∈ A(g)), 0,20/(n − m) (diğer). ana: 1 tabanlı kategori numaraları. Boşsa eşit (Genel)."""
    ana = sorted(set(int(k) for k in ana))
    assert all(1 <= k <= n for k in ana)
    m = len(ana)
    if m == 0 or m == n:
        return np.full(n, 1.0 / n)
    w = np.full(n, (1 - ANA_PAY) / (n - m))
    w[[k - 1 for k in ana]] = ANA_PAY / m
    return w


def gorev_agirligi(gorev, sema="ana"):
    """Belge 7.3: gorev ∈ {None/'genel', 'mobility', 'geology', 'ice', 'astro'} (ayar.json agirlik.ana_kategoriler);
    sema 'ana' (80/20) ya da 'esit' (1/8). Geometrik ortalama birleştirmedir, ağırlığı 'ana' ile aynıdır."""
    assert sema in ("ana", "esit"), sema
    if sema == "esit" or gorev in (None, "genel"):
        return np.full(N_KATEGORI, 1.0 / N_KATEGORI)
    return kademeli_agirlik(A.ayar("agirlik.ana_kategoriler")[gorev])


def etkili_agirlik(w, mevcut):
    """Belge 7.3 'eksik kategori': null kategori düşer, kalan ağırlıklar toplamına bölünür."""
    w = np.asarray(w, float); mevcut = np.asarray(mevcut, bool)
    t = w[mevcut].sum()
    return np.where(mevcut, w / t, 0.0) if t > 0 else np.full(w.shape, np.nan)


# ------------------------------------------------------------------ 5.4 s_k ve ζ_k
def _ref(d_ref):
    d = np.asarray(d_ref, float)
    return np.sort(d[np.isfinite(d)])


def s_k(d_aday, d_ref, ref_konum=None, en_az=EN_AZ_REFERANS):
    """Belge 5.4: s_k(E) = (#{d(E′) > d(E)} + ½ #{d(E′) = d(E)}) / |R_k(T, E)|, R_k(T, E) = {E′ ∈ R(k) \\ {E}: d ≠ null}.
    d_aday (n,), d_ref (m,) (NaN = null). ref_konum (n,): adayın d_ref içindeki indeksi, R(k)'da değilse −1 (kendisi çıkar).
    d(E) null ya da |R_k(T, E)| < en_az → NaN."""
    da = np.asarray(d_aday, float)
    dr_ham = np.asarray(d_ref, float)
    a = _ref(dr_ham)
    m = np.full(da.shape, float(len(a)))
    sol = np.searchsorted(a, da, side="left").astype(float)
    sag = np.searchsorted(a, da, side="right").astype(float)
    buyuk = len(a) - sag
    esit = sag - sol
    if ref_konum is not None:
        rk = np.asarray(ref_konum, int)
        ic = rk >= 0
        kendi_var = np.zeros(da.shape, bool)
        kendi_var[ic] = np.isfinite(dr_ham[rk[ic]])
        if kendi_var.any():
            assert np.all(dr_ham[rk[kendi_var]] == da[kendi_var]), "aday R(k) içinde ama uzaklığı farklı"
        esit = esit - kendi_var
        m = m - kendi_var
    with np.errstate(invalid="ignore", divide="ignore"):
        s = (buyuk + 0.5 * esit) / m
    return np.where(np.isfinite(da) & (m >= en_az), s, np.nan)


def _ortanca_haric(a, p):
    """Sıralı a'dan sıralı konumu p olan eleman çıkarılınca ortanca; p dizi (−1 → çıkarma yok)."""
    p = np.asarray(p, int)
    m = len(a)
    n = np.where(p >= 0, m - 1, m)
    def el(r):
        q = np.where((p < 0) | (r < p), r, r + 1)
        return a[np.clip(q, 0, max(m - 1, 0))] if m else np.full(p.shape, np.nan)
    k = n // 2
    tek = el(k)
    cift = 0.5 * (el(np.maximum(k - 1, 0)) + el(k))
    return np.where(n <= 0, np.nan, np.where(n % 2 == 1, tek, cift))


def zeta_k(d_aday, d_ref, ref_konum=None, sayim=False):
    """Belge 5.4: ζ_k(E) = d_k(E, T) / medyan_{E′ ∈ R_k(T, E)} d_k(E′, T). d null → NaN.
    Ortanca 0 ise (Q-11, Sude onaylı 13:14): d = 0 → 1 (tipik referans kadar yakın; s_k'nin ½ eşitlik kuralıyla tutarlı),
    d > 0 → +∞. sayim=True ise (ζ, paydası 0 olan aday sayısı) döner (kayda yazılır)."""
    da = np.asarray(d_aday, float)
    dr_ham = np.asarray(d_ref, float)
    a = _ref(dr_ham)
    gecerli = np.isfinite(dr_ham)
    # geçerli referansların sıralı konumu (a ile aynı sıra; eşitlerde hangisinin çıktığı ortancayı değiştirmez)
    sk = np.full(len(dr_ham), -1, int)
    gi = np.flatnonzero(gecerli)
    sk[gi[np.argsort(dr_ham[gi], kind="stable")]] = np.arange(len(gi))
    rk = np.full(da.shape, -1, int) if ref_konum is None else np.asarray(ref_konum, int)
    p = np.where(rk >= 0, sk[np.clip(rk, 0, None)] if len(sk) else -1, -1)
    with np.errstate(invalid="ignore"):
        med = _ortanca_haric(a, p)
        z = np.where(med > 0, da / np.where(med > 0, med, 1.0), np.where(da == 0, 1.0, np.inf))
    gecer = np.isfinite(da) & ~np.isnan(med)
    z = np.where(gecer, z, np.nan)
    if sayim:
        return z, int(np.sum(gecer & (med == 0)))
    return z


# ------------------------------------------------------------------ 7.4 P, Q
def P_Q(s, z, w, kapi):
    """Belge 7.4: P = Kapı · Σ w s / Σ w, Q = Σ w ζ / Σ w; toplamlar K(E) = {k : s_k ≠ null} üzerinden.
    s, z (n, 8); w (8,); kapi (n,) bool (= Uygun · G). K(E) boşsa P, Q = NaN. Kapıdan kalan: P = 0."""
    s = np.asarray(s, float); z = np.asarray(z, float); w = np.asarray(w, float); kapi = np.asarray(kapi, bool)
    assert s.shape == z.shape and s.shape[1] == len(w) and kapi.shape == (len(s),)
    K = np.isfinite(s)
    assert not np.any(K & np.isnan(z)), "s var ama ζ yok"
    W = np.where(K, w[None, :], 0.0).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        P = np.where(K, w * s, 0.0).sum(axis=1) / W
        Q = np.where(K, w * np.where(K, z, 0.0), 0.0).sum(axis=1) / W
    P = np.where(W > 0, np.where(kapi, P, 0.0), np.nan)
    Q = np.where(W > 0, Q, np.nan)
    return P, Q


def P_geometrik(s, w, kapi):
    """Belge 7.4 duyarlılık (ii): Π s_k^(w_k / Σw), K(E) üzerinden; s_k = 0 → 0."""
    s = np.asarray(s, float); w = np.asarray(w, float); kapi = np.asarray(kapi, bool)
    K = np.isfinite(s)
    W = np.where(K, w[None, :], 0.0).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        ust = np.where(K, w[None, :], 0.0) / W[:, None]
        lg = np.where(K & (ust > 0), ust * np.log(np.where(K, s, 1.0)), 0.0).sum(axis=1)
    P = np.exp(lg)
    return np.where(W > 0, np.where(kapi, P, 0.0), np.nan)


def sirala(P, Q, kimlik):
    """Belge 7.4: P azalan, eşitlikte Q artan, sonra kimlik artan. NaN P en sona, NaN Q eşitlikte sona."""
    P = np.asarray(P, float); Q = np.asarray(Q, float); kimlik = np.asarray(kimlik)
    Pk = np.where(np.isfinite(P), -P, np.inf)
    Qk = np.where(np.isnan(Q), np.inf, Q)
    return np.lexsort((kimlik, Qk, Pk))


# ------------------------------------------------------------------ 7.4 Top-3 (100 km)
def gc_km(lat1, lon1, lat2, lon2, govde="dunya"):
    """Belge 4.2 büyük çember uzaklığı (haversine [101]); girdiler derece, yarıçap ayar.json cisim.yaricap_km."""
    r = float(A.ayar("cisim.yaricap_km")[govde])
    p1, l1, p2, l2 = (np.radians(np.asarray(v, float)) for v in (lat1, lon1, lat2, lon2))
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin((l2 - l1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0)))


def aralikli_liste(sira, lat, lon, n, gecer=None, en_az_km=TOP3_EN_AZ_KM, govde="dunya"):
    """Belge 7.4: sırayla gez; seçilmişlerin her birine merkez uzaklığı ≥ en_az_km olanı al; n tane olunca dur.
    gecer (n_aday,) bool: listeye girebilen (kapıdan geçen) adaylar. Dönüş seçilen indeksler."""
    lat = np.asarray(lat, float); lon = np.asarray(lon, float)
    gecer = np.ones(len(lat), bool) if gecer is None else np.asarray(gecer, bool)
    secilen = []
    for i in sira:
        if len(secilen) >= n:
            break
        if not gecer[i]:
            continue
        if secilen:
            d = gc_km(lat[i], lon[i], lat[secilen], lon[secilen], govde)
            if np.any(np.asarray(d, float) < en_az_km):
                continue
        secilen.append(int(i))
    return np.array(secilen, int)


def yeniden_sirala(ilk, P_tam, Q_tam, kimlik):
    """Belge 7.4: topolojisiz sıranın ilk 30'u (ilk) tam puanla yeniden sıralanır. Dönüş ilk'in yeni sırası."""
    ilk = np.asarray(ilk, int)
    o = sirala(np.asarray(P_tam, float)[ilk], np.asarray(Q_tam, float)[ilk], np.asarray(kimlik)[ilk])
    return ilk[o]


# ------------------------------------------------------------------ 7.4 şampiyonlar
def sampiyonlar(s, z, kimlik, uygun):
    """Belge 7.4 + Q-2: her k için uygun adaylar içinde s_k en büyük, eşitlikte ζ_k en küçük, sonra kimlik küçük.
    uygun (n,) ya da (n, 8) bool (k = 2 için son 30 maskesi kos.py'den). Aday yoksa −1."""
    s = np.asarray(s, float); z = np.asarray(z, float); kimlik = np.asarray(kimlik)
    u = np.asarray(uygun, bool)
    u = np.broadcast_to(u[:, None], s.shape) if u.ndim == 1 else u
    out = np.full(s.shape[1], -1, int)
    for k in range(s.shape[1]):
        m = u[:, k] & np.isfinite(s[:, k])
        if not m.any():
            continue
        idx = np.flatnonzero(m)
        zk = np.where(np.isnan(z[idx, k]), np.inf, z[idx, k])
        o = np.lexsort((kimlik[idx], zk, -s[idx, k]))
        out[k] = idx[o[0]]
    return out


# ------------------------------------------------------------------ 7.4 duyarlılık
def kendall_tau_b(x, y):
    """Kendall τb [53] (eşitlik düzeltmeli), NaN çiftler dışarıda. Tanımsızsa NaN."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 2:
        return float("nan")
    r = kendalltau(x[m], y[m], variant="b")
    return float(r.statistic if hasattr(r, "statistic") else r[0])


def jaccard(a, b):
    """J = |A ∩ B| / |A ∪ B| [52]."""
    A, B = set(map(int, a)), set(map(int, b))
    return float(len(A & B) / len(A | B)) if (A | B) else float("nan")
