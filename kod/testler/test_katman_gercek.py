# Developed with assistance from Claude (Anthropic).
"""katman.py gerçek temiz\\ verisiyle: açılış, bağımsız okuma (rasterio) ile aynılık, belge 8.3 veri testleri,
gerçek-yer kontrolleri (koordinatlar belgeden), vektör sınıfları."""
import math
import numpy as np
import pytest
import ayar as A
import izgara as Z
import katman as K

RASTER = ["etopo", "mcd12c1_00", "mcd12c1_15", "perm_kuzey", "perm_antarktika", "ai", "ai_bayrak", "kil", "silt",
          "lola", "ra", "tbol", "avgvisib_n", "avgvisib_s", "lpsr_n", "lpsr_s", "gcp_gece_n", "gcp_gece_s",
          "prp_temp_max", "prp_temp_avg", "prp_ice_depth_m", "prp_ice_depth_bayrak", "lpgrs_w_feo", "lpgrs_w_th",
          "hidrojen", "mola", "tes_plagioclase", "tes_low_ca_pyroxene", "tes_high_ca_pyroxene", "ti", "albedo_mars",
          "dci", "swim"]


@pytest.mark.parametrize("ad", RASTER)
def test_katman_acilir(ad):
    assert K.ac(ad) is not None


@pytest.mark.parametrize("kod,onek", [("E4", "yayinim_b10"), ("E4", "yayinim_b12"), ("E4", "yayinim_b13"),
                                      ("E4", "yayinim_b14"), ("E4", "ndvi"), ("E4", "ndvi_bayrak"),
                                      ("E5", "lst_gunduz"), ("E5", "lst_gece"), ("E6", "albedo_wsa")])
def test_aylik_katmanlar(kod, onek):
    for ad in K.aylik(kod, onek):
        assert K.ac(ad).tur == "cografi"


def _rastgele(g, n, lat0, lat1, lon0=-180.0, lon1=180.0):
    z = g.uniform(math.sin(math.radians(lat0)), math.sin(math.radians(lat1)), n)
    return np.degrees(np.arcsin(z)), g.uniform(lon0, lon1, n)


def _ayni(a, b):
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    assert np.array_equal(np.isnan(a), np.isnan(b)), f"NaN deseni farklı: {np.isnan(a).sum()} / {np.isnan(b).sum()}"
    assert np.array_equal(a[~np.isnan(a)], b[~np.isnan(b)])


@pytest.mark.parametrize("ad,lat0,lat1", [("etopo", -90, 90), ("ai", -60, 90), ("ra", -70, 70), ("tbol", -70, 70)])
def test_cografi_tif_rasterio_ile_ayni(ad, lat0, lat1):
    k = K.ac(ad)
    lat, lon = _rastgele(np.random.default_rng(5), 3000, lat0 + 1e-6, lat1 - 1e-6)
    biz = k.ornekle(lat, lon)
    onlar = np.array([v[0] for v in k.kaynak.sample(zip(lon, lat))])
    _ayni(biz, onlar)


@pytest.mark.parametrize("ad,lat0,lat1", [("perm_kuzey", 25, 90), ("perm_antarktika", -90, -55),
                                          ("kil", -56, 84), ("silt", -56, 84)])
def test_projeksiyon_rasterio_ile_ayni(ad, lat0, lat1):
    from pyproj import Transformer
    k = K.ac(ad)
    ds = k.kaynak
    lat, lon = _rastgele(np.random.default_rng(6), 4000, lat0, lat1)
    x, y = Transformer.from_crs("EPSG:4326", ds.crs.to_wkt(), always_xy=True).transform(lon, lat)
    x, y = np.asarray(x), np.asarray(y)
    b = ds.bounds
    ic = np.isfinite(x) & np.isfinite(y) & (x > b.left) & (x < b.right) & (y > b.bottom) & (y < b.top)
    assert ic.sum() > 1000
    biz = k.ornekle(lat[ic], lon[ic])
    onlar = np.array([v[0] for v in ds.sample(zip(x[ic], y[ic]))])
    _ayni(biz, onlar)


@pytest.mark.parametrize("ad,R,lat0,lat1", [("lola", 1737400.0, -90, 90), ("swim", 3396190.0, -60, 60)])
def test_metre_silindirik_rasterio_ile_ayni(ad, R, lat0, lat1):
    k = K.ac(ad)
    lat, lon = _rastgele(np.random.default_rng(7), 3000, lat0 + 1e-6, lat1 - 1e-6)
    biz = k.ornekle(lat, lon)
    m = math.pi * R / 180.0
    onlar = np.array([v[0] for v in k.kaynak.sample(zip(lon * m, lat * m))])
    _ayni(biz, onlar)


def test_mola_jezero():
    # belge 17.3 D2: Jezero merkezi (18,44, 77,45) yaklaşık −2570 m (PDS MEGDR çapraz ürün)
    v = float(K.ac("mola").ornekle(18.44, 77.45))
    assert abs(v + 2570) < 100, v


def test_pgda_anormal_piksel_nan():
    # belge 10.2: anormal piksel 88,435°K 106,602°D NaN
    for ad in ("lpsr_n", "avgvisib_n"):
        k = K.ac(ad)
        assert np.isnan(k.ornekle(88.435, 106.602)), ad
        assert np.isfinite(k.ornekle(88.435 + 0.05, 106.602)), ad


