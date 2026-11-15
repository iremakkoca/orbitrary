# Developed with assistance from Claude (Anthropic).
# Madde 29 (Sude 12:57): yıllık I⊕ = Σ C₁(1 − α) / Σ ΔTg (geçerli aylar). Yalnız ara\cmg_iarti yeniden üretilir.
# Ardından kayit\iarti_olcum.json: aynı piksellerde |u(oranların ortalaması) − u(ortalamaların oranı)|.
import sys, json, hashlib, importlib, datetime, warnings
from pathlib import Path
import numpy as np
KOK = Path.home() / "orbitrary"; KOD, KAYIT, ARA = KOK / "kod", KOK / "kayit", KOK / "ara"
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))

# 1) Değiştirilecek dosya beklenen sürüm mü? Değilse hiçbir şey yazılmaz.
od_yol = KOD / "ozellik_diger.py"
h = hashlib.sha256(od_yol.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
assert h == "d5602df946dc6dea7dfb7090ce22fb30253958414e3bfe7e54628760ab4eaef4", "ozellik_diger.py beklenen sürüm değil — DUR, bana haber ver: " + h
tyol = KOD / "testler" / "test_ozellik_diger.py"
tmetin = tyol.read_text(encoding="utf-8")
assert "test_I_arti_yillik_madde29" not in tmetin

# 2) Kod + birim testi + kayıtlar
od_yol.write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 6.3–6.8: jeoloji (3), mineraloji (4), termal (5), su/buz (6), toz (7), aydınlanma (8).

Formüller (saf fonksiyonlar) → türetilmiş katmanlar (ornekle/cozunurluk_km; katman.hucreye ile hücreye) →
pencere temsilleri (sınıf payları, sıra dağılımlarının 1000 noktalı yüzdelik vektörleri) → d₃ … d₈.

Okuma kararları (14 Kasım; kayit\\degisiklik.md):
- Dünya Tmax = 12 aylık gündüz LST'nin en büyüğü; T̄ = aylık (gündüz + gece)/2'nin yıllık ortalaması;
  Tgece = aylık gece LST'nin yıllık ortalaması.
- I⊕ aylık; C₁ = 0 ya da ΔTg ≤ 0 olan ay yıllık toplamlara girmez; yıllık I⊕ = Σ C₁(1 − α) / Σ ΔTg (madde 29, Sude). δ⊙: ayın 15'i, düşük duyarlıklı güneş formülü
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


def I_arti_yillik(pay_top, payda_top, n):
    """Madde 29 (Sude, 14 Kasım; D8'den önce, sonuçlara bakılmadan): I⊕ yıllık = Σ C₁(1 − α) / Σ ΔTg; toplamlar
    aylık I⊕'nin geçerli olduğu aylar (C₁ > 0, ΔTg > 0, α var) üzerinden. Bu, aylık I⊕'nin ΔTg ağırlıklı ortalamasıdır.
    Geçerli ay yoksa NaN."""
    pay_top, payda_top, n = (np.asarray(v, float) for v in (pay_top, payda_top, n))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, pay_top / np.where(n > 0, payda_top, 1.0), np.nan)


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
    eksik = {a for a, p in yollar.items() if not p.exists()}
    if not eksik:
        return yollar
    gt = [-180.0, 0.05, 0.0, 90.0, 0.0, -0.05]
    bilgi = {}

    def yukle(ad):
        k = K.ac(ad)
        assert k.tur == "cografi" and (k.x0, k.dx, k.y0, k.dy) == (-180.0, 0.05, 90.0, 0.05), ad
        return np.asarray(k.kaynak, dtype=np.float32)

    # MI: her bandın 12 aylık ortalaması
    mi = None
    if "mi" in eksik:
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
    top_pay = np.zeros((3600, 7200), np.float64); top_payda = np.zeros((3600, 7200), np.float64)
    n_i = np.zeros((3600, 7200), np.int16)
    for ay in range(1, 13):
        D, N, a = yukle(gun[ay]), yukle(gec[ay]), yukle(alb[ay])
        tmax = np.fmax(tmax, D)
        m = np.isfinite(D) & np.isfinite(N)
        top_ort += np.where(m, (D + N) / 2, 0); n_ort += m
        mg = np.isfinite(N)
        top_gece += np.where(mg, N, 0); n_gece += mg
        _, d = gunes_boylami_ve_deklinasyon(datetime.date(2023, ay, 15))
        c1 = C1(np.radians(lat_c), d)[:, None]
        dT = D - N
        I = I_arti_ay(c1, a, dT)
        mi_ = np.isfinite(I)
        top_pay += np.where(mi_, c1 * (1.0 - a), 0); top_payda += np.where(mi_, dT, 0); n_i += mi_
        bilgi[f"ay_{ay:02d}"] = {"gunduz": gun[ay], "gece": gec[ay], "albedo": alb[ay],
                                 "deklinasyon_der": round(math.degrees(d), 4), "iarti_gecerli": int(mi_.sum())}
    with np.errstate(invalid="ignore", divide="ignore"):
        ciktilar = {"mi": mi,
                    "tmax": np.where(np.isfinite(tmax), tmax, np.nan).astype(np.float32),
                    "tort": np.where(n_ort > 0, top_ort / np.maximum(n_ort, 1), np.nan).astype(np.float32),
                    "tgece": np.where(n_gece > 0, top_gece / np.maximum(n_gece, 1), np.nan).astype(np.float32),
                    "iarti": I_arti_yillik(top_pay, top_payda, n_i).astype(np.float32)}
    ciktilar = {ad: v for ad, v in ciktilar.items() if ad in eksik}
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
        # Belge 6.5 F₅: Ay'da Tmax ve T̄ (PRP) yalnız |φ₀| ≥ 76° pencerelerde; diğerlerinde null (hesaplanmaz)
        lat0 = np.degrees(phi0)
        for f, kat in adlar.items():
            gerek = np.array([f in termal_ozellikleri(govde, float(la)) for la in lat0])
            Q = np.full((len(phi0), U.M()), np.nan, np.float32)
            if gerek.any():
                Q[gerek] = _Q(sirala(sira(govde, f, n_ref), _hucre(kat, phi0[gerek], lam0[gerek], r)))
            T[f"Q5_{f}"] = Q
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
tyol.write_text(tmetin.rstrip() + "\n" + r'''def test_I_arti_yillik_madde29():
    # Σ C₁(1 − α) / Σ ΔTg = aylık I⊕'nin ΔTg ağırlıklı ortalaması; geçersiz ay (NaN) toplamlara girmez
    rng = np.random.default_rng(29)
    c1 = rng.uniform(0.1, 1.6, (12, 50)); a = rng.uniform(0, 0.9, (12, 50)); dT = rng.uniform(0.02, 40, (12, 50))
    dT[0, :10] = -1.0; c1[1, 10:20] = 0.0; a[2, 20:30] = np.nan
    I = O.I_arti_ay(c1, a, dT)
    g = np.isfinite(I)
    Iy = O.I_arti_yillik(np.where(g, c1 * (1 - a), 0).sum(0), np.where(g, dT, 0).sum(0), g.sum(0))
    w = np.where(g, dT, 0)
    np.testing.assert_allclose(Iy, np.nansum(I * w, 0) / w.sum(0), rtol=1e-12)
    assert np.all(Iy <= np.nanmax(I, 0) + 1e-12) and np.all(Iy >= np.nanmin(I, 0) - 1e-12)
    assert np.isnan(O.I_arti_yillik(0.0, 0.0, 0))
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
| 29 | I⊕ yıllık değeri: oranların ortalaması (belge) küçük paydalı aylara duyarlı. **Karar (Sude, 12:57; D8'den önce, sonuçlara bakılmadan):** ortalamaların oranı, I⊕ = Σ C₁(1 − α) / Σ ΔTg, toplam C₁ > 0, ΔTg > 0 (ve α var) olan geçerli aylar üzerinden. Cebirsel olarak aylık I⊕'nin ΔTg ağırlıklı ortalaması; ΔTg ≈ 0 olan ay yıllık değeri ele geçiremez. MI'deki "önce ortalama" (madde 7) ile tutarlı | 6.5 | Evet: yalnız ozellik_diger yıllık I⊕ (`I_arti_yillik`) ve ara\cmg_iarti.npy yeniden üretildi; sınır (≤ 82,1) aynı | uygulandı; gerekçe büyüklüğü `kayit\iarti_olcum.json` (|u_eski − u_yeni|: ortanca, %95, en büyük) |
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
''', encoding="utf-8")
fy = KOD / "FONKSIYONLAR.md"; fm = fy.read_text(encoding="utf-8")
a = "I⊕ → `ozellik_diger.I_arti_ay`"
assert fm.count(a) == 1
fy.write_text(fm.replace(a, "I⊕ aylık → `ozellik_diger.I_arti_ay`; yıllık Σ C₁(1 − α)/Σ ΔTg (madde 29) → `ozellik_diger.I_arti_yillik`"), encoding="utf-8")

