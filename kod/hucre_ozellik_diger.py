# Developed with assistance from Claude (Anthropic).
# 17.4 sıra 7: kod\\ozellik_diger.py + testler (belge 6.3–6.8; 8.2 C₁, I⊕, sıfır kuralı, ıslak/kuru, aydınlanma, mineraloji)
import sys, subprocess, datetime
from pathlib import Path

KOK = Path.home() / "orbitrary"
KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / "ozellik_diger.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 6.3–6.8: jeoloji (3), mineraloji (4), termal (5), su/buz (6), toz (7), aydınlanma (8).

Formüller (saf fonksiyonlar) → türetilmiş katmanlar (ornekle/cozunurluk_km; katman.hucreye ile hücreye) →
pencere temsilleri (sınıf payları, sıra dağılımlarının 1000 noktalı yüzdelik vektörleri) → d₃ … d₈.

Okuma kararları (14 Kasım; kayit\\degisiklik.md):
- Dünya Tmax = 12 aylık gündüz LST'nin en büyüğü; T̄ = aylık (gündüz + gece)/2'nin yıllık ortalaması;
  Tgece = aylık gece LST'nin yıllık ortalaması.
- I⊕ aylık; C₁ = 0 ya da ΔTg ≤ 0 olan ay ortalamaya girmez. δ⊙: ayın 15'i, düşük duyarlıklı güneş formülü
  (Astronomical Almanac), sin δ = sin ε sin λ.
