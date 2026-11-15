# Developed with assistance from Claude (Anthropic).
"""Belge 7.1 ön eleme testleri (Q-1 dahil)."""
import itertools

import numpy as np
import pytest

import onele as O
import ozellik_topo as T
import ozellik_topoloji as TP

RNG = np.random.default_rng(20261113)


def _Z(n, rng=RNG):
    Z = rng.normal(size=(n, 6)) * [3, 5, 0.01, 1, 4, 4] + [10, 20, 0.02, 5, 8, 8]
    Z[:, 4:] = np.round(np.abs(Z[:, 4:]))
    return Z


def _kaba(Z, G, zt, ol, K):
    Zs = ol.standart(Z)
    ok = G & np.isfinite(Zs).all(axis=1)
    idx = np.flatnonzero(ok)
    d = np.sqrt(((Zs[idx] - ol.standart(zt)) ** 2).sum(axis=1))
    o = np.lexsort((idx, d))[:K]
    return idx[o], d[o]


def test_z_vektoru_bilesenleri():
    x = np.arange(56) * 500.0
    h = 300 * np.sin(x[None, :] / 4000) * np.cos(x[:, None] / 3000) + 50 * np.random.default_rng(1).normal(size=(56, 56))
    oz = T.ozellikler(h, "dunya")
    W = h[T.GEN:-T.GEN, T.GEN:-T.GEN]
    dg = TP.diyagramlar(W, "dunya", yontem="union_find")
    z = O.z_vektoru(oz, dg, "dunya")
    assert z.shape == (6,)
    th = oz["theta_1"].ravel()
    assert z[0] == pytest.approx(np.mean(th))
    assert z[1] == pytest.approx(T.ceyrek(th, 9, 10))
    assert z[2] == pytest.approx(np.mean(oz["vrm_1"]))
    assert z[3] == pytest.approx(float(oz["lnR"]))
    assert tuple(z[4:]) == TP.n_onemli(dg, "dunya")


def test_z_vektoru_dem_eksik_nan():
    oz = T.ozellikler(np.ones((56, 56)), "dunya")
    z = O.z_vektoru(oz, None, "dunya")
    assert np.isnan(z[4:]).all() and np.isfinite(z[:4]).all()


def test_medyan_mad_elle():
    Z = np.array([[1, 2, 3, 4, 5, 6], [2, 4, 6, 8, 10, 12], [4, 8, 12, 16, 20, 24],
                  [np.nan, 0, 0, 0, 0, 0]], float)
    ol = O.Olcek(Z)
    assert ol.n_eksik == 1
    np.testing.assert_allclose(ol.medyan, [2, 4, 6, 8, 10, 12])
    np.testing.assert_allclose(ol.mad, [1, 2, 3, 4, 5, 6])
    np.testing.assert_allclose(ol.standart(np.array([4, 4, 6, 8, 10, 0.0])),
                               [2 / 1.4826, 0, 0, 0, 0, -12 / (6 * 1.4826)])


def test_mad_sifir_bilesen_cikar_Q1():
    Z = _Z(101)
    Z[:, 4] = 3.0
    Z[:60, 5] = 7.0   # yarıdan fazlası aynı → MAD = 0
    ol = O.Olcek(Z)
    assert ol.dusen == ["n_asagi", "n_yukari"]
    assert ol.standart(Z).shape == (101, 4)
    assert ol.kayit()["MAD_sifir_cikan_bilesenler"] == ["n_asagi", "n_yukari"]


@pytest.mark.parametrize("K", [1, 5, 37, 200])
def test_kd_kaba_kuvvetle_ayni(K):
    rng = np.random.default_rng(K)
    Z = _Z(3000, rng)
    Z[rng.choice(3000, 50, replace=False), 4] = np.nan
    G = rng.random(3000) < 0.6
    ol = O.Olcek(Z)
    ag = O.Agac(ol, Z, G)
    for _ in range(5):
        zt = _Z(1, rng)[0]
        s, kim, d = ag.sorgu(zt, K)
        s0, d0 = _kaba(Z, G, zt, ol, K)
        np.testing.assert_array_equal(s, s0)
        np.testing.assert_allclose(d, d0, rtol=1e-12)
        assert G[s].all() and np.all(np.diff(d) >= 0)


