# Developed with assistance from Claude (Anthropic).
# puan.py güncellemesi: Q-11 (payda 0 → d = 0 için ζ = 1, sayım), sabitler ayar.json'dan; Q-12/Q-13 kayıtta (kos.py uygular).
import sys, importlib
from pathlib import Path
KOK = Path.home() / "orbitrary"; KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / "puan.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
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
''', encoding="utf-8")
(KOD / "testler" / "test_puan.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 5.4, 7.3–7.4 testleri (8.2 ve 8.3 tablolarındaki satırlar adlarında)."""
import numpy as np
import pytest

import ayar as A
import puan as Pn

TABLO_7_3 = {  # belge 7.3 tablosu: görev → ana kategoriler (1 = Top … 8 = Işık)
    "Genel": [], "Mobility": [1, 2, 7], "Geology": [2, 3, 4], "Ice": [5, 6, 8], "Astro": [4, 5, 6]}


def test_gorev_agirligi_8_2():
    w = Pn.kademeli_agirlik([1, 2, 7])
    assert w.sum() == pytest.approx(1.0)
    assert w[0] == pytest.approx(0.2667, abs=5e-5) and w[2] == pytest.approx(0.04)
    assert 3 * 0.8 / 3 + 5 * 0.04 == pytest.approx(1.0)


def test_agirlik_tablosu_7_3():
    for g, ana in TABLO_7_3.items():
        w = Pn.kademeli_agirlik(ana)
        beklenen = np.full(8, 0.125) if not ana else np.where(np.isin(np.arange(1, 9), ana), 0.8 / 3, 0.04)
        np.testing.assert_allclose(w, beklenen, err_msg=g)


def test_null_dusmesi_8_3():
    w = Pn.kademeli_agirlik(TABLO_7_3["Ice"])
    mevcut = np.ones(8, bool); mevcut[7] = False      # s₈ = null
    e = Pn.etkili_agirlik(w, mevcut)
    assert e[4] == pytest.approx(0.364, abs=5e-4) and e[5] == pytest.approx(0.364, abs=5e-4)
    assert e[0] == pytest.approx(0.055, abs=5e-4) and e[7] == 0 and e.sum() == pytest.approx(1)


def test_yuzdelik_kalibrasyon_s1_8_2():
    d_ref = np.linspace(1, 10, 500)
    assert Pn.s_k([0.5], d_ref)[0] == 1.0


def test_yuzdelik_sira_bicimi_8_2():
    # R(k) = bütün E′ (N = 5), her aday kendi referansından çıkar; en_az = 1 (formül sınaması)
    d = np.array([1, 2, 2, 3, 4], float)
    s = Pn.s_k(d, d, ref_konum=np.arange(5), en_az=1)
    np.testing.assert_allclose(s, [1, 0.625, 0.625, 0.25, 0])


def test_sira_bicimi_formulu_rastgele():
    # belge 5.4: s = 1 − (r − 1)/(N − 1), r ortalama sıra
    from scipy.stats import rankdata
    rng = np.random.default_rng(3)
    d = rng.integers(0, 40, 300).astype(float)
    s = Pn.s_k(d, d, ref_konum=np.arange(300), en_az=1)
    np.testing.assert_allclose(s, 1 - (rankdata(d) - 1) / 299)


def test_referans_alt_siniri_8_3():
    d_ref = np.r_[np.arange(99.0), np.nan]          # 99 geçerli
    assert np.isnan(Pn.s_k([5.0], d_ref)[0])
    assert np.isfinite(Pn.s_k([5.0], np.arange(100.0))[0])
    # aday R(k) içindeyse kendisi düşer: 100 referans → 99 → null
    assert np.isnan(Pn.s_k([5.0], np.arange(100.0), ref_konum=[5])[0])
    assert np.isnan(Pn.s_k([np.nan], np.arange(200.0))[0])


def test_zeta_ve_kendi_haric_ortanca():
    d_ref = np.array([1, 2, 3, 4, 10.0])
    np.testing.assert_allclose(Pn.zeta_k([1.5, 6.0], d_ref), [0.5, 2.0])
    # aday d_ref[4] (=10) ise ortanca {1,2,3,4} = 2,5
    assert Pn.zeta_k([10.0], d_ref, ref_konum=[4])[0] == pytest.approx(4.0)
    assert np.isnan(Pn.zeta_k([np.nan], d_ref)[0])


def test_zeta_kaba_kuvvet():
    rng = np.random.default_rng(8)
    d_ref = rng.random(101); d_ref[[3, 50]] = np.nan
    aday = rng.random(30); rk = np.full(30, -1); rk[:10] = np.arange(10); aday[:10] = d_ref[:10]
    z = Pn.zeta_k(aday, d_ref, ref_konum=rk)
    for i in range(30):
        if not np.isfinite(aday[i]):
            assert np.isnan(z[i]); continue
        r = d_ref.copy()
        if rk[i] >= 0: r = np.delete(r, rk[i])
        assert z[i] == pytest.approx(aday[i] / np.nanmedian(r))


def test_zeta_ortanca_sifir_Q11():
    # Q-11 (Sude): payda 0 → d = 0 için ζ = 1, d > 0 için +∞; sayı kayda
    d_ref = np.zeros(200)
    z, n0 = Pn.zeta_k([0.0, 0.3, np.nan], d_ref, sayim=True)
    np.testing.assert_array_equal(z, [1.0, np.inf, np.nan])
    assert n0 == 2
    assert Pn.zeta_k([0.5], np.r_[np.zeros(100), np.ones(101)], sayim=True)[1] == 0


def test_ayar_agirlik_tablosu_7_3():
    # ayar.json agirlik.ana_kategoriler belge 7.3 tablosuyla aynı; Genel ve 'esit' eşit
    ana = A.ayar("agirlik.ana_kategoriler")
    harita = {"mobility": "Mobility", "geology": "Geology", "ice": "Ice", "astro": "Astro"}
    assert set(ana) == set(harita)
    for g, b in harita.items():
        assert sorted(ana[g]) == TABLO_7_3[b], g
        np.testing.assert_allclose(Pn.gorev_agirligi(g), Pn.kademeli_agirlik(TABLO_7_3[b]))
        np.testing.assert_allclose(Pn.gorev_agirligi(g, "esit"), np.full(8, 0.125))
    np.testing.assert_allclose(Pn.gorev_agirligi("genel"), np.full(8, 0.125))
    assert A.ayar("agirlik.duyarlilik_sema") == ["esit", "geometrik"]


def test_P_Q_null_ve_kapi():
    s = np.array([[1, 0.5, np.nan, 0, 0, 0, 0, 0], [0.2] * 8, [np.nan] * 8])
    z = np.where(np.isfinite(s), 1.0, np.nan)
    w = Pn.kademeli_agirlik([1, 2, 3])
    P, Q = Pn.P_Q(s, z, w, kapi=[True, False, True])
    e = Pn.etkili_agirlik(w, np.isfinite(s[0]))
    assert P[0] == pytest.approx((e * np.nan_to_num(s[0])).sum())
    assert P[1] == 0 and Q[1] == pytest.approx(1.0) and np.isnan(P[2]) and np.isnan(Q[2])


def test_esitlik_kirici_8_3():
    P = np.array([0.8, 0.9, 0.9, 0.7]); Q = np.array([0.1, 0.5, 0.2, 0.0]); kim = np.array([10, 11, 12, 13])
    o = Pn.sirala(P, Q, kim)
    np.testing.assert_array_equal(o, [2, 1, 0, 3])
    np.testing.assert_array_equal(Pn.sirala(P, Q, kim), o)   # tekrar koşuda aynı
    P2 = np.array([0.5, 0.5]); Q2 = np.array([0.3, 0.3])
    np.testing.assert_array_equal(Pn.sirala(P2, Q2, np.array([7, 3])), [1, 0])
    np.testing.assert_array_equal(Pn.sirala([np.nan, 0.1], [0, 0], [0, 1]), [1, 0])


def test_top3_araligi_8_3():
    # 60 km arayla iki yüksek aday → ikincisi atlanır
    lat0 = 40.0
    dlat = 60.0 / 6371.0 * 180 / np.pi
    lat = np.array([lat0, lat0 + dlat, 10.0, -20.0]); lon = np.array([30.0, 30.0, 30.0, 30.0])
    assert Pn.gc_km(lat[0], lon[0], lat[1], lon[1]) == pytest.approx(60.0, rel=1e-9)
    assert Pn.gc_km(0, 0, 0, 90, "ay") == pytest.approx(np.pi / 2 * 1737.4)
    sec = Pn.aralikli_liste(np.arange(4), lat, lon, 3)
    np.testing.assert_array_equal(sec, [0, 2, 3])
    # tam 100 km: alınır (en az 100 km)
    d100 = 100.0 / 6371.0 * 180 / np.pi
    sec = Pn.aralikli_liste(np.arange(2), np.array([0.0, d100 * (1 + 1e-9)]), np.zeros(2), 3)
    np.testing.assert_array_equal(sec, [0, 1])
    # kapıdan kalan listeye girmez
    sec = Pn.aralikli_liste(np.arange(4), lat, lon, 3, gecer=[False, True, True, True])
    np.testing.assert_array_equal(sec, [1, 2, 3])


def test_yeniden_sirala_ilk30():
    rng = np.random.default_rng(4)
    ilk = rng.permutation(100)[:30]
    P = rng.random(100); Q = rng.random(100); kim = np.arange(100)
    y = Pn.yeniden_sirala(ilk, P, Q, kim)
    assert sorted(y) == sorted(ilk) and np.all(np.diff(P[y]) <= 0)


def test_sampiyonlar_Q2():
    s = np.array([[0.9, 0.2], [0.9, 0.8], [0.95, 0.8], [0.5, np.nan]])
    z = np.array([[0.1, 1.0], [0.05, 0.3], [0.2, 0.3], [0.4, np.nan]])
    kim = np.array([5, 6, 7, 8])
    np.testing.assert_array_equal(Pn.sampiyonlar(s, z, kim, [True, True, False, True]), [1, 1])
    u = np.ones((4, 2), bool); u[:, 1] = [False, False, False, True]   # k=2 için yalnız son-30 maskesi
    np.testing.assert_array_equal(Pn.sampiyonlar(s, z, kim, u), [2, -1])


def test_geometrik_ortalama():
    s = np.array([[0.5, 0.5, np.nan, 1, 1, 1, 1, 1], [0, 1, 1, 1, 1, 1, 1, 1.0]])
    w = np.full(8, 0.125)
    G = Pn.P_geometrik(s, w, kapi=[True, True])
    assert G[0] == pytest.approx(0.5 ** (2 / 7)) and G[1] == 0


def test_kendall_ve_jaccard():
    x = np.array([1, 2, 3, 4, 5.0])
    assert Pn.kendall_tau_b(x, x) == pytest.approx(1) and Pn.kendall_tau_b(x, -x) == pytest.approx(-1)
    assert Pn.kendall_tau_b([1, 1, 2, 2], [1, 2, 1, 2]) == pytest.approx(0)
    assert Pn.jaccard([1, 2, 3], [1, 2, 4]) == pytest.approx(0.5)


def test_kimlik_D7_her_s1():
    # hedefin kendisi aday (uzaklık 0), R(k) 2000 referans > 0 → s_k = 1 ve ilk sıra
    rng = np.random.default_rng(9)
    d_ref = rng.random((8, 2000)) + 0.01
    aday = np.vstack([np.zeros(8), rng.random((50, 8))])
    s = np.column_stack([Pn.s_k(aday[:, k], d_ref[k]) for k in range(8)])
    z = np.column_stack([Pn.zeta_k(aday[:, k], d_ref[k]) for k in range(8)])
    assert np.all(s[0] == 1)
    P, Q = Pn.P_Q(s, z, Pn.kademeli_agirlik([]), np.ones(51, bool))
    assert Pn.sirala(P, Q, np.arange(51))[0] == 0
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
''', encoding="utf-8")
yol = KOD / "FONKSIYONLAR.md"; metin = yol.read_text(encoding="utf-8")
a = "- 5.4 ζ_k(E) (kendisi hariç ortanca) → `puan.zeta_k`"
assert metin.count(a) == 1
metin = metin.replace(a, a.replace("ortanca)", "ortanca; Q-11 payda 0 → ζ = 1 / +∞)") + "\n- 7.3 w_k(g) ayar.json'dan (ana / eşit) → `puan.gorev_agirligi`")
yol.write_text(metin, encoding="utf-8")
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | puan.py: Q-11 (Sude 13:14) payda 0 → d = 0 için ζ = 1, d > 0 için +∞, sayım; Q-12 ilk 10'a da 100 km; Q-13 τb son 30 aday, aynı küme; sabitler ayar.json'dan + assert | etkisi: MAKALEYİ ETKİLER 43–45, 50\n")
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_puan", "testler/test_puan.py")
