# Developed with assistance from Claude (Anthropic).
# 17.4 sıra 8: kod\\kapi.py + testler (belge 7.1–7.2; 8.2 kapı testleri, 8.3 kara maskesi; K-1…K-5 Sude onaylı).
# Ayrıca: MAKALEYİ ETKİLER kaydı güncel hali (onaylar + 19–25).
import sys, importlib
from pathlib import Path
KOK = Path.home() / "orbitrary"; KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / 'kapi.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
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
''', encoding='utf-8')
(KOD / 'testler/test_kapi.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 8.2 kapı testleri + 8.3 kara maskesi; uygunluk (K-4); X leave-one-out (K-5)."""
import numpy as np
import pytest
import kapi as G


def test_kara_maskesi_8_3():
    # MCD12C1 su %100 / %5 → kara 0 / 0,95
    assert G.kara_payi(100.0) == 0.0 and abs(G.kara_payi(5.0) - 0.95) < 1e-15
    k = np.full((40, 40), 0.95)
    assert G.maskeden_gecer(k) and not G.maskeden_gecer(np.full((40, 40), 0.89))


def test_hareket_kapisi_8_2():
    # 1600 hücreden 81'i ≥ 20° → G = 0 (1519/1600 = 0,9494)
    th = np.full((40, 40), np.radians(10.0)); th.ravel()[:81] = np.radians(25.0)
    kara = np.ones((40, 40))
    d = G.degiskenler(kara, egim_rad=th)
    assert abs(d["mob"] - 1519 / 1600) < 1e-15
    Gm, durum = G.kapi_mobility(d["mob"])
    assert not Gm and durum == G.KALDI
    th.ravel()[80] = np.radians(10.0)  # 80 hücre → 0,95 → G = 1
    assert G.kapi_mobility(G.degiskenler(kara, egim_rad=th)["mob"])[0]


def test_buz_kapisi_8_2():
    kara = np.ones((40, 40))
    x = np.full((500, ), 0.95)  # yedek gerekmesin diye ≥ 100 pencere ana eşikten geçsin
    for ort, beklenen in ((0.90, True), (0.89, False)):
        d = G.degiskenler(kara, perm=np.full((40, 40), ort))["buz"]
        Gb, durum, bilgi = G.kapi_buz(np.concatenate([[d], x]), hedef_islak=True)
        assert bool(Gb[0]) == beklenen and not bilgi["yedek"]


def test_kapi_yedegi_8_2():
    # ana eşikten 99 / 100 pencere geçiyor → yedek eşik / ana eşik
    for n_gecen, yedek in ((99, True), (100, False)):
        buz = np.concatenate([np.full(n_gecen, 0.95), np.full(500, 0.6)])
        Gb, durum, bilgi = G.kapi_buz(buz, hedef_islak=True)
        assert bilgi["yedek"] == yedek and bilgi["ana_gecen"] == n_gecen
        if yedek:
            assert Gb[-1] and durum[-1] == G.YEDEK      # 0,6 ≥ 0,50 yedekle geçer, kırmızı etiket
        else:
            assert not Gb[-1] and durum[0] == G.GECTI


def test_astrobiyoloji_kapisi_8_2():
    # AI ortancası veride 299 / 300 (AI = ham/10 000 → 0,0299 / 0,0300) → G = 1 / 0
    kara = np.ones((40, 40))
    ai = np.concatenate([[G.degiskenler(kara, ai=np.full((40, 40), 299 / 10000))["astro"],
                          G.degiskenler(kara, ai=np.full((40, 40), 300 / 10000))["astro"]], np.full(200, 0.01)])
    Ga, durum, bilgi = G.kapi_astro(ai)
    assert Ga[0] and not Ga[1] and not bilgi["yedek"]


def test_bitki_ortusu_8_2():
    # NDVI 0,2 / 0,41 / 0,42 / 0,6 → Pv = 0 / 0,49 / 0,54 / 1
    p = G.Pv(np.array([0.2, 0.41, 0.42, 0.6]))
    assert p[0] == 0 and abs(p[1] - 0.49) < 1e-12 and round(p[2], 2) == 0.54 and p[3] == 1.0


def test_eksik_kapi_verisi_8_2():
    # permafrost verisi yok → G = 1, "could not be checked"
    kara = np.ones((40, 40))
    d = G.degiskenler(kara, perm=np.full((40, 40), np.nan))["buz"]
    Gb, durum, _ = G.kapi_buz(np.concatenate([[d], np.full(200, 0.95)]), hedef_islak=True)
    assert Gb[0] and durum[0] == G.KONTROL_YOK
    Gm, dm = G.kapi_mobility(np.nan)
    assert Gm and dm == G.KONTROL_YOK


def test_kuru_hedefte_ice_uygulanmaz():
    Gb, durum, _ = G.kapi_buz(np.array([0.99, 0.2]), hedef_islak=False)
    assert not Gb.any() and (durum == G.UYGULANMAZ).all()


def test_w_kare_kara_esigi_K1():
    # kara payı < 0,5 hücreler W° dışında
    kara = np.ones((40, 40)); kara[:, :20] = 0.4
    x = np.ones((40, 40)); x[:, :20] = 0.0
    assert G.w_ortalama(x, kara) == 1.0 and G.degiskenler(kara, kar_buz=x)["karbuz"] == 1.0


def test_jeoloji_kapisi():
    Gj, d = G.kapi_jeoloji(np.array([0.3, 0.6, 0.3, np.nan]), np.array([0.1, 0.1, 0.1, 0.1]),
                           np.array([0.5, 0.5, 0.1, 0.5]), X=0.2)
    assert Gj.tolist() == [True, False, False, True] and d[3] == G.KONTROL_YOK and d[0] == G.GECTI
    Gj2, _ = G.kapi_jeoloji(np.array([0.3]), np.array([0.6]), np.array([0.5]), X=0.2)
    assert not Gj2[0]  # kar/buz ≥ 0,5


def test_pv_ortanca_K2():
    kara = np.ones((40, 40))
    pv = np.zeros((40, 40)); pv.ravel()[:801] = 1.0  # çoğunluk 1 → ortanca 1
    assert G.degiskenler(kara, pv=pv)["pv"] == 1.0


def test_uygunluk_K4():
    Kt = np.array([1, 1, 1, 1, 1, 0, 1, 1], bool)        # hedef kuru: su/buz yok
    Ka = np.array([[1, 1, 1, 1, 1, 0, 1, 1],              # tam
                   [1, 1, 1, 1, 0, 0, 1, 1],              # 1 eksik (termal)
                   [1, 1, 0, 1, 0, 0, 1, 1],              # 2 eksik
                   [1, 0, 1, 1, 1, 1, 1, 1],              # topoloji yok
                   [1, 1, 1, 1, 1, 1, 1, 1]], bool)       # su/buz fazla, sayılmaz
    assert G.uygun(Ka, Kt).tolist() == [True, True, False, False, True]


def test_X_leave_one_out_K5():
    X, loo = G.X_degerleri({1: 0.4, 2: 0.2, 3: 0.6, 4: 0.6, 8: 0.5, 9: 0.3, 10: 0.7})
    assert X == 0.2 and loo[2] == 0.3 and loo[1] == 0.2 and len(loo) == 7
''', encoding='utf-8')
(KOD / 'testler/test_kapi_gercek.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
"""kapi.py gerçek veriyle: NDVI yıllık, SP Crater (V1 çift 5) penceresinin kapı değişkenleri; E5 = Aqua (MYD11C3)."""
import json
import math
import numpy as np
import ayar as A
import izgara as Z
import katman as K
import kapi as G
import ozellik_diger as O
import ozellik_topo as T


def test_e5_aqua_myd11c3():
    # Madde 5/19: termal veri Aqua (MYD11C3), Terra (MOD11C3) değil — temiz\ yan dosyalarından
    for ad in K.aylik("E5", "lst_gunduz") + K.aylik("E5", "lst_gece"):
        j = json.loads((K._kl("dunya", "E5") / f"{ad}.json").read_text(encoding="utf-8"))
        assert "MYD11C3" in j["kaynak"] and "MOD11C3" not in j["kaynak"], j["kaynak"]


def test_ndvi_yillik():
    k = G.ndvi_yillik()
    v = np.asarray(k.kaynak)
    assert np.nanmin(v) >= -1 and np.nanmax(v) <= 1 and np.isfinite(v).sum() > 1_000_000


def test_sp_crater_kapi_degiskenleri():
    lat, lon, r = 35.58223, -111.63182, Z.yaricap("dunya")   # belge 9.3 SP Crater
    phi0, lam0 = [math.radians(lat)], [math.radians(lon)]
    kara = G.kara_payi(K.hucreye(K.ac("mcd12c1_00"), phi0, lam0, r)[0])
    assert G.maskeden_gecer(kara)[0]
    h, _, _ = K.hucreye(K.ac("etopo"), phi0, lam0, r, genisletme=T.GEN)
    th = T.ozellikler(h, "dunya")["theta_1"]
    perm = K.hucreye(O.ac("perm_sifir"), phi0, lam0, r)[0]
    ai = K.hucreye(K.ac("ai"), phi0, lam0, r)[0]
    pv = G.Pv(K.hucreye(G.ndvi_yillik(), phi0, lam0, r)[0])
    kb = K.hucreye(K.ac("mcd12c1_15"), phi0, lam0, r)[0] / 100.0
    d = G.degiskenler(kara, egim_rad=th, perm=perm, ai=ai, pv=pv, kar_buz=kb)
    assert 0 <= d["mob"][0] <= 1 and d["buz"][0] == 0.0          # Arizona: sıfır kuralı → permafrost 0
    assert 0 < d["astro"][0] < 1 and 0 <= d["pv"][0] <= 1 and d["karbuz"][0] == 0.0
''', encoding='utf-8')
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
''', encoding="utf-8")

