# Developed with assistance from Claude (Anthropic).
"""Belge 8.2: Horn eğimi, VRM, rölyef; 6.1 eğrilik, iki ölçek, IQR, d₁."""
import math
import numpy as np
import pytest
import ayar as A
import ozellik_topo as T

n = 56
x = (np.arange(n) - n / 2 + 0.5)[None, :] * 500.0   # m, doğu
y = (np.arange(n) - n / 2 + 0.5)[:, None] * 500.0   # m, kuzey


def test_horn_egimi_8_2():
    # 8.2: z = 0,1x düzlemi, piksel 1 m → arctan 0,1 = 5,7106°
    h = 0.1 * np.arange(10.0)[None, :].repeat(10, 0)
    hx, hy, *_ = T.turevler(h, 1.0)
    assert np.allclose(np.degrees(T.egim(hx, hy)), 5.7106, atol=5e-5)
    assert abs(math.degrees(math.atan(0.1)) - 5.7106) < 5e-5


def test_horn_yonu():
    # h_x doğuya, h_y kuzeye artış: z = 2y − 3x
    h = 2 * y - 3 * x
    hx, hy, hxx, hyy, hxy = T.turevler(h, 500.0)
    assert np.allclose(hx, -3) and np.allclose(hy, 2) and np.allclose(hxx, 0) and np.allclose(hxy, 0)


def test_vrm_sabit_egimli_duz_yuzey_8_2():
    # 8.2: sabit eğimli düz yüzey → VRM 0
    oz = T.ozellikler(0.3 * x + 0.1 * y + 100.0, "dunya")
    assert np.allclose(oz["vrm_1"], 0, atol=1e-12) and np.allclose(oz["vrm_4"], 0, atol=1e-12)
    assert oz["vrm_1"].shape == (40, 40) and oz["vrm_4"].shape == (10, 10)


def test_vrm_araligi():
    h = np.random.default_rng(0).normal(0, 300, (n, n))
    v = T.ozellikler(h, "dunya")["vrm_1"]
    assert (v >= 0).all() and (v <= 1).all() and v.max() > 0


def test_rolyef_sifir_8_2():
    # 8.2: R = 0 olan pencere → R = σv (cisim başına)
    for g in ("dunya", "ay", "mars"):
        oz = T.ozellikler(np.full((n, n), 123.0), g)
        assert oz["R"] == A.ayar("cisim.sigma_v_m")[g]


def test_rolyef_yalniz_pencere():
    h = np.zeros((n, n)); h[0, 0] = 1e4  # genişletme bölgesindeki uç değer rölyefe girmez
    h[20, 20] = 50.0
    assert T.ozellikler(h, "dunya")["R"] == 50.0


def test_ortalama_egrilik_canak():
    # z = (x² + y²)/(2a): merkezde H = 1/a > 0 (çukur)
    a = 1e5
    h = (x ** 2 + y ** 2) / (2 * a)
    hx, hy, hxx, hyy, hxy = T.turevler(h, 500.0)
    H = T.egrilik(hx, hy, hxx, hyy, hxy)
    j = i = n // 2 - 1 - 1  # turevler iç bölge: orijinal (27, 27) → (26, 26); merkeze en yakın
    xc, yc = x[0, 27], y[27, 0]
    p, q = xc / a, yc / a
    beklenen = ((1 + q * q) / a + (1 + p * p) / a) / (2 * (1 + p * p + q * q) ** 1.5)
    assert abs(H[26, 26] - beklenen) / beklenen < 1e-9 and H[26, 26] > 0
    assert (T.egrilik(*T.turevler(-h, 500.0)) < 0).all()


def test_blok4():
    h = np.arange(56 * 56, dtype=float).reshape(56, 56)
    b = T.blok4(h)
    assert b.shape == (14, 14) and b[0, 0] == h[:4, :4].mean() and b[13, 13] == h[52:, 52:].mean()


def test_iki_olcek_egim():
    # düzlemde iki ölçekte eğim aynı
    oz = T.ozellikler(0.2 * x + 0 * y, "dunya")
    assert np.allclose(oz["theta_1"], math.atan(0.2)) and np.allclose(oz["theta_4"], math.atan(0.2))


