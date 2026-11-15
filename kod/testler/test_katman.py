# Developed with assistance from Claude (Anthropic).
"""Belge 4.4 hücreye aktarma ve okuyucu çekirdeği: sentetik girdilerle (cevabı bilinen)."""
import math
import numpy as np
import pytest
import ayar as A
import izgara as Z
import katman as K

R_D = 6371.0


def test_cografi_yonelim_ve_sarma():
    a = (np.arange(180)[:, None] * 1000 + np.arange(360)[None, :]).astype(np.float32)
    k = K.Cografi("t", a, -180.0, 1.0, 90.0, 1.0, 180, 360, "")
    v = k.ornekle(np.array([89.5, -89.5, 0.5, 0.5, -90.0, 90.0]), np.array([-179.5, 179.5, 180.0, -180.0, 0.0, 0.0]))
    assert v.tolist() == [0.0, 179359.0, 89000.0, 89000.0, 179180.0, 180.0]


def test_cografi_kapsam_disi_nan():
    a = np.ones((10, 20), np.float32)
    k = K.Cografi("t", a, 0.0, 1.0, 70.0, 1.0, 10, 20, "")   # 60–70°K, 0–20°D, küresel değil
    v = k.ornekle(np.array([65.0, 75.0, 65.0, 59.9]), np.array([5.0, 5.0, 25.0, 5.0]))
    assert v[0] == 1 and np.isnan(v[1:]).all()


def test_alt_noktalar_s1_pencere_ile_ayni():
    phi0, lam0 = math.radians(45.0), math.radians(179.9)
    lat, lon = K._alt_noktalar([phi0], [lam0], R_D, 0, 1)
    p, l = Z.pencere(phi0, lam0, R_D)
    lp = np.degrees(l); lp = np.where(lp >= 180, lp - 360, lp)
    assert np.allclose(lat[0, :, :, 0, 0], np.degrees(p)) and np.allclose(lon[0, :, :, 0, 0], lp)


def test_alt_noktalar_hucre_icinde():
    phi0, lam0 = 0.0, 0.0
    s = 4
    lat, lon = K._alt_noktalar([phi0], [lam0], R_D, 0, s)
    x, y = Z.lambert_ileri(np.radians(lat[0]), np.radians(lon[0]), phi0, lam0, R_D)
    c = Z.hucre_merkezleri()
    # her alt nokta kendi hücresinin içinde (|x − x_i| < δ/2), alt noktaların ortalaması hücre merkezi
    assert np.all(np.abs(x - c[None, :, None, None]) < 0.25) and np.all(np.abs(y - c[:, None, None, None]) < 0.25)
    assert np.allclose(x.mean(axis=(2, 3)), c[None, :], atol=1e-9) and np.allclose(y.mean(axis=(2, 3)), c[:, None], atol=1e-9)


def _ince_katman(deger_fn, dx=0.001):
    n = int(round(2.0 / dx))
    lat_c = 1.0 - (np.arange(n) + 0.5) * dx
    lon_c = -1.0 + (np.arange(n) + 0.5) * dx
    return K.Cografi("ince", deger_fn(lat_c[:, None], lon_c[None, :]).astype(np.float32), -1.0, dx, 1.0, dx, n, n, "")


def test_ince_katman_ortalama():
    # 0,001° ≈ 111 m < 500 m → ortalama (coarse değil). Otomatik s, çok sık örneğe (s = 40: alan ağırlıklı
    # piksel ortalaması) piksel adımının (burada 1,0) en fazla 0,15'i kadar yakın olmalı.
    k = _ince_katman(lambda la, lo: 1000.0 * np.floor(lo / 0.001) * 0.001 + 0.0 * la)
    v, coarse, s = K.hucreye(k, [0.0], [0.0], R_D)
    assert not coarse[0] and s[0] == math.ceil(2 * 0.5 / (0.001 * math.pi * R_D / 180))
    ref, _, _ = K.hucreye(k, [0.0], [0.0], R_D, s=40)
    assert np.max(np.abs(v[0] - ref[0])) < 0.15, float(np.max(np.abs(v[0] - ref[0])))
    # doğrusal alanın alan ağırlıklı ortalaması hücre merkezindeki değere (piksel yarım adım kaymasıyla) eşit
    lat, lon = K._alt_noktalar([0.0], [0.0], R_D, 0, 1)
    # s = 40 → piksel başına ~9 örnek; kalan kuantalama ≤ adım/(2·9) ≈ 0,056
    assert np.max(np.abs(ref[0] - (1000.0 * lon[0, :, :, 0, 0] - 0.5))) < 0.06


