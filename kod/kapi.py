# Developed with assistance from Claude (Anthropic).
"""Belge 7.1–7.2: kara maskesi, uygunluk, dört kapı, yedek kuralı, X (leave-one-out).

Kapı durumları (metin.json adları): passed, passed with fallback threshold, could not be checked, not applicable.
Kod içi kısaltmalar: GECTI, YEDEK, KONTROL_YOK, UYGULANMAZ, KALDI.

Onaylı okuma kararları (14 Kasım, Sude; kayit\\degisiklik.md, MAKALEYİ ETKİLER 20–24):
- W° = pencerenin kara (MCD12C1 kara payı ≥ 0,5) ve kapı verisi olan hücreleri.
- Pv: ASTER NDVI 12 ay → yıllık ortalama (geçerli aylar) → Pv; pencerede ortanca (belge 7.2 "medyan_{W°} P_v").
- Geology kar/buz payı: W° üzerinde ortalama.
- Uygunluk: hedefte verisi olmayan kategori iki taraftan da çıkar.
- X: leave-one-out yalnız V1'in kendi Geology satırlarında; diğer hedeflerde 7 çiftin hepsiyle.
"""
import json
from pathlib import Path

import numpy as np

import ayar as A
import katman as K

ARA = A.KLASOR["ara"]
GECTI, YEDEK, KONTROL_YOK, UYGULANMAZ, KALDI = "passed", "passed with fallback threshold", "could not be checked", "not applicable", "failed"


# ------------------------------------------------------------------ formüller
def kara_payi(su_yuzde):
    """Belge 7.1 / v1.2 D2: kara_ij = 1 − su_ij / 100 (MCD12C1 sınıf 0)."""
    return 1.0 - np.asarray(su_yuzde, float) / 100.0


def maskeden_gecer(kara):
    """Belge 7.1: E′ = {E : (1/N²) Σ kara_ij ≥ 0,9}. kara: (..., n, n); NaN hücre kara sayılmaz (0)."""
    k = np.nan_to_num(np.asarray(kara, float), nan=0.0)
    return k.mean(axis=(-2, -1)) >= float(A.ayar("maske.kara_orani"))


def kara_hucresi(kara):
    """W° için kara hücresi: kara payı ≥ 0,5 (K-1)."""
    k = np.asarray(kara, float)
    return np.isfinite(k) & (k >= 0.5)


def Pv(ndvi):
    """Belge 7.2: P_v = min(1, max(0, (NDVI − 0,2)/(0,5 − 0,2))²) (Sobrino ve ark. [137])."""
    a = float(A.ayar("kapi.jeoloji.NDVI_ciplak"))
    b = float(A.ayar("kapi.jeoloji.NDVI_tam"))
    x = np.asarray(ndvi, float)
    return np.where(np.isfinite(x), np.minimum(1.0, np.maximum(0.0, (x - a) / (b - a)) ** 2), np.nan)


def _w_degerleri(deger, kara):
    """W° hücrelerinin değerleri: (..., n, n) → maske (kara ve veri var)."""
    deger = np.asarray(deger, float)
    return kara_hucresi(kara) & np.isfinite(deger)