- ASTER MI: her bandın 12 aylık ortalamasından.
- Ay aydınlanması: |φ| ≥ 65° PGDA, |φ| < 65° Berger; her biri kendi kapsamında sıralanır.
- Sıfır kuralı: kara hücresi = MCD12C1 kara payı ≥ 0,5. Ay π⁺: alt örneklerin ≥ yarısı pozitifse hücre pozitif.
"""
import datetime
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import ayar as A
import izgara as Z
import katman as K
import uzaklik as U

ARA = A.KLASOR["ara"]
GRUPLAR = ["volkanik", "bazik_plutonik", "asidik_ara_plutonik", "tortul", "metamorfik", "buz"]
IZINLI = set(GRUPLAR) | {"yayla_yarim", "hesap_disi"}


# =============================================================== 1. formüller
def gunes_boylami_ve_deklinasyon(tarih):
    """Düşük duyarlıklı güneş konumu (Astronomical Almanac): ekliptik boylam λ (derece) ve
    δ⊙ = asin(sin ε sin λ), ε = ayar cisim.eksen_egikligi_der['dunya'] (belge 6.8 biçimi)."""
    n = (datetime.datetime(tarih.year, tarih.month, tarih.day, 12) - datetime.datetime(2000, 1, 1, 12)).days
    L = 280.460 + 0.9856474 * n
    g = math.radians(357.528 + 0.9856003 * n)
    lam = (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360.0
    eps = math.radians(float(A.ayar("cisim.eksen_egikligi_der")["dunya"]))
    return lam, math.asin(math.sin(eps) * math.sin(math.radians(lam)))


def _H0(phi, delta):
    """Gün doğumu saat açısı: cos H₀ = −tan φ tan δ; kutup gününde π, kutup gecesinde 0."""
    with np.errstate(invalid="ignore", divide="ignore"):
        c = -np.tan(phi) * np.tan(delta)
    return np.arccos(np.clip(c, -1.0, 1.0))


def C1(phi, delta):
    """Belge 6.5: C₁ = sin φ sin δ sin H₀ + H₀ cos φ cos δ (H₀ = π → π cos φ cos δ; H₀ = 0 → 0)."""
    phi, delta = np.asarray(phi, float), np.asarray(delta, float)
    H = _H0(phi, delta)
    return np.sin(phi) * np.sin(delta) * np.sin(H) + H * np.cos(phi) * np.cos(delta)


def I_arti_ay(c1, albedo, dTg):
    """Belge 6.5: I⊕ = C₁ (1 − α) / ΔTg; C₁ = 0 ya da ΔTg ≤ 0 → NaN (ortalamaya girmez)."""
    c1, albedo, dTg = (np.asarray(v, float) for v in (c1, albedo, dTg))
    with np.errstate(invalid="ignore", divide="ignore"):
        I = c1 * (1.0 - albedo) / dTg
    return np.where((c1 > 0) & (dTg > 0) & np.isfinite(albedo), I, np.nan)


def berger_gunluk(phi, delta):
    """Belge 6.8: Q̄_gün = (1/π)(H₀ sin φ sin δ + cos φ cos δ sin H₀)."""
    phi, delta = np.asarray(phi, float), np.asarray(delta, float)
    H = _H0(phi, delta)
    return (H * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(H)) / math.pi


def berger_yillik(phi, eps_der, n_adim=None):
    """Belge 6.8: f(φ) = (1/2π) ∫ Q̄_gün(φ, δ(L_s)) dL_s, sin δ = sin ε sin L_s; orta nokta kuralı."""
    n_adim = int(A.ayar("aydinlanma.Ls_adim")) if n_adim is None else int(n_adim)
    Ls = (np.arange(n_adim) + 0.5) * 2 * math.pi / n_adim
    d = np.arcsin(math.sin(math.radians(eps_der)) * np.sin(Ls))
    phi = np.atleast_1d(np.asarray(phi, float))
    return np.array([berger_gunluk(p, d).mean() for p in phi])


class BergerTablosu:
    """f(φ) tablosu (0,001° adım) ve doğrusal ara değer (ölçülen en büyük hata 1,2e-9, Ay ε = 1,54°; testte < 1e-8)."""

    def __init__(self, eps_der, adim_der=0.001):
        self.adim = adim_der
        self.lat = np.linspace(-90.0, 90.0, int(round(180 / adim_der)) + 1)
        n_adim = int(A.ayar("aydinlanma.Ls_adim"))
        Ls = (np.arange(n_adim) + 0.5) * 2 * math.pi / n_adim
        d = np.arcsin(math.sin(math.radians(eps_der)) * np.sin(Ls))
        phi = np.radians(self.lat)
        self.f = np.empty_like(phi)
        for k in range(0, phi.size, 2000):
            self.f[k:k + 2000] = berger_gunluk(phi[k:k + 2000, None], d[None, :]).mean(axis=1)

    def __call__(self, lat_der):
        return np.interp(np.asarray(lat_der, float), self.lat, self.f)


def mafik_indeks(e12, e13, e14):
    """Belge 6.4 (Ninomiya ve ark. [134]): MI = ε₁₂ ε₁₄³ / ε₁₃⁴."""
    e12, e13, e14 = (np.asarray(v, float) for v in (e12, e13, e14))
    with np.errstate(invalid="ignore", divide="ignore"):
        return e12 * e14 ** 3 / e13 ** 4


def mars_hcp(b3, b5, b6):
    """Belge 6.4 / v1.2 D11: x = b₆ / (b₃ + b₅ + b₆); paydada 0 ya da veri yok → NaN."""
    b3, b5, b6 = (np.asarray(v, float) for v in (b3, b5, b6))
    s = b3 + b5 + b6
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(s > 0, b6 / s, np.nan)


def sifir_kurali(perm, kar_buz, kara):
    """Belge 6.6 Dünya: kar/buz ≥ 0,5 → hesap dışı (NaN); haritada değer yok ve kara hücresi (kara ≥ 0,5) → 0;
    haritada değer yok ve kara değil → NaN; değer var → değer."""
    perm, kar_buz, kara = (np.asarray(v, float) for v in (perm, kar_buz, kara))
    kb_sinir = float(A.ayar("su_buz.kar_buz_siniri"))
    x = np.where(np.isfinite(perm), perm, np.where(kara >= 0.5, 0.0, np.nan))
    return np.where(np.isfinite(kar_buz) & (kar_buz >= kb_sinir), np.nan, x)


def pi_arti(pozitif, veri_var):
    """Belge 6.6: π⁺(T) = #{pozitif hücre} / #{verisi olan hücre}; veri yoksa NaN."""
    pozitif, veri_var = np.asarray(pozitif, bool), np.asarray(veri_var, bool)
    n = veri_var.sum(axis=(-2, -1))
    p = (pozitif & veri_var).sum(axis=(-2, -1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, p / np.maximum(n, 1), np.nan)


def islak_mi(pi):
    """Belge 6.6: π⁺ ≥ 0,5 → ıslak; NaN (kapsam dışı) → kuru."""
    pi = np.asarray(pi, float)
    return np.where(np.isfinite(pi), pi >= float(A.ayar("su_buz.islak_esigi")), False)


def gecerli_oran(x):
    """Pencerede değeri olan hücre oranı (son iki eksen)."""
    x = np.asarray(x, float)
    return np.isfinite(x).mean(axis=(-2, -1))


# =============================================================== 2. jeoloji sözlüğü
def sozluk_matrisi(govde, siniflar, yol=None):
    """kod\\jeoloji_sozluk.csv → (C, 6) ağırlık matrisi (birim → grup). Verideki her birim sözlükte ve grubu izinli
    olmalı; hesap_disi → 0 satırı; yayla_yarim → ayar jeoloji.mars_yayla."""
    yol = A.KLASOR["kod"] / "jeoloji_sozluk.csv" if yol is None else Path(yol)
    sz = pd.read_csv(yol, dtype=str, encoding="utf-8-sig").fillna("")
    sz = sz[sz["cisim"].str.strip().str.lower() == govde]
    harita = dict(zip(sz["birim_kodu"].str.strip(), sz["grup"].str.strip()))
    eksik = [s for s in siniflar if s not in harita]
    bos = [s for s in siniflar if s in harita and harita[s] == ""]
    yanlis = sorted({harita[s] for s in siniflar if s in harita and harita[s] not in IZINLI and harita[s] != ""})
    assert not eksik, f"jeoloji_sozluk.csv ({govde}): sözlükte olmayan birimler {eksik}"
    assert not bos, f"jeoloji_sozluk.csv ({govde}): grubu boş birimler ({len(bos)}): {bos}"
    assert not yanlis, f"jeoloji_sozluk.csv ({govde}): izinsiz grup değerleri {yanlis}; izinli: {sorted(IZINLI)}"
    yayla = A.ayar("jeoloji.mars_yayla")
    G = np.zeros((len(siniflar), len(GRUPLAR)))
    for i, s in enumerate(siniflar):
        g = harita[s]
        if g == "hesap_disi":
            continue
        if g == "yayla_yarim":
            for ad, w in yayla.items():
                G[i, GRUPLAR.index(ad)] = float(w)
        else:
            G[i, GRUPLAR.index(g)] = 1.0
    return G


def hucre_grup_paylari(pay, G, kar_buz=None):
    """Hücre sınıf payları pay (..., C) → grup payları (..., 6), hesap dışı noktalar düşer ve yeniden
    normalleşir. Dünya: kar/buz payı kb (MCD12C1 sınıf 15) 'buz' grubuna yazılır: (1 − kb)·q + kb·e_buz.
    Geçersiz hücre (veri yok, kb = 0 ya da yok) → NaN."""
    g = np.nan_to_num(np.asarray(pay, float)) @ G
    t = g.sum(axis=-1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        q = np.where(t > 0, g / np.maximum(t, 1e-300), np.nan)
    if kar_buz is not None:
        kb = np.clip(np.nan_to_num(np.asarray(kar_buz, float)), 0, 1)[..., None]
        e = np.zeros(len(GRUPLAR)); e[GRUPLAR.index("buz")] = 1.0
        q = np.where(np.isfinite(q), (1 - kb) * q + kb * e, np.where(kb > 0, e * np.ones_like(kb), np.nan))
    return q


def pencere_jeoloji(qh):
    """Belge 6.3: q_c(W) = W* hücrelerinin ortalaması; (..., n, n, 6) → (..., 6), geçerli hücre oranı."""
    qh = np.asarray(qh, float)
    gec = np.isfinite(qh).all(axis=-1)
    say = gec.sum(axis=(-2, -1))
    top = np.where(gec[..., None], qh, 0.0).sum(axis=(-3, -2))
    with np.errstate(invalid="ignore", divide="ignore"):
        q = np.where(say[..., None] > 0, top / np.maximum(say, 1)[..., None], np.nan)
    return q, gec.mean(axis=(-2, -1))


# =============================================================== 3. türetilmiş katmanlar
class Fonksiyon:
    """f(lat, lon) → değer; çözünürlük fonksiyonu (katman.hucreye için)."""

    tur = "fonksiyon"

    def __init__(self, ad, f, coz):
        self.ad, self.f, self.coz = ad, f, coz

    def ornekle(self, lat, lon):
        lat, lon = np.asarray(lat, float), np.asarray(lon, float)
        return np.asarray(self.f(lat, lon), np.float32)

    def cozunurluk_km(self, lat, r):
        return self.coz(lat, r)


def _kaba(lat, r):
    return 1e9, 1e9  # hücreden kaba → coarse (s = 1)


def _tarih(ad):
    s = ad.split("_")[-1]
    return datetime.date(int(s[:4]), 1, 1) + datetime.timedelta(days=int(s[4:]) - 1)


def dunya_cmg():
    """Dünya 0,05° CMG türetilmiş ızgaraları (bir kez hesaplanır, ara\\cmg_*.npy + .json):
    mi, tmax, tort, tgece, iarti. Girdiler temiz\\ E4, E5, E6 (aynı CMG ızgarası, assert)."""
    adlar = ["mi", "tmax", "tort", "tgece", "iarti"]
    yollar = {a: ARA / f"cmg_{a}.npy" for a in adlar}
    if all(p.exists() for p in yollar.values()):
        return yollar
    gt = [-180.0, 0.05, 0.0, 90.0, 0.0, -0.05]
    bilgi = {}

    def yukle(ad):
        k = K.ac(ad)
        assert k.tur == "cografi" and (k.x0, k.dx, k.y0, k.dy) == (-180.0, 0.05, 90.0, 0.05), ad
        return np.asarray(k.kaynak, dtype=np.float32)

    # MI: her bandın 12 aylık ortalaması
    e = {}
    for b in (12, 13, 14):
        st = np.stack([yukle(a) for a in K.aylik("E4", f"yayinim_b{b}")])
        with np.errstate(invalid="ignore"):
            e[b] = np.nanmean(st, axis=0)
        del st
    mi = mafik_indeks(e[12], e[13], e[14]).astype(np.float32)
    del e
    # LST
    gun = {_tarih(a).month: a for a in K.aylik("E5", "lst_gunduz")}
    gec = {_tarih(a).month: a for a in K.aylik("E5", "lst_gece")}
    alb = {_tarih(a).month: a for a in K.aylik("E6", "albedo_wsa")}
    assert sorted(gun) == sorted(gec) == sorted(alb) == list(range(1, 13))
    lat_c = 90.0 - (np.arange(3600) + 0.5) * 0.05
    tmax = np.full((3600, 7200), -np.inf, np.float32)
    top_ort = np.zeros((3600, 7200), np.float32); n_ort = np.zeros((3600, 7200), np.int16)
    top_gece = np.zeros((3600, 7200), np.float32); n_gece = np.zeros((3600, 7200), np.int16)
    top_i = np.zeros((3600, 7200), np.float64); n_i = np.zeros((3600, 7200), np.int16)
    for ay in range(1, 13):
        D, N, a = yukle(gun[ay]), yukle(gec[ay]), yukle(alb[ay])
        tmax = np.fmax(tmax, D)
        m = np.isfinite(D) & np.isfinite(N)
        top_ort += np.where(m, (D + N) / 2, 0); n_ort += m
        mg = np.isfinite(N)
        top_gece += np.where(mg, N, 0); n_gece += mg
        _, d = gunes_boylami_ve_deklinasyon(datetime.date(2023, ay, 15))
        c1 = C1(np.radians(lat_c), d)[:, None]
        I = I_arti_ay(c1, a, D - N)
        mi_ = np.isfinite(I)
        top_i += np.where(mi_, I, 0); n_i += mi_
        bilgi[f"ay_{ay:02d}"] = {"gunduz": gun[ay], "gece": gec[ay], "albedo": alb[ay],
                                 "deklinasyon_der": round(math.degrees(d), 4), "iarti_gecerli": int(mi_.sum())}
    with np.errstate(invalid="ignore", divide="ignore"):
        ciktilar = {"mi": mi,
                    "tmax": np.where(np.isfinite(tmax), tmax, np.nan).astype(np.float32),
                    "tort": np.where(n_ort > 0, top_ort / np.maximum(n_ort, 1), np.nan).astype(np.float32),
                    "tgece": np.where(n_gece > 0, top_gece / np.maximum(n_gece, 1), np.nan).astype(np.float32),
                    "iarti": np.where(n_i > 0, top_i / np.maximum(n_i, 1), np.nan).astype(np.float32)}
    for ad, v in ciktilar.items():
        np.save(yollar[ad], v)
        Path(yollar[ad]).with_suffix(".json").write_text(json.dumps({
            "geotransform": gt, "sekil": [3600, 7200], "birim": {"mi": "", "tmax": "K", "tort": "K", "tgece": "K", "iarti": "K⁻¹ (göreli)"}[ad],
            "gecerli": int(np.isfinite(v).sum()), "en_kucuk": float(np.nanmin(v)), "en_buyuk": float(np.nanmax(v)),
            "aylar": bilgi if ad == "iarti" else None, "uretim": datetime.datetime.now().isoformat(timespec="seconds")},
            ensure_ascii=False, indent=1), encoding="utf-8")
    return yollar


_OD = {}


def ac(ad):
    """Türetilmiş katmanlar (bu modül) + katman.ac."""
    if ad in _OD:
        return _OD[ad]
    k = _ac(ad)
    _OD[ad] = k
    return k


def _ac(ad):
    R = {g: float(A.ayar("cisim.yaricap_km")[g]) for g in ("dunya", "ay", "mars")}
    if ad.startswith("cmg_"):
        p = dunya_cmg()[ad[4:]]
        return K._npy_cografi(ad, p, 20)
    if ad == "perm_sifir":
        kn, ka, su, kb = K.ac("perm_kuzey"), K.ac("perm_antarktika"), K.ac("mcd12c1_00"), K.ac("mcd12c1_15")

        def f(lat, lon):
            p = np.where(lat >= 0, kn.ornekle(lat, lon), ka.ornekle(lat, lon))
            return sifir_kurali(p, kb.ornekle(lat, lon) / 100.0, 1.0 - su.ornekle(lat, lon) / 100.0)
        return Fonksiyon(ad, f, _kaba)
    if ad == "siltkil":
        kil, silt = K.ac("kil"), K.ac("silt")
        return Fonksiyon(ad, lambda lat, lon: (kil.ornekle(lat, lon) + silt.ornekle(lat, lon)) / 1000.0,
                         lambda lat, r: kil.cozunurluk_km(lat, r))
    if ad == "berger_dunya" or ad == "berger_mars" or ad == "berger_ay":
        g = ad.split("_")[1]
        t = BergerTablosu(float(A.ayar("cisim.eksen_egikligi_der")[g]))
        return Fonksiyon(ad, lambda lat, lon: t(lat) + 0.0 * lon, _kaba)
    if ad == "ay_tgece":  # belge 6.5 / v1.2 D5: |φ| ≥ 70° GCP gece ortalaması, < 70° GHRM tbol
        gn, gs, tb = K.ac("gcp_gece_n"), K.ac("gcp_gece_s"), K.ac("tbol")
        sinir = float(A.ayar("termal.ay_tgece_gcp_sinir_der"))

        def f(lat, lon):
            return np.where(lat >= sinir, gn.ornekle(lat, lon),
                            np.where(lat <= -sinir, gs.ornekle(lat, lon), tb.ornekle(lat, lon)))

        def coz(lat, r):
            return gn.cozunurluk_km(lat, r) if abs(lat) >= sinir else tb.cozunurluk_km(lat, r)
        return Fonksiyon(ad, f, coz)
    if ad == "hidrojen_th":  # belge 6.6: Th ≥ 4,56 ppm hücreler hesap dışı
        h, th = K.ac("hidrojen"), K.ac("lpgrs_w_th")
        esik = float(A.ayar("su_buz.ay_toryum_ppm"))
        return Fonksiyon(ad, lambda lat, lon: np.where(th.ornekle(lat, lon) >= esik, np.nan, h.ornekle(lat, lon)), _kaba)
    if ad == "pgda":  # iki kutup birlikte (|φ| ≥ 65°)
        n_, s_ = K.ac("avgvisib_n"), K.ac("avgvisib_s")
        sinir = float(A.ayar("aydinlanma.ay_pgda_sinir_der"))
        return Fonksiyon(ad, lambda lat, lon: np.where(lat >= sinir, n_.ornekle(lat, lon),
                                                       np.where(lat <= -sinir, s_.ornekle(lat, lon), np.nan)),
                         lambda lat, r: n_.cozunurluk_km(lat, r))
    if ad == "mars_hcp":
        b3, b5, b6 = (np.asarray(K.ac(f"tes_{b}").kaynak) for b in ("plagioclase", "low_ca_pyroxene", "high_ca_pyroxene"))
        k6 = K.ac("tes_high_ca_pyroxene")
        return K.Cografi(ad, mars_hcp(b3, b5, b6).astype(np.float32), k6.x0, k6.dx, k6.y0, k6.dy, k6.nrow, k6.ncol, "")
    return K.ac(ad)


# =============================================================== 4. sıra referansları (P_f,B)
OZELLIK = {  # (gövde, özellik) → (katman, bantlar, sıra türü)
    ("dunya", "mi"): ("cmg_mi", ((-90, 90),), "u"),
    ("dunya", "tmax"): ("cmg_tmax", ((-90, 90),), "u"),
    ("dunya", "tort"): ("cmg_tort", ((-90, 90),), "u"),
    ("dunya", "tgece"): ("cmg_tgece", ((-90, 90),), "u"),
    ("dunya", "iarti"): ("cmg_iarti", ((-90, 90),), "u"),
    ("dunya", "su"): ("perm_sifir", ((-90, 90),), "u+"),
    ("dunya", "toz"): ("siltkil", ((-90, 90),), "u"),
    ("dunya", "isik"): ("berger_dunya", ((-90, 90),), "u"),
    ("ay", "mi"): ("lpgrs_w_feo", ((-90, 90),), "u"),
    ("ay", "tmax"): ("prp_temp_max", ((-90, -75.9), (75.9, 90)), "u"),
    ("ay", "tort"): ("prp_temp_avg", ((-90, -75.9), (75.9, 90)), "u"),
    ("ay", "tgece"): ("ay_tgece", ((-90, 90),), "u"),
    ("ay", "su"): ("hidrojen_th", ((-90, 90),), "u+"),
    ("ay", "toz"): ("ra", ((-70, 70),), "ters"),
    ("ay", "isik_pgda"): ("pgda", ((-90, -65), (65, 90)), "u"),
    ("ay", "isik_berger"): ("berger_ay", ((-65, 65),), "u"),
    ("mars", "mi"): ("mars_hcp", ((-90, 90),), "u"),
    ("mars", "iarti"): ("ti", ((-90, 90),), "u"),
    ("mars", "su"): ("swim", ((-60, 60),), "u+"),
    ("mars", "toz"): ("dci", ((-90, 90),), "ters"),
    ("mars", "isik"): ("berger_mars", ((-90, 90),), "u"),
}
_SIRA = {}


def sira(govde, ozellik, n_en_fazla=None, onbellek=True):
    """P_f,B'den sıra fonksiyonu (Sira / SiraPozitif). Varsayılan: ≤ 10⁶ değer, ara\\ref_<gövde>_<özellik>.npy önbelleği."""
    anahtar = (govde, ozellik, n_en_fazla)
    if anahtar in _SIRA:
        return _SIRA[anahtar]
    kat, bant, tur = OZELLIK[(govde, ozellik)]
    yol = ARA / f"ref_{govde}_{ozellik}.npy"
    if onbellek and n_en_fazla is None and yol.exists():
        v = np.load(yol)
    else:
        v, bilgi = U.referans_orneklem(f"{govde}_{ozellik}", ac(kat).ornekle, bantlar=bant, n_en_fazla=n_en_fazla)
        if onbellek and n_en_fazla is None:
            np.save(yol, v)
            yol.with_suffix(".json").write_text(json.dumps(bilgi, ensure_ascii=False, indent=1), encoding="utf-8")
    s = U.SiraPozitif(v) if tur == "u+" else U.Sira(v)
    s.tur = tur
    _SIRA[anahtar] = s
    return s


def sirala(s, x):
    """Belge 5.2: u, u⁺ ya da ters (1 − u)."""
    return s.ters(x) if getattr(s, "tur", "u") == "ters" else s(x)


# =============================================================== 5. pencere temsilleri
def _hucre(ad, phi0, lam0, r, alt=False):
    v, coarse, s = K.hucreye(ac(ad), phi0, lam0, r, alt=alt)
    return v


def _Q(u):
    u = np.asarray(u, float)
    return U.yuzdelik(u.reshape(*u.shape[:-2], -1)).astype(np.float32)


def termal_ozellikleri(govde, lat0_der):
    """Belge 6.5 F₅ (hedefin cisminde de bulunanlar). Dünya referans tarafı dördünü de tutar."""
    if govde == "mars":
        return ["iarti"]
    if govde == "ay":
        return ["tmax", "tort", "tgece"] if abs(lat0_der) >= float(A.ayar("termal.ay_prp_sinir_der")) else ["tgece"]
    return ["tmax", "tort", "tgece", "iarti"]


def pencere_temsili(govde, phi0, lam0, kategoriler=(3, 4, 5, 6, 7, 8), n_ref=None):
    """Pencereler (radyan dizileri) için kategori 3–8 temsilleri:
    q3 (nw, 6), q3_gecerli; x4_gecerli (nw,), Q4 (nw, M); Q5[f] (nw, M); Q6 (nw, M); Q7; Q8;
    hedef bilgileri: pi_arti (Ay/Mars). n_ref: test için küçük referans (None = 10⁶, önbellekli)."""
    phi0 = np.atleast_1d(np.asarray(phi0, float))
    lam0 = np.atleast_1d(np.asarray(lam0, float))
    r = float(A.ayar("cisim.yaricap_km")[govde])
    T = {}
    if 3 in kategoriler:
        vek = ac({"dunya": "glim", "ay": "ay_jeoloji", "mars": "sim3292"}[govde])
        G = sozluk_matrisi(govde, list(vek.siniflar))
        pay, _ = K.hucreye_sinif(vek, phi0, lam0, r)
        kb = _hucre("mcd12c1_15", phi0, lam0, r) / 100.0 if govde == "dunya" else None
        T["q3"], T["q3_gecerli"] = pencere_jeoloji(hucre_grup_paylari(pay, G, kb))
    if 4 in kategoriler:
        x = _hucre({"dunya": "cmg_mi", "ay": "lpgrs_w_feo", "mars": "mars_hcp"}[govde], phi0, lam0, r)
        T["x4_gecerli"] = gecerli_oran(x)
        T["Q4"] = _Q(sirala(sira(govde, "mi", n_ref), x))
    if 5 in kategoriler:
        adlar = {"dunya": {"tmax": "cmg_tmax", "tort": "cmg_tort", "tgece": "cmg_tgece", "iarti": "cmg_iarti"},
                 "ay": {"tmax": "prp_temp_max", "tort": "prp_temp_avg", "tgece": "ay_tgece"},
                 "mars": {"iarti": "ti"}}[govde]
        for f, kat in adlar.items():
            T[f"Q5_{f}"] = _Q(sirala(sira(govde, f, n_ref), _hucre(kat, phi0, lam0, r)))
    if 6 in kategoriler:
        x = _hucre({"dunya": "perm_sifir", "ay": "hidrojen_th", "mars": "swim"}[govde], phi0, lam0, r)
        T["Q6"] = _Q(sirala(sira(govde, "su", n_ref), x))
        if govde == "mars":
            T["pi_arti"] = pi_arti(x > 0, np.isfinite(x))
        elif govde == "ay":
            b = _hucre("prp_ice_depth_bayrak", phi0, lam0, r, alt=True)  # (nw, n, n, s²)
            veri = np.isfinite(b)
            poz = veri & (b != 1)
            nv = veri.sum(-1)
            with np.errstate(invalid="ignore", divide="ignore"):
                oran = np.where(nv > 0, poz.sum(-1) / np.maximum(nv, 1), np.nan)
            T["pi_arti"] = pi_arti(np.nan_to_num(oran) >= 0.5, nv > 0)
    if 7 in kategoriler:
        x = _hucre({"dunya": "siltkil", "ay": "ra", "mars": "dci"}[govde], phi0, lam0, r)
        T["Q7"] = _Q(sirala(sira(govde, "toz", n_ref), x))
    if 8 in kategoriler:
        if govde == "ay":
            sinir = float(A.ayar("aydinlanma.ay_pgda_sinir_der"))
            lat, _ = K._alt_noktalar(phi0, lam0, r, 0, 1)
            lat = lat[..., 0, 0]
            up = sirala(sira("ay", "isik_pgda", n_ref), _hucre("pgda", phi0, lam0, r))
            ub = sirala(sira("ay", "isik_berger", n_ref), _hucre("berger_ay", phi0, lam0, r))
            u = np.where(np.abs(lat) >= sinir, up, ub)
        else:
            u = sirala(sira(govde, "isik", n_ref), _hucre(f"berger_{govde}", phi0, lam0, r))
        T["Q8"] = _Q(u)
    return T


# =============================================================== 6. uzaklıklar d₃ … d₈
def d3(qA, qT):
    """Belge 6.3: d₃ = TV(q(A), q(T))."""
    return U.tv(qA, qT)


def d4(QA, gecA, QT, gecT):
    """Belge 6.4: W₁(u[A], u[T]); pencerede değerli hücre oranı < %50 (iki taraftan biri) → null."""
    esik = float(A.ayar("mineraloji.gecerlilik_orani"))
    d = U.w1(QA, QT)
    return np.where((np.asarray(gecA) >= esik) & (float(gecT) >= esik), d, np.nan)


def d5(QA_dict, QT_dict, F5):
    """Belge 6.5: (1/|F₅|) Σ_f W₁; bir F₅ özelliği adayda yoksa null."""
    w = np.stack([U.w1(QA_dict[f], QT_dict[f]) for f in F5], axis=0)
    return np.mean(w, axis=0)  # NaN yayılır → null


def d_dagilim(QA, QT):
    """Belge 6.6–6.8: d = W₁ (u ya da u⁺ dağılımları); değer yoksa null (NaN)."""
    return U.w1(QA, QT)
''', encoding="utf-8")
(KOD / "testler" / "test_ozellik_diger.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 8.2 (C₁, I⊕, su/buz sıfır kuralı, ıslak/kuru, aydınlanma, mineraloji) ve 6.3–6.8 sentetik pencere testleri."""
import datetime
import math
import numpy as np
import pandas as pd
import pytest
import ayar as A
import katman as K
import ozellik_diger as O
import uzaklik as U

r = math.radians


@pytest.mark.parametrize("phi,delta,beklenen", [(0, 0, math.pi / 2), (45, 20, 1.5165),
                                                (80, 20, math.pi * math.cos(r(80)) * math.cos(r(20))),
                                                (80, -20, 0.0), (69.99, 20, 1.0102), (70.01, 20, 1.0092)])
def test_C1_8_2(phi, delta, beklenen):
    assert abs(float(O.C1(r(phi), r(delta))) - beklenen) < 1e-4


def test_C1_kutup_gunu_degeri_8_2():
    assert abs(float(O.C1(r(80), r(20))) - 0.5126) < 1e-4


def test_I_arti_8_2():
    assert abs(float(O.I_arti_ay(1.0, 0.2, 10.0)) - 0.08) < 1e-15
    # kutup gecesi: C₁ = 0 olan ay ortalamaya girmez
    aylar = O.I_arti_ay(np.array([1.0, 0.0, 1.0]), np.array([0.2, 0.2, 0.2]), np.array([10.0, 10.0, 5.0]))
    assert np.isnan(aylar[1]) and abs(np.nanmean(aylar) - (0.08 + 0.16) / 2) < 1e-15
    assert np.isnan(O.I_arti_ay(1.0, 0.2, 0.0)) and np.isnan(O.I_arti_ay(1.0, 0.2, -3.0))


def test_su_buz_sifir_kurali_8_2():
    # haritada değeri olmayan kara hücresi: kar/buz 0,2 → x = 0; 0,7 → hesap dışı
    x = O.sifir_kurali(np.array([np.nan, np.nan, 0.6, np.nan]), np.array([0.2, 0.7, 0.1, 0.0]), np.array([1.0, 1.0, 1.0, 0.2]))
    assert x[0] == 0.0 and np.isnan(x[1]) and abs(x[2] - 0.6) < 1e-7 and np.isnan(x[3])


def test_islak_kuru_8_2():
    poz = np.zeros((40, 40), bool); poz.ravel()[:800] = True
    veri = np.ones((40, 40), bool)
    assert O.pi_arti(poz, veri) == 0.5 and O.islak_mi(O.pi_arti(poz, veri))
    poz.ravel()[799] = False
    assert not O.islak_mi(O.pi_arti(poz, veri))
    assert not O.islak_mi(O.pi_arti(poz, np.zeros_like(veri)))  # kapsam dışı → kuru


@pytest.mark.parametrize("phi,delta,beklenen", [(0, 0, 1 / math.pi), (90, 23.44, math.sin(r(23.44))), (90, -23.44, 0.0)])
def test_aydinlanma_8_2(phi, delta, beklenen):
    assert abs(float(O.berger_gunluk(r(phi), r(delta))) - beklenen) < 1e-12
    assert abs(math.sin(r(23.44)) - 0.3978) < 1e-4


def test_berger_tablosu_ara_deger():
    for eps in (23.44, 1.54, 25.19):
        t = O.BergerTablosu(eps)
        lat = np.concatenate([np.random.default_rng(0).uniform(-90, 90, 300), 90 - eps + np.linspace(-0.01, 0.01, 50)])
        assert np.max(np.abs(t(lat) - O.berger_yillik(np.radians(lat), eps))) < 1e-8, eps
    # ekvatorda ε = 0 → f = 1/π
    assert abs(O.berger_yillik(0.0, 0.0)[0] - 1 / math.pi) < 1e-12


def test_deklinasyon():
    _, dh = O.gunes_boylami_ve_deklinasyon(datetime.date(2023, 6, 21))
    _, dk = O.gunes_boylami_ve_deklinasyon(datetime.date(2023, 12, 22))
    _, de = O.gunes_boylami_ve_deklinasyon(datetime.date(2023, 3, 20))
    assert abs(math.degrees(dh) - 23.44) < 0.05 and abs(math.degrees(dk) + 23.44) < 0.05 and abs(math.degrees(de)) < 0.5


def test_mars_mineraloji_8_2():
    assert abs(float(O.mars_hcp(0.2, 0.1, 0.1)) - 0.25) < 1e-15
    assert np.isnan(O.mars_hcp(0.2, 0.1, np.nan)) and np.isnan(O.mars_hcp(0.0, 0.0, 0.0))


def test_mineraloji_gecersiz_pencere_8_2():
    Q = np.zeros(1000)
    assert np.isnan(O.d4(Q, 0.40, Q, 1.0)) and O.d4(Q, 0.50, Q, 1.0) == 0.0 and np.isnan(O.d4(Q, 1.0, Q, 0.4))
    x = np.full((40, 40), np.nan); x.ravel()[:640] = 1.0
    assert O.gecerli_oran(x) == 0.4


def test_mafik_indeks():
    assert abs(float(O.mafik_indeks(0.95, 0.97, 0.96)) - 0.95 * 0.96 ** 3 / 0.97 ** 4) < 1e-15


def _sozluk(tmp_path, satirlar):
    p = tmp_path / "s.csv"
    pd.DataFrame(satirlar, columns=["cisim", "birim_kodu", "birim_aciklama", "grup", "kaynak"]).to_csv(p, index=False)
    return p


def test_sozluk_assertleri(tmp_path):
    p = _sozluk(tmp_path, [("mars", "a", "", "volkanik", ""), ("mars", "b", "", "yayla_yarim", ""), ("mars", "c", "", "", "")])
    with pytest.raises(AssertionError, match="grubu boş"):
        O.sozluk_matrisi("mars", ["a", "b", "c"], p)
    with pytest.raises(AssertionError, match="sözlükte olmayan"):
        O.sozluk_matrisi("mars", ["a", "z"], p)
    p2 = _sozluk(tmp_path, [("mars", "a", "", "volkanikk", "")])
    with pytest.raises(AssertionError, match="izinsiz"):
        O.sozluk_matrisi("mars", ["a"], p2)
    p3 = _sozluk(tmp_path, [("mars", "a", "", "volkanik", ""), ("mars", "b", "", "yayla_yarim", ""), ("mars", "w", "", "hesap_disi", "")])
    G = O.sozluk_matrisi("mars", ["a", "b", "w"], p3)
    assert G[0].tolist() == [1, 0, 0, 0, 0, 0] and G[1].tolist() == [0.5, 0, 0, 0.5, 0, 0] and G[2].sum() == 0


def test_grup_paylari_ve_kar_buz():
    G = np.array([[1, 0, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 0]], float)  # volkanik, tortul, hesap dışı
    pay = np.array([[0.5, 0.3, 0.2], [0, 0, 1.0], [np.nan, np.nan, np.nan]])
    q = O.hucre_grup_paylari(pay, G)
    assert np.allclose(q[0], [0.625, 0, 0, 0.375, 0, 0]) and np.isnan(q[1]).all() and np.isnan(q[2]).all()
    qk = O.hucre_grup_paylari(pay, G, kar_buz=np.array([0.2, 0.5, 0.0]))
    assert np.allclose(qk[0], [0.5, 0, 0, 0.3, 0, 0.2]) and np.allclose(qk[1], [0, 0, 0, 0, 0, 1]) and np.isnan(qk[2]).all()


def test_pencere_jeoloji_ve_tv():
    qh = np.full((2, 2, 6), np.nan)
    qh[0, 0] = [1, 0, 0, 0, 0, 0]; qh[0, 1] = [0, 0, 0, 1, 0, 0]; qh[1, 0] = [1, 0, 0, 0, 0, 0]
    q, gec = O.pencere_jeoloji(qh)
    assert np.allclose(q, [2 / 3, 0, 0, 1 / 3, 0, 0]) and gec == 0.75
    assert abs(O.d3(q, [0, 0, 0, 1, 0, 0]) - 2 / 3) < 1e-12


# ------------------------------------------------ sentetik katmanlarla pencere hattı
def _sahte(monkeypatch, katmanlar):
    for ad, k in katmanlar.items():
        monkeypatch.setitem(O._OD, ad, k)
    monkeypatch.setattr(O, "_SIRA", {})


def _cografi(ad, f, ppd, y0=90.0, nrow=None):
    nrow = int(180 * ppd) if nrow is None else nrow
    lat = y0 - (np.arange(nrow) + 0.5) / ppd
    lon = -180 + (np.arange(int(360 * ppd)) + 0.5) / ppd
    return K.Cografi(ad, f(lat[:, None], lon[None, :]).astype(np.float32), -180.0, 1 / ppd, y0, 1 / ppd, nrow, int(360 * ppd), "")


def test_mars_pencere_hatti(monkeypatch):
    _sahte(monkeypatch, {
        "mars_hcp": _cografi("mars_hcp", lambda la, lo: 0.3 + 0.001 * la + 0 * lo, 4),
        "ti": _cografi("ti", lambda la, lo: 200 + la + 0.1 * lo, 20),
        "swim": _cografi("swim", lambda la, lo: np.sin(np.radians(lo)) + 0 * la, 20, y0=60.0, nrow=2400),
        "dci": _cografi("dci", lambda la, lo: 0.95 + 0 * la + 0 * lo, 16),
    })
    phi0, lam0 = np.radians([18.44, 18.44]), np.radians([77.45, 77.45])
    T = O.pencere_temsili("mars", phi0, lam0, kategoriler=(4, 5, 6, 7, 8), n_ref=20000)
    for k in ("Q4", "Q5_iarti", "Q6", "Q7", "Q8"):
        assert T[k].shape == (2, 1000) and np.isfinite(T[k]).all(), k
        assert np.array_equal(T[k][0], T[k][1])
    assert T["x4_gecerli"].tolist() == [1.0, 1.0]
    assert T["pi_arti"][0] == 1.0 and O.islak_mi(T["pi_arti"])[0]  # sin(77°) > 0 → bütün hücreler pozitif
    assert np.all((T["Q8"] >= 0) & (T["Q8"] <= 1))
    # aynı pencereye uzaklık 0
    assert O.d_dagilim(T["Q6"][0], T["Q6"][1]) == 0 and O.d4(T["Q4"][0], 1.0, T["Q4"][1], 1.0) == 0
    assert O.d5({"iarti": T["Q5_iarti"][0]}, {"iarti": T["Q5_iarti"][1]}, ["iarti"]) == 0


def test_ay_pencere_hatti_pi_arti_ve_aydinlanma(monkeypatch):
    # PRP bayrağı: boylam < 30° sansürlü (1), ≥ 30° değer (0); M-SP (−89, 30) penceresinde iki taraf da var
    bay = O.Fonksiyon("b", lambda la, lo: np.where(la < -75.9, np.where(lo < 30.0, 1.0, 0.0), np.nan), lambda la, rr: (0.2, 0.2))
    _sahte(monkeypatch, {
        "prp_ice_depth_bayrak": bay,
        "hidrojen_th": _cografi("h", lambda la, lo: 100 + 0 * la + 0 * lo, 2),
        "pgda": O.Fonksiyon("p", lambda la, lo: np.where(np.abs(la) >= 65, 0.3 + 0 * lo, np.nan), O._kaba),
        "berger_ay": O.Fonksiyon("b", lambda la, lo: 0.3 - 0.001 * np.abs(la) + 0 * lo, O._kaba),
        "ra": _cografi("ra", lambda la, lo: 0.01 + 0 * la + 0 * lo, 4, y0=70.0, nrow=560),
    })
    T = O.pencere_temsili("ay", np.radians([-89.0]), np.radians([30.0]), kategoriler=(6, 7, 8), n_ref=5000)
    assert 0.3 < T["pi_arti"][0] < 0.7               # yaklaşık yarısı pozitif
    assert np.isnan(T["Q7"]).all()                    # 70° ötesinde kaya bolluğu yok → null
    assert np.isfinite(T["Q8"]).all()                 # 65° ötesi PGDA sırası
    T2 = O.pencere_temsili("ay", np.radians([0.0]), np.radians([0.0]), kategoriler=(6, 8), n_ref=5000)
    assert np.isnan(T2["pi_arti"][0]) and not O.islak_mi(T2["pi_arti"])[0]  # 75,9° berisi → kuru


def test_termal_ozellikleri():
    assert O.termal_ozellikleri("ay", -85.0) == ["tmax", "tort", "tgece"]
    assert O.termal_ozellikleri("ay", -72.0) == ["tgece"] and O.termal_ozellikleri("ay", 10.0) == ["tgece"]
    assert O.termal_ozellikleri("mars", 18.0) == ["iarti"] and len(O.termal_ozellikleri("dunya", 0.0)) == 4
''', encoding="utf-8")
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
    aralik = {"tmax": (150, 400), "tort": (150, 350), "tgece": (150, 330), "mi": (0.5, 2.0), "iarti": (0, 10)}
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

yol = KOD / "FONKSIYONLAR.md"
metin = yol.read_text(encoding="utf-8")
bas, son = "<!-- ozellik_diger.py -->", "<!-- /ozellik_diger.py -->"
blok = bas + "\n## ozellik_diger.py\n" + "\n".join("- " + s for s in [
    "6.3 q_c(W), kar/buz → buz → `ozellik_diger.hucre_grup_paylari`, `ozellik_diger.pencere_jeoloji`; sözlük → `ozellik_diger.sozluk_matrisi`; d₃ → `ozellik_diger.d3`",
    "6.4 MI → `ozellik_diger.mafik_indeks`; Mars x → `ozellik_diger.mars_hcp`; d₄ (%50 kuralı) → `ozellik_diger.d4`",
    "6.5 C₁ → `ozellik_diger.C1`; I⊕ → `ozellik_diger.I_arti_ay`; δ⊙ → `ozellik_diger.gunes_boylami_ve_deklinasyon`; F₅ → `ozellik_diger.termal_ozellikleri`; d₅ → `ozellik_diger.d5`",
    "6.6 sıfır kuralı → `ozellik_diger.sifir_kurali`; π⁺ → `ozellik_diger.pi_arti`; ıslak/kuru → `ozellik_diger.islak_mi`",
    "6.8 Q̄_gün → `ozellik_diger.berger_gunluk`; f(φ) → `ozellik_diger.berger_yillik` (tablo `BergerTablosu`)",
    "6.3–6.8 pencere temsilleri → `ozellik_diger.pencere_temsili`; P_f,B sıraları → `ozellik_diger.sira`; Dünya CMG ızgaraları → `ozellik_diger.dunya_cmg`"]) + "\n" + son
metin = (metin.split(bas)[0] + blok + metin.split(son)[1]) if bas in metin else (metin.rstrip() + "\n\n" + blok + "\n")
yol.write_text(metin, encoding="utf-8")

deg = KAYIT / "degisiklik.md"
satirlar = [
    "- 2026-11-14 | Belge 6.5 Dünya termal okuması: Tmax = aylık gündüz LST'nin en büyüğü; T̄ = aylık (gündüz+gece)/2'nin yıllık ortalaması; Tgece = aylık gece LST'nin yıllık ortalaması | dayanak: 6.5 'Aqua öğleden sonra geçişi günlük maksimuma yakın' | etkisi: Method 6.5 metni\n",
    "- 2026-11-14 | Belge 6.5 I⊕: aylık; C₁ = 0 ya da ΔTg ≤ 0 ayı ortalamaya girmez (ΔTg ≤ 0 proje kararı); δ⊙ ayın 15'i, düşük duyarlıklı güneş formülü (Astronomical Almanac), sin δ = sin ε sin λ | etkisi: Method 6.5\n",
    "- 2026-11-14 | Belge 6.4 ASTER MI: her bandın 12 aylık ortalamasından | etkisi: Method 6.4\n",
    "- 2026-11-14 | Belge 6.8 Ay aydınlanması: |φ| ≥ 65° PGDA ve |φ| < 65° Berger hücreleri kendi kapsamlarında ayrı sıralanır | neden: iki büyüklük farklı | etkisi: Method 6.8\n",
    "- 2026-11-14 | Belge 6.6: kara hücresi = MCD12C1 kara payı ≥ 0,5; Ay π⁺ hücre pozitifliği = alt örneklerin ≥ yarısında ice_depth ≠ −999 (proje kararı) | etkisi: Method 6.6\n",
]
d = deg.read_text(encoding="utf-8")
yeni = [s for s in satirlar if s.split(" | ")[1][:35] not in d]
if yeni:
    deg.write_text(d + "".join(yeni), encoding="utf-8")

r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--durations=6", "testler"],
                   cwd=KOD, capture_output=True, text=True)
cikti = r.stdout + r.stderr
(KAYIT / "D4_test_ozellik_diger.txt").write_text(cikti, encoding="utf-8")
print(cikti[-5000:])
durum = "PASS" if r.returncode == 0 else "FAIL"
with open(KAYIT / "14_kasim_log.txt", "a", encoding="utf-8") as f:
    f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\tozellik_diger.py+test\t{durum}\n")
print(f"\ntestler: {durum}")