def test_ince_katman_alan_agirligi():
    # sütun paritesi 0/1 (dama sütunları): hücre ortalaması ≈ 0,5
    k = _ince_katman(lambda la, lo: (np.floor((lo + 1.0) / 0.001) % 2) + 0.0 * la)
    v, coarse, s = K.hucreye(k, [0.0], [0.0], R_D, s=8)
    assert abs(float(np.mean(v)) - 0.5) < 0.02


def test_kaba_katman_coarse():
    a = (np.arange(3600)[:, None] * 10000 + np.arange(7200)[None, :]).astype(np.float64)
    k = K.Cografi("kaba", a, -180.0, 0.05, 90.0, 0.05, 3600, 7200, "")
    v, coarse, s = K.hucreye(k, [math.radians(30.0)], [math.radians(10.0)], R_D)
    assert coarse[0] and s[0] == 1
    lat, lon = K._alt_noktalar([math.radians(30.0)], [math.radians(10.0)], R_D, 0, 1)
    beklenen = np.floor((90 - lat[0, :, :, 0, 0]) / 0.05) * 10000 + np.floor((lon[0, :, :, 0, 0] + 180) / 0.05)
    assert np.array_equal(v[0].astype(np.float64), beklenen.astype(np.float32).astype(np.float64))


def test_hucreye_nan_kurali():
    k = _ince_katman(lambda la, lo: np.where(lo < 0, np.nan, 1.0) + 0.0 * la)
    v, _, _ = K.hucreye(k, [0.0], [0.0], R_D)
    lat, lon = K._alt_noktalar([0.0], [0.0], R_D, 0, 1)
    sol = lon[0, :, :, 0, 0] < -0.003
    sag = lon[0, :, :, 0, 0] > 0.003
    assert np.isnan(v[0][sol]).all() and (v[0][sag] == 1).all()


def test_hucreye_alt_ornekler():
    k = _ince_katman(lambda la, lo: 1.0 + 0.0 * la + 0.0 * lo)
    v, _, s = K.hucreye(k, [0.0], [0.0], R_D, alt=True)
    assert v.shape == (1, 40, 40, int(s[0]) ** 2) and (v == 1).all()


def test_genisletme():
    k = _ince_katman(lambda la, lo: 1.0 + 0.0 * la + 0.0 * lo)
    v, _, _ = K.hucreye(k, [0.0], [0.0], R_D, genisletme=2)
    assert v.shape == (1, 44, 44)


def test_hidrojen_izgara():
    lat_k = 90.0 - 0.5 * np.repeat(np.arange(360), 720)
    lon_b = np.tile(np.arange(720) * 0.5, 360)  # 0–360 doğu
    h = np.arange(259200, dtype=float)
    t = np.stack([lat_k - 0.5, lat_k, lon_b, np.mod(lon_b + 0.5, 360.0), h], 1)
    d = K.hidrojen_izgara(t)
    k = K.Cografi("h", d, -180.0, 0.5, 90.0, 0.5, 360, 720, "")
    # 0–0,5°D hücresi (tablo sırası 0) → enlem 89,75, boylam 0,25
    assert k.ornekle(np.array([89.75]), np.array([0.25]))[0] == 0
    assert k.ornekle(np.array([89.75]), np.array([-0.25]))[0] == 719  # 359,5–360
    with pytest.raises(AssertionError):
        K.hidrojen_izgara(np.concatenate([t, t[:1]]))


def _gcp_bant(lat_lo, lat_hi, fn):
    clat = np.arange(lat_lo + 0.25, lat_hi, 0.5)
    clon = np.arange(0.25, 360, 0.5)
    ltim = (np.arange(96) + 0.5) * 0.25
    L, O, T = np.meshgrid(clat, clon, ltim, indexing="ij")
    return L.ravel(), O.ravel(), T.ravel(), fn(L.ravel(), T.ravel())


def test_gcp_gece_ortalamasi():
    fn = lambda la, t: 100.0 + la * 0 + np.where((t >= 18) | (t < 6), 0.0, 50.0) + 0.001 * t
    bantlar = [_gcp_bant(70, 80, fn), _gcp_bant(80, 90, fn)]
    d, y0 = K.gcp_gece_izgara(bantlar, "n")
    ltim = (np.arange(96) + 0.5) * 0.25
    gece = (ltim >= 18) | (ltim < 6)
    assert y0 == 90.0 and d.shape == (40, 720)
    assert np.allclose(d, 100.0 + 0.001 * ltim[gece].mean())