def oran_esik_alti(deger, kara, esik):
    """(1/|W°|) Σ 1[x < eşik]; W° boşsa NaN."""
    m = _w_degerleri(deger, kara)
    n = m.sum(axis=(-2, -1))
    a = (m & (np.asarray(deger, float) < esik)).sum(axis=(-2, -1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, a / np.maximum(n, 1), np.nan)


def w_ortalama(deger, kara):
    m = _w_degerleri(deger, kara)
    n = m.sum(axis=(-2, -1))
    s = np.where(m, np.asarray(deger, float), 0.0).sum(axis=(-2, -1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, s / np.maximum(n, 1), np.nan)


def w_ortanca(deger, kara):
    d = np.where(_w_degerleri(deger, kara), np.asarray(deger, float), np.nan)
    d2 = d.reshape(*d.shape[:-2], -1)
    out = np.full(d2.shape[:-1], np.nan)
    gec = np.isfinite(d2).any(axis=-1)
    if gec.any():
        out[gec] = np.nanmedian(d2[gec], axis=-1)
    return out


# ------------------------------------------------------------------ kapı değişkenleri (pencere başına)
def degiskenler(kara, egim_rad=None, perm=None, ai=None, pv=None, kar_buz=None):
    """Pencere başına kapı değişkenleri (her biri (..., n, n) hücre dizisi; verilmeyen None):
    mob = W°'da θ < 20° oranı; buz = W° ortalama permafrost; astro = W° ortanca AI; pv = W° ortanca Pv;
    karbuz = W° ortalama kar/buz payı. W° boşsa NaN (→ could not be checked)."""
    d = {}
    if egim_rad is not None:
        d["mob"] = oran_esik_alti(egim_rad, kara, np.radians(float(A.ayar("kapi.mobility.egim_der"))))
    if perm is not None:
        d["buz"] = w_ortalama(perm, kara)
    if ai is not None:
        d["astro"] = w_ortanca(ai, kara)
    if pv is not None:
        d["pv"] = w_ortanca(pv, kara)
    if kar_buz is not None:
        d["karbuz"] = w_ortalama(kar_buz, kara)
    return d


# ------------------------------------------------------------------ kapılar
def kapi_mobility(mob):
    """G_mob = 1[oran ≥ 0,95]; veri yoksa G = 1, could not be checked. Yedek yok."""
    mob = np.asarray(mob, float)
    G = np.where(np.isfinite(mob), mob >= float(A.ayar("kapi.mobility.hucre_orani")), True)
    durum = np.where(np.isfinite(mob), np.where(G, GECTI, KALDI), KONTROL_YOK)
    return G, durum


def _esikli(x, esik_ana, esik_yedek, yon, yedek_kullan):
    """yon '>=' (buz) ya da '<' (astro)."""
    x = np.asarray(x, float)
    esik = esik_yedek if yedek_kullan else esik_ana
    with np.errstate(invalid="ignore"):
        gec = (x >= esik) if yon == ">=" else (x < esik)
    G = np.where(np.isfinite(x), gec, True)
    etiket = YEDEK if yedek_kullan else GECTI
    durum = np.where(np.isfinite(x), np.where(G, etiket, KALDI), KONTROL_YOK)
    return G, durum


def yedek_gerekir_mi(x, esik_ana, yon):
    """Belge 7.2 kural 1: ana eşikten (veriyle) geçen Dünya penceresi < 100 ise yedek eşik."""
    x = np.asarray(x, float)
    with np.errstate(invalid="ignore"):
        gec = (x >= esik_ana) if yon == ">=" else (x < esik_ana)
    n = int((np.isfinite(x) & gec).sum())
    return n < int(A.ayar("kapi.yedek_siniri_pencere")), n


def kapi_buz(buz, hedef_islak):
    """Belge 7.2: hedef ıslak değilse Ice 'not applicable'; ıslaksa ortalama permafrost ≥ 0,90 (yedek 0,50)."""
    buz = np.asarray(buz, float)
    if not hedef_islak:
        return np.zeros(buz.shape, bool), np.full(buz.shape, UYGULANMAZ, dtype=object), {"yedek": False, "ana_gecen": 0}
    ana, yed = float(A.ayar("kapi.buz.ana")), float(A.ayar("kapi.buz.yedek"))
    yedek, n = yedek_gerekir_mi(buz, ana, ">=")
    G, d = _esikli(buz, ana, yed, ">=", yedek)
    return G, d, {"yedek": yedek, "ana_gecen": n}


def kapi_astro(ai_ortanca):
    """Belge 7.2: ortanca AI < 0,03 (yedek < 0,20)."""
    ana, yed = float(A.ayar("kapi.astro.ana")), float(A.ayar("kapi.astro.yedek"))
    yedek, n = yedek_gerekir_mi(ai_ortanca, ana, "<")
    G, d = _esikli(ai_ortanca, ana, yed, "<", yedek)
    return G, d, {"yedek": yedek, "ana_gecen": n}


def kapi_jeoloji(pv_ortanca, karbuz_ortalama, q_baskin, X):
    """Belge 7.2: G_jeo = 1[ortanca Pv < 0,5] · 1[kar/buz < 0,5] · 1[q_{c*(T)}(E) ≥ X]. Bir koşulun verisi yoksa
    o koşul 1 sayılır ve aday 'could not be checked' işaretlenir (kural 2). Yedek yok."""
    pv, kb, q = (np.asarray(v, float) for v in (pv_ortanca, karbuz_ortalama, q_baskin))
    p_es, k_es = float(A.ayar("kapi.jeoloji.Pv_esigi")), float(A.ayar("kapi.jeoloji.kar_buz_siniri"))
    with np.errstate(invalid="ignore"):
        c1 = np.where(np.isfinite(pv), pv < p_es, True)
        c2 = np.where(np.isfinite(kb), kb < k_es, True)
        c3 = np.where(np.isfinite(q), q >= float(X), True)
    G = c1 & c2 & c3
    eksik = ~np.isfinite(pv) | ~np.isfinite(kb) | ~np.isfinite(q)
    durum = np.where(G, np.where(eksik, KONTROL_YOK, GECTI), KALDI)
    return G, durum


# ------------------------------------------------------------------ uygunluk
def uygun(K_aday, K_hedef):
    """Belge 7.2 + K-4: Uygun(E) = 1[{1,2} ⊆ K(E)] · 1[|K(E) ∩ K(T)| ≥ |K(T)| − 1].
    K_aday: (n, 8) bool (kategori verisi var); K_hedef: (8,) bool. Hedefte olmayan kategori sayılmaz."""
    Ka = np.asarray(K_aday, bool)
    Kt = np.asarray(K_hedef, bool)
    zorunlu = [k - 1 for k in A.ayar("uygunluk.zorunlu_kategoriler")]
    eksik_izin = int(A.ayar("uygunluk.en_fazla_eksik"))
    ortak = (Ka & Kt[None, :]).sum(axis=1)
    return Ka[:, zorunlu].all(axis=1) & (ortak >= Kt.sum() - eksik_izin)


# ------------------------------------------------------------------ X (leave-one-out)
def X_degerleri(paylar):
    """Belge 7.2 / v1.2 D7 + K-5. paylar: {çift_no: q_{c*(T_a)}(E_a)} (V1 Geology çiftleri).
    Dönüş: (X_tam = hepsinin en küçüğü, {çift_no: o çift hariç en küçük})."""
    ks = sorted(paylar)
    v = np.array([float(paylar[k]) for k in ks])
    assert len(v) >= 2 and np.isfinite(v).all(), paylar
    X_tam = float(v.min())
    loo = {k: float(np.delete(v, i).min()) for i, k in enumerate(ks)}
    return X_tam, loo


# ------------------------------------------------------------------ NDVI yıllık (Pv için)
def ndvi_yillik():
    """ASTER NDVI 12 ay → geçerli ayların ortalaması (K-2); ara\\cmg_ndvi.npy (CMG ızgarası)."""
    p = ARA / "cmg_ndvi.npy"
    if not p.exists():
        st = []
        for ad in K.aylik("E4", "ndvi"):
            k = K.ac(ad)
            assert (k.x0, k.dx, k.y0, k.dy) == (-180.0, 0.05, 90.0, 0.05), ad
            st.append(np.asarray(k.kaynak, np.float32))
        st = np.stack(st)
        with np.errstate(invalid="ignore"), __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore", RuntimeWarning)
            v = np.nanmean(st, axis=0).astype(np.float32)
        np.save(p, v)
        p.with_suffix(".json").write_text(json.dumps({
            "geotransform": [-180.0, 0.05, 0.0, 90.0, 0.0, -0.05], "sekil": [3600, 7200], "birim": "NDVI",
            "kural": "12 aylık ASTER GED NDVI, geçerli ayların ortalaması (K-2, Sude onayı)",
            "gecerli": int(np.isfinite(v).sum()), "en_kucuk": float(np.nanmin(v)), "en_buyuk": float(np.nanmax(v))},
            ensure_ascii=False, indent=1), encoding="utf-8")
    return K._npy_cografi("cmg_ndvi", p, 20)