yol = KOD / "FONKSIYONLAR.md"; metin = yol.read_text(encoding="utf-8")
bas, son = "<!-- kapi.py -->", "<!-- /kapi.py -->"
blok = bas + "\n## kapi.py\n" + "\n".join("- " + s for s in [
    "7.1 kara_ij, E′ → `kapi.kara_payi`, `kapi.maskeden_gecer`",
    "7.2 P_v → `kapi.Pv`; W° değişkenleri → `kapi.degiskenler`",
    "7.2 G_mob, G_buz, G_astro, G_jeo → `kapi.kapi_mobility`, `kapi.kapi_buz`, `kapi.kapi_astro`, `kapi.kapi_jeoloji`",
    "7.2 kapı yedeği (< 100 pencere) → `kapi.yedek_gerekir_mi`",
    "7.2 Uygun(E) → `kapi.uygun`; X ve leave-one-out → `kapi.X_degerleri`"]) + "\n" + son
metin = (metin.split(bas)[0] + blok + metin.split(son)[1]) if bas in metin else (metin.rstrip() + "\n\n" + blok + "\n")
yol.write_text(metin, encoding="utf-8")
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | Sude onayları (12:17): madde 4, 5, 7, 8, 9, 10, PRP 3× eşiği; K-1…K-5 (kapı okumaları) | madde 5 'Terra' düzeltmesi uygulanmadı: veri MYD11C3 = Aqua (test_e5_aqua_myd11c3) | Pv pencerede ortanca (belge 7.2 açık) | Ice kapısında kar/buz şartı yok → buz tabakası içi 'could not be checked' (kayıt) | etkisi: MAKALEYİ ETKİLER 19–25\n")

if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_kapi", ["testler/test_kapi.py", "testler/test_kapi_gercek.py"])
