# Developed with assistance from Claude (Anthropic).
"""Belge 8.3: 'Lambert penceresi' ve 'Halka ızgarası' testleri (tanım: 14 Kasım notu, kayit\\degisiklik.md)."""
import numpy as np
import pytest
import ayar as A
import izgara as Z

G = ["dunya", "ay", "mars"]
D = 20.0


@pytest.fixture(scope="module")
def halkalar():
    return {g: Z.Halka(g) for g in G}


def test_haversine():
    r = 6371.0
    assert abs(Z.haversine(0.0, 0.0, 0.0, np.pi / 2, r) - np.pi * r / 2) < 1e-9
    assert abs(Z.haversine(np.pi / 2, 0.0, -np.pi / 2, 0.0, r) - np.pi * r) < 1e-6


@pytest.mark.parametrize("phi0_der", [0.0, 45.0, 89.9, -45.0, -89.9])
def test_lambert_gidis_donus(phi0_der):
    r, phi0, lam0 = 1737.4, np.radians(phi0_der), np.radians(179.9)
    g = np.random.default_rng(1)
    x, y = g.uniform(-15, 15, 5000), g.uniform(-15, 15, 5000)
    phi, lam = Z.lambert_geri(x, y, phi0, lam0, r)
    x2, y2 = Z.lambert_ileri(phi, lam, phi0, lam0, r)
    assert np.max(np.abs(x2 - x)) < 1e-9 and np.max(np.abs(y2 - y)) < 1e-9


def _kure_alan(phi, lam, merkez, r):
    # Merkezden yelpaze üçgenler; tan(E/2) = |c·(a×b)| / (1 + a·b + b·c + c·a)
    a = Z.birim_vektor(phi, lam)
    b = np.roll(a, -1, axis=0)
    c = Z.birim_vektor(*merkez)
    ust = np.abs(np.cross(a, b) @ c)
    alt = 1 + np.einsum("ij,ij->i", a, b) + a @ c + b @ c
    return np.sum(2 * np.arctan2(ust, alt)) * r * r


@pytest.mark.parametrize("govde", G)
@pytest.mark.parametrize("phi0_der", [0.0, 45.0, 89.9])
def test_lambert_pencere_alani(govde, phi0_der):
    r, L = Z.yaricap(govde), float(A.ayar("izgara.L_km"))
    h, k = L / 2, 2000
    t = np.linspace(-h, h, k, endpoint=False)
    x = np.concatenate([t, np.full(k, h), -t, np.full(k, -h)])
    y = np.concatenate([np.full(k, -h), t, np.full(k, h), -t])
    phi0, lam0 = np.radians(phi0_der), np.radians(179.9)
    phi, lam = Z.lambert_geri(x, y, phi0, lam0, r)
    alan = _kure_alan(phi, lam, (phi0, lam0), r)
    assert abs(alan / (L * L) - 1) < 1e-3, alan