# 3) Yalnız I⊕ ürünlerini kaldır (diğer CMG dosyaları dokunulmaz; önce/sonra SHA)
digerleri = [ARA / f"cmg_{a}.npy" for a in ("mi", "tmax", "tort", "tgece")]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
once = {p.name: sha(p) for p in digerleri}
for p in (ARA / "cmg_iarti.npy", ARA / "cmg_iarti.json", ARA / "ref_dunya_iarti.npy"):
    if p.exists(): p.unlink(); print("silindi:", p.name)
if (KAYIT / "iarti_olcum.json").exists():
    (KAYIT / "iarti_olcum.json").replace(KAYIT / "iarti_olcum_1206.json")   # önceki ölçüm (ortanca karşılaştırması) saklanır

import katman as K; import ozellik_diger as O
importlib.reload(K); importlib.reload(O)
t0 = datetime.datetime.now()
print("cmg_iarti yeniden üretiliyor (12 ay LST + albedo)...", flush=True)
yol = O.dunya_cmg()
print("bitti:", (datetime.datetime.now() - t0).seconds, "s")
assert {p.name: sha(p) for p in digerleri} == once, "MI/Tmax/T̄/Tgece dosyaları değişti!"
yeni = np.load(yol["iarti"])
j = json.loads(Path(yol["iarti"]).with_suffix(".json").read_text(encoding="utf-8"))
print("cmg_iarti.json: geçerli", j["gecerli"], "en küçük", j["en_kucuk"], "en büyük", j["en_buyuk"])