def test_esalan():
    satirlar = []
    for lo in range(-90, 90, 2):
        m = max(1, int(round(180 * math.cos(math.radians(lo + 1)))))
        w = 360.0 / m
        for k in range(m):
            satirlar.append((lo, lo + 2, k * w, (k + 1) * w, lo * 1000 + k))
    t = np.array(satirlar, float)
    e = K.EsAlan("t", t[:, 0], t[:, 1], t[:, 2], t[:, 3], t[:, 4], "")
    assert e.ornekle(np.array([0.5]), np.array([0.1]))[0] == 0
    assert e.ornekle(np.array([-89.0]), np.array([-1.0]))[0] == -90000 + (len([r for r in satirlar if r[0] == -90]) - 1)


def test_ucgen_esik():
    g = np.random.default_rng(0)
    lat = np.linspace(80, 90, 200).repeat(200); lon = np.tile(np.linspace(-180, 180, 200, endpoint=False), 200)
    u = K.Ucgen("t", lat, lon, np.arange(lat.size), 1737.4, "")
    v = u.ornekle(np.array([lat[500], 0.0]), np.array([lon[500], 0.0]))
    assert v[0] == 500 and np.isnan(v[1])


def test_pgda_xy():
    R = 1737400.0
    x, y = K.pgda_xy(np.array([90.0, 89.0, -89.0, -89.0]), np.array([0.0, 0.0, 90.0, 0.0]), "n", R)
    rho1 = 2 * R * math.tan(math.radians(1.0) / 2)
    assert abs(x[0]) < 1e-6 and abs(y[0]) < 1e-6 and abs(x[1]) < 1e-6 and abs(y[1] - rho1) < 1e-6
    assert np.isnan(x[2:]).all()
    xs, ys = K.pgda_xy(np.array([-89.0]), np.array([90.0]), "s", R)
    assert abs(xs[0] - rho1) < 1e-6 and abs(ys[0]) < 1e-6


def test_seyrek_noktalar_dogrudan_indeks(monkeypatch):
    a = (np.arange(1000)[:, None] * 10000 + np.arange(2000)[None, :]).astype(np.float32)
    k = K.Cografi("t", a, -180.0, 0.18, 90.0, 0.18, 1000, 2000, "")
    monkeypatch.setattr(K, "BLOK_SINIRI_BAYT", 1000)  # blok sınırını zorla aş
    lat = np.array([89.95, -89.95, 0.05]); lon = np.array([-179.95, 179.95, 0.05])
    v = k.ornekle(lat, lon)
    r = np.floor((90 - lat) / 0.18); c = np.floor((lon + 180) / 0.18)
    assert np.array_equal(v, (r * 10000 + c).astype(np.float32))


def test_toplam_onbellek_siniri(monkeypatch):
    monkeypatch.setattr(K, "_BLOK_SIRASI", [])
    kat = [K.Cografi(f"t{i}", np.full((180, 360), i, np.float32), -180.0, 1.0, 90.0, 1.0, 180, 360, "") for i in range(5)]
    blok = 33 * 360 * 4                                                 # 1 satır + 16 satır dolgu her yanda
    monkeypatch.setattr(K, "TOPLAM_ONBELLEK_BAYT", 3 * blok + 100)    # üç blok sığar
    for k in kat:
        assert k.ornekle(np.array([0.5]), np.array([0.5]))[0] == float(k.ad[1:])
    dolu = [k for k in kat if k._blok.veri is not None]
    assert len(dolu) == 3 and dolu == kat[2:]                          # en eski ikisi boşaltıldı
    assert kat[0].ornekle(np.array([0.5]), np.array([0.5]))[0] == 0.0   # boşaltılan yeniden okunur


def test_ucgen_kapsamdan_uzak_sorgu_hizli():
    # Kapsamdan uzak noktalar (ör. Apollo 15 için PRP) eşik sınırlı aramayla hızlı elenir; sonuç NaN
    import time
    g = np.random.default_rng(1)
    n = 400000
    z = g.uniform(np.sin(np.radians(76)), 1, n)
    lat = np.concatenate([np.degrees(np.arcsin(z)), -np.degrees(np.arcsin(z))])
    lon = np.concatenate([g.uniform(-180, 180, n)] * 2)
    u = K.Ucgen("t", lat, lon, np.arange(lat.size, dtype=float), 1737.4, "")
    qlat = 26.0 + g.uniform(-0.2, 0.2, 130000); qlon = 3.6 + g.uniform(-0.2, 0.2, 130000)
    t0 = time.time()
    v = u.ornekle(qlat, qlon)
    assert np.isnan(v).all() and time.time() - t0 < 5.0
    # kapsam kenarına yakın (76° berisinde, eşik içinde) nokta yine bulunur
    v2 = u.ornekle(np.array([lat[0]]), np.array([lon[0]]))
    assert v2[0] == 0