def test_pencere_merkezleri():
    N, r = int(A.ayar("izgara.N")), 6371.0
    phi0, lam0 = np.radians(45.0), np.radians(179.9)
    c = Z.hucre_merkezleri()
    assert len(c) == N and abs(c[0] + 9.75) < 1e-12 and abs(c[-1] - 9.75) < 1e-12
    phi, lam = Z.pencere(phi0, lam0, r)
    assert phi.shape == (N, N)
    x, y = Z.lambert_ileri(phi, lam, phi0, lam0, r)
    assert np.allclose(x, c[None, :], atol=1e-9) and np.allclose(y, c[:, None], atol=1e-9)
    assert np.all(np.diff(phi[:, N // 2]) > 0)
    assert Z.pencere(phi0, lam0, r, genisletme=2)[0].shape == (N + 4, N + 4)


@pytest.mark.parametrize("govde", G)
def test_halka_araliklari(halkalar, govde):
    H = halkalar[govde]
    assert abs(H.r * H.dphi / D - 1) < 0.05
    s = 2 * np.pi * H.r * np.cos(H.phi_halka) / H.m
    assert np.all(np.abs(s / D - 1) < 0.05), float(s[np.argmax(np.abs(s / D - 1))])
    assert abs(H.n / (4 * np.pi * H.r ** 2 / D ** 2) - 1) < 0.01
    d, _ = H.agac.query(Z.birim_vektor(H.phi, H.lam), k=2)
    gc = 2 * H.r * np.arcsin(d[:, 1] / 2)
    ic = (H.i > 0) & (H.i < H.M - 1)
    assert gc[ic].min() > 0.95 * D and gc[ic].max() < 1.05 * D, (gc[ic].min(), gc[ic].max())
    assert H.m[0] == H.m[-1] == 3


def _kure_noktalari(g, n):
    lat = np.degrees(np.arcsin(g.uniform(-1, 1, n)))
    lon = g.uniform(-180, 180, n)
    zc = g.uniform(np.sin(np.radians(85)), 1, n)
    isaret = g.choice([-1.0, 1.0], n)
    lat = np.concatenate([lat, isaret * np.degrees(np.arcsin(zc)), [90.0, -90.0]])
    lon = np.concatenate([lon, g.uniform(-180, 180, n), [0.0, 0.0]])
    return lat, lon


@pytest.mark.parametrize("govde", G)
def test_kutupta_bosluk_yok(halkalar, govde):
    H = halkalar[govde]
    lat, lon = _kure_noktalari(np.random.default_rng(2), 100000)
    d, _ = H.en_yakin(lat, lon)
    assert d.max() < 15.0, d.max()


@pytest.mark.parametrize("govde", G)
def test_tiklama_merkez_ve_yakini(halkalar, govde):
    H = halkalar[govde]
    g = np.random.default_rng(3)
    k = np.unique(np.concatenate([g.choice(H.n, 20000, replace=False), H.ofset[:-1], H.ofset[1:] - 1]))
    lat, lon = H.merkez_der(k)
    assert np.array_equal(H.tikla(lat, lon), k)
    rr, az = g.uniform(0, 5, len(k)), g.uniform(0, 2 * np.pi, len(k))
    phi, lam = Z.lambert_geri(rr * np.sin(az), rr * np.cos(az), H.phi[k], H.lam[k], H.r)
    plat, plon = np.degrees(phi), np.degrees(lam)
    assert np.array_equal(H.tikla(plat, plon), k)
    _, yak = H.en_yakin(plat, plon)
    assert np.array_equal(yak, k)


def kose_uzakligi(H):
    """Her halkada hücre köşesinin merkeze büyük çember uzaklığı (hücrenin en uzak noktası)."""
    ust = np.minimum(H.phi_halka + H.dphi / 2, np.pi / 2)
    alt = np.maximum(H.phi_halka - H.dphi / 2, -np.pi / 2)
    yarim = np.pi / H.m
    return np.maximum(Z.haversine(H.phi_halka, 0.0, ust, yarim, H.r),
                      Z.haversine(H.phi_halka, 0.0, alt, yarim, H.r))


@pytest.mark.parametrize("govde", G)
def test_tiklama_rastgele(halkalar, govde):
    H = halkalar[govde]
    lat, lon = _kure_noktalari(np.random.default_rng(4), 100000)
    k = H.tikla(lat, lon)
    phi, lam = np.radians(lat), np.radians(np.mod(lon, 360.0))
    i, j = H.i[k], H.j[k]
    e = 1e-12
    assert np.all(phi >= H.phi_halka[i] - H.dphi / 2 - e) and np.all(phi <= H.phi_halka[i] + H.dphi / 2 + e)
    assert np.all(lam >= j * 2 * np.pi / H.m[i] - e) and np.all(lam < (j + 1) * 2 * np.pi / H.m[i] + e)
    d = Z.haversine(phi, lam, H.phi[k], H.lam[k], H.r)
    asim = d - kose_uzakligi(H)[i]
    assert asim.max() <= 1e-6, float(asim.max())


def test_komsular(halkalar):
    H = halkalar["ay"]
    lat, lon = H.merkez_der(12345)
    idx, d = H.komsular(lat, lon)
    assert len(idx) == 20 and 12345 not in idx and np.all(np.diff(d) >= -1e-9) and d.max() < 60
    idx2, d2 = H.komsular(-89.0, 30.0)
    assert len(idx2) == 20 and d2.max() < 60
