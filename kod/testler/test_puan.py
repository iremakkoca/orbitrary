# Developed with assistance from Claude (Anthropic).
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
