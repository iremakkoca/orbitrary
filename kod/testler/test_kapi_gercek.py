# Developed with assistance from Claude (Anthropic).
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