def test_pgda_en_soguk_ucgenler_guney():
    # D2 testinin katman.py ile tekrarı: |enlem| ≥ 85° güney en soğuk 100 PRP üçgeni (temp_max) → LPSR = 1 oranı ≥ 0,9
    kl = K._kl("ay", "M4")
    lat = np.load(kl / "prp_south_tri_clat.npy"); lon = np.load(kl / "prp_south_tri_clon.npy")
    t = np.load(kl / "prp_south_temp_max.npy")
    m = np.abs(lat) >= 85
    o = np.argsort(t[m])[:100]
    lp = K.ac("lpsr_s").ornekle(lat[m][o], lon[m][o])
    assert np.mean(lp == 1.0) >= 0.9, float(np.mean(lp == 1.0))


@pytest.mark.parametrize("kutup", ["n", "s"])
def test_gcp_ghrm_70_derece(kutup):
    # belge 8.3 "Ay Tgece birleştirme": 70° bandında GCP (gece yarısı) ile GHRM tbol farkı < 1 K
    kl = K._kl("ay", "M4")
    b = "70n80n" if kutup == "n" else "80s70s"
    clat, ltim, tb = (np.load(kl / f"gcp_{b}_{s}.npy") for s in ("clat", "ltim", "tbol"))
    m = (np.abs(clat) < 70.5) & ((ltim < 0.5) | (ltim >= 23.5)) & np.isfinite(tb)
    gcp = float(np.mean(tb[m]))
    ds = K.ac("tbol").kaynak
    from rasterio.windows import Window
    satir = Window(0, 0, ds.width, 64) if kutup == "n" else Window(0, ds.height - 64, ds.width, 64)
    ghrm = float(np.nanmean(ds.read(1, window=satir)))
    assert abs(gcp - ghrm) < 1.0, (gcp, ghrm)


def test_tes_ve_dci_veri_yok_kodu_kalmadi():
    # belge 8.3: TES b6 = −1 → null; DCI = 0,85 → null
    for ad in ("tes_plagioclase", "tes_low_ca_pyroxene", "tes_high_ca_pyroxene"):
        a = np.asarray(K.ac(ad).kaynak)
        assert not (a == -1).any(), ad
    assert not (np.asarray(K.ac("dci").kaynak) == np.float32(0.85)).any()


def test_gcp_gece_kapsami():
    for ad in ("gcp_gece_n", "gcp_gece_s"):
        d = K.ac(ad).kaynak
        assert np.isfinite(d).mean() > 0.99, (ad, float(np.isfinite(d).mean()))


@pytest.mark.parametrize("govde,lat,lon,katman", [("ay", -89.0, 30.0, "lola"),          # belge 9.1 M-SP
                                                  ("mars", 18.44, 77.45, "mola"),        # belge 9.2 R-JEZ
                                                  ("dunya", 35.58223, -111.63182, "etopo")])  # belge 9.3 SP Crater
def test_gercek_pencere_dem(govde, lat, lon, katman):
    r = Z.yaricap(govde)
    v, coarse, s = K.hucreye(K.ac(katman), [math.radians(lat)], [math.radians(lon)], r, genisletme=2)
    assert v.shape == (1, 44, 44) and np.isfinite(v).all() and not coarse[0] and s[0] >= 2


def test_vektor_sentetik():
    import shapely
    v = K.Vektor("t", [shapely.box(-1, -1, 0, 1), shapely.box(0, -1, 1, 1)], ["a", "b"], "EPSG:4326")
    assert v.sinif(np.array([0.5, 0.5, 5.0]), np.array([-0.5, 0.5, 5.0])).tolist() == [0, 1, -1]
    pay, gec = K.hucreye_sinif(v, [0.0], [0.0], 6371.0)
    lat, lon = K._alt_noktalar([0.0], [0.0], 6371.0, 0, 1)
    sol = lon[0, :, :, 0, 0] < -0.003
    sag = lon[0, :, :, 0, 0] > 0.003
    assert (pay[0][sol][:, 0] == 1).all() and (pay[0][sag][:, 1] == 1).all() and (gec[0] == 25).all()


@pytest.fixture(scope="module")
def glim():
    return K.ac("glim")


def test_glim_siniflari(glim):
    belge_6_3 = {"va", "vi", "vb", "py", "pb", "pa", "pi", "su", "ss", "sm", "sc", "ev", "mt", "ig", "wb", "nd"}
    assert set(glim.siniflar) <= belge_6_3, set(glim.siniflar) - belge_6_3


def test_glim_sp_crater(glim):
    pay, gec = K.hucreye_sinif(glim, [math.radians(35.58223)], [math.radians(-111.63182)], 6371.0)
    assert (gec[0] == 25).mean() > 0.9


def test_ay_ve_mars_jeoloji():
    ay = K.ac("ay_jeoloji")
    assert {"Im1", "Im2", "Em", "Imd", "Id", "EIp"} & set(ay.siniflar)
    mars = K.ac("sim3292")
    assert len(mars.siniflar) == 44
    assert (K.hucreye_sinif(mars, [math.radians(18.44)], [math.radians(77.45)], 3389.5)[1] == 25).all()