def test_esitlikte_kucuk_kimlik_once():
    base = _Z(400)
    Z = np.vstack([base, np.repeat(base[:1], 9, axis=0)])   # 10 aynı nokta
    kim = np.arange(len(Z))[::-1].copy()                    # kimlik sırası satır sırasının tersi
    ol = O.Olcek(Z)
    ag = O.Agac(ol, Z, kimlik=kim)
    s, k, d = ag.sorgu(base[0], 4)
    assert np.all(d == 0)
    hepsi = np.r_[0, np.arange(400, 409)]
    np.testing.assert_array_equal(k, np.sort(kim[hepsi])[:4])
    s2, k2, _ = ag.sorgu(base[0], 4)
    np.testing.assert_array_equal(k, k2)


def test_kimlik_D7_kendi_penceresi_ilk():
    Z = _Z(2000)
    ol = O.Olcek(Z)
    ag = O.Agac(ol, Z)
    for i in (0, 17, 1999):
        s, _, d = ag.sorgu(Z[i], 10)
        assert s[0] == i and d[0] == 0


def test_aday_sayisi_K_den_az():
    Z = _Z(500)
    G = np.zeros(500, bool); G[[3, 9, 44]] = True
    ag = O.Agac(O.Olcek(Z), Z, G)
    s, _, _ = ag.sorgu(Z[0], 100)
    assert sorted(s) == [3, 9, 44]
    bos = O.Agac(O.Olcek(Z), Z, np.zeros(500, bool))
    assert len(bos.sorgu(Z[0], 10)[0]) == 0


def test_kapi_ve_eksik_sayilari():
    Z = _Z(1000)
    Z[:10, 5] = np.nan
    G = np.ones(1000, bool); G[5:20] = False
    ag = O.Agac(O.Olcek(Z), Z, G)
    assert ag.kayit() == {"kapidan_gecen": 985, "kapidan_gecen_z_eksik": 5, "agac_boyu": 980}


def test_hedef_nan():
    Z = _Z(300)
    Z[:, 4] = 1.0
    ag = O.Agac(O.Olcek(Z), Z)
    zt = Z[0].copy(); zt[4] = np.nan          # çıkan bileşen: sorun yok
    assert len(ag.sorgu(zt, 5)[0]) == 5
    zt[5] = np.nan                            # tutulan bileşen: hata
    with pytest.raises(ValueError):
        ag.sorgu(zt, 5)


def test_olcek_ve_kaydirma_degismez():
    rng = np.random.default_rng(7)
    Z = _Z(2000, rng); zt = _Z(1, rng)[0]
    a = rng.uniform(0.1, 50, 6); b = rng.normal(0, 100, 6)
    s1 = O.Agac(O.Olcek(Z), Z).sorgu(zt, 50)[0]
    s2 = O.Agac(O.Olcek(Z * a + b), Z * a + b).sorgu(zt * a + b, 50)[0]
    np.testing.assert_array_equal(s1, s2)


def test_kon_sec_Q9_Q10():
    assert O.kon_sec({100: 0.85, 200: 0.91, 400: 0.95, 800: 0.97}) == (200, True)
    assert O.kon_sec({100: 0.9, 200: 0.95, 400: 0.95, 800: 0.97}) == (100, True)
    assert O.kon_sec({100: 0.5, 200: 0.6, 400: 0.7, 800: 0.89}) == (800, False)
    with pytest.raises(AssertionError):
        O.kon_sec({100: 0.9})


def test_recall_ozet():
    r = np.array([1, 2 / 3, 1, 1 / 3, 1.0])
    m, a, u = O.recall_ozet(r)
    y = 1.96 * np.std(r, ddof=1) / np.sqrt(5)
    assert m == pytest.approx(np.mean(r)) and a == pytest.approx(m - y) and u == pytest.approx(m + y)
    assert O.recall_ozet(np.ones(200)) == (1.0, 1.0, 1.0)