# 4) Ölçüm (gerekçenin büyüklüğü; yöntem yeni formül): aynı geçerli aylar, iki yıllık birleştirme
gun = {O._tarih(a).month: a for a in K.aylik("E5", "lst_gunduz")}
gec = {O._tarih(a).month: a for a in K.aylik("E5", "lst_gece")}
alb = {O._tarih(a).month: a for a in K.aylik("E6", "albedo_wsa")}
lat_c = 90.0 - (np.arange(3600) + 0.5) * 0.05; lon_c = -180.0 + (np.arange(7200) + 0.5) * 0.05
top_I = np.zeros((3600, 7200)); top_pay = np.zeros((3600, 7200)); top_payda = np.zeros((3600, 7200))
n = np.zeros((3600, 7200), np.int16)
for ay in range(1, 13):
    D = np.asarray(K.ac(gun[ay]).kaynak, np.float32); N = np.asarray(K.ac(gec[ay]).kaynak, np.float32)
    a_ = np.asarray(K.ac(alb[ay]).kaynak, np.float32)
    _, d = O.gunes_boylami_ve_deklinasyon(datetime.date(2023, ay, 15))
    c1 = O.C1(np.radians(lat_c), d)[:, None]
    dT = D - N
    I = O.I_arti_ay(c1, a_, dT); g = np.isfinite(I)
    top_I += np.where(g, I, 0); top_pay += np.where(g, c1 * (1 - a_), 0); top_payda += np.where(g, dT, 0); n += g
    del D, N, a_, dT, I, g
    print(f"   ay {ay:02d}", flush=True)