def test_coklu_pencere_vektor():
    g = np.random.default_rng(1)
    h = g.normal(0, 100, (3, n, n))
    oz = T.ozellikler(h, "ay")
    tek = T.ozellikler(h[1], "ay")
    assert oz["theta_1"].shape == (3, 40, 40) and np.allclose(oz["theta_1"][1], tek["theta_1"])
    assert oz["R"].shape == (3,) and oz["dem_tam"].all()
    Q = T.yuzdelik_vektorleri(oz)
    assert Q.shape == (3, 6, 1000)


def test_dem_eksik():
    h = np.zeros((n, n)); h[30, 30] = np.nan
    oz = T.ozellikler(h, "mars")
    assert not oz["dem_tam"] and np.isnan(oz["theta_1"]).any()


def test_ceyrek_ve_iqr():
    assert T.ceyrek([1, 2, 3, 4], 1, 4) == 1 and T.ceyrek([1, 2, 3, 4], 3, 4) == 3
    g = np.random.default_rng(2)
    ozl = [T.ozellikler(g.normal(0, 100, (n, n)), "dunya") for _ in range(21)]
    iqr = T.iqr_hedef(ozl)
    assert iqr.shape == (6,) and (iqr > 0).all()
    duz = [T.ozellikler(0.2 * x + 0 * y, "dunya") for _ in range(21)]
    iq2 = T.iqr_hedef(duz)
    assert iq2[0] == 0 and iq2[1] == 0  # sabit eğim → IQR 0 → F_T dışında


def test_d1():
    g = np.random.default_rng(3)
    ozl = [T.ozellikler(g.normal(0, 100, (n, n)), "dunya") for _ in range(4)]
    Q = np.stack([T.yuzdelik_vektorleri(o) for o in ozl])
    lnR = np.array([o["lnR"] for o in ozl])
    iqr = T.iqr_hedef(ozl)
    d = T.d1(Q, lnR, Q[0], lnR[0], iqr)
    assert d[0] == 0 and (d[1:] > 0).all()
    # yalnız ln R farkı: F_T boş → d₁ = |Δ ln R| / 1
    d0 = T.d1(Q[:2], np.array([0.0, 1.0]), Q[0], 0.0, np.zeros(6))
    assert d0[1] == 1.0
    # el ile: |F_T| = 6
    w = np.mean(np.abs(Q[1] - Q[0]), axis=-1)
    assert abs(d[1] - (np.sum(w / iqr) + abs(lnR[1] - lnR[0])) / 7) < 1e-12


def test_z_topo():
    oz = T.ozellikler(0.2 * x + 0 * y, "dunya")
    z = T.z_topo(oz)
    assert z.shape == (4,) and abs(z[0] - math.atan(0.2)) < 1e-12 and abs(z[1] - math.atan(0.2)) < 1e-12
    assert abs(z[2]) < 1e-12 and abs(z[3] - math.log(0.2 * 500 * 39)) < 1e-9


@pytest.mark.parametrize("govde,lat,lon,ad", [("ay", -89.0, 30.0, "lola"),            # belge 9.1 M-SP
                                              ("mars", 18.44, 77.45, "mola"),          # belge 9.2 R-JEZ
                                              ("dunya", 35.58223, -111.63182, "etopo")])  # belge 9.3 SP Crater
def test_gercek_pencere_ozellikleri(govde, lat, lon, ad):
    import izgara as Z
    import katman as K
    h, coarse, s = K.hucreye(K.ac(ad), [math.radians(lat)], [math.radians(lon)], Z.yaricap(govde), genisletme=T.GEN)
    oz = T.ozellikler(h[0], govde)
    assert oz["dem_tam"]
    for f in T.OZELLIKLER:
        assert np.isfinite(oz[f]).all(), f
    assert np.degrees(oz["theta_1"]).max() < 60 and oz["R"] > A.ayar("cisim.sigma_v_m")[govde]
    assert np.isfinite(T.yuzdelik_vektorleri(oz)).all() and np.isfinite(T.z_topo(oz)).all()
