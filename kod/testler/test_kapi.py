# Developed with assistance from Claude (Anthropic).
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