with warnings.catch_warnings():
    warnings.simplefilter("ignore", RuntimeWarning)
    eski = np.where(n > 0, top_I / np.maximum(n, 1), np.nan)
    kontrol = O.I_arti_yillik(top_pay, top_payda, n)
assert np.allclose(kontrol, yeni, rtol=1e-5, equal_nan=True), "ara\\cmg_iarti.npy bağımsız hesapla tutmuyor"

def agirlikli_sira(x, w):
    """cos φ ağırlıklı ECDF sırası (belge 5.2 biçimi): u = (W_<x + ½ W_=x) / W."""
    g = np.isfinite(x); xv, wv = x[g].astype(np.float64), w[g]
    uniq, ters = np.unique(xv, return_inverse=True)
    ws = np.bincount(ters, weights=wv); once_ = np.concatenate([[0.0], np.cumsum(ws)[:-1]])
    u = np.full(x.shape, np.nan); u[g] = ((once_ + 0.5 * ws) / wv.sum())[ters]
    return u
w = np.broadcast_to(np.cos(np.radians(lat_c))[:, None], yeni.shape)
ortak = np.isfinite(eski) & np.isfinite(yeni)
fark = np.abs(agirlikli_sira(np.where(ortak, eski, np.nan), w) - agirlikli_sira(np.where(ortak, yeni, np.nan), w))
def ozet(v): v = v[np.isfinite(v)]; return {"ortanca": round(float(np.median(v)), 4), "yuzde95": round(float(np.percentile(v, 95)), 4), "en_buyuk": round(float(v.max()), 4)}
en10 = np.argsort(np.where(np.isfinite(fark), fark, -1).ravel())[::-1][:10]
r, c = np.unravel_index(en10, fark.shape)
olcum = {"tanim": {"yontem": "madde 29 (Sude 12:57): I⊕ yıllık = Σ C₁(1 − α) / Σ ΔTg, geçerli aylar (C₁ > 0, ΔTg > 0, α var)",
                   "karsilastirilan": "aylık I⊕'nin düz ortalaması (belgedeki ilk okuma), aynı geçerli aylar",
                   "fark": "|u_eski − u_yeni|, u = cos φ ağırlıklı ECDF sırası (belge 5.2 biçimi), ortak geçerli pikseller"},
         "gecerli_piksel": int(ortak.sum()), "yeni_en_kucuk": float(np.nanmin(yeni)), "yeni_en_buyuk": float(np.nanmax(yeni)),
         "sira_farki": ozet(fark),
         "en_buyuk_fark_10_piksel": [{"enlem": round(float(lat_c[i]), 3), "boylam": round(float(lon_c[k]), 3),
                                      "fark": round(float(fark[i, k]), 4), "gecerli_ay": int(n[i, k]),
                                      "I_eski": round(float(eski[i, k]), 5), "I_yeni": round(float(yeni[i, k]), 5)} for i, k in zip(r, c)]}
(KAYIT / "iarti_olcum.json").write_text(json.dumps(olcum, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: olcum[k] for k in ("gecerli_piksel", "yeni_en_kucuk", "yeni_en_buyuk", "sira_farki")}, ensure_ascii=False, indent=1))
del top_I, top_pay, top_payda, eski, kontrol, fark

with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | Madde 29 (Sude 12:57, D8'den önce, sonuçlara bakılmadan): yıllık I⊕ = Σ C₁(1 − α)/Σ ΔTg, geçerli aylar; "
            "ozellik_diger.I_arti_yillik; yalnız ara\\cmg_iarti + ref_dunya_iarti yeniden üretildi (diğer CMG SHA aynı); "
            "(1 − α) belge 6.5 gereği kaldı (E6 MCD43C3 temiz\\ altında) | etkisi: MAKALEYİ ETKİLER 29, 41–42\n")

# 5) Testler: birim (yeni test dahil bütün dosya) + gerçek veri CMG sınırı (≤ 82,1)
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_ozellik_diger_i29", "testler/test_ozellik_diger.py")
test_kos.calistir("D4_test_cmg_sinir_i29", "testler/test_ozellik_diger_gercek.py", ek=["-k", "cmg"])
