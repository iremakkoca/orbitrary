# Developed with assistance from Claude (Anthropic).
# 17.4 sıra 5: kod\\ozellik_topo.py + testler (belge 6.1; 8.2 Horn eğimi, VRM, rölyef)
import sys, subprocess, datetime
from pathlib import Path

KOK = Path.home() / "orbitrary"
KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / "ozellik_topo.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 6.1 Kategori 1 — Topografya: Horn eğimi, VRM, ortalama eğrilik H, rölyef R, iki ölçek, IQR, d₁.

Girdi: pencere DEM'i h, biçim [..., j, i] (j kuzey, i doğu), pencerenin GEN = 8 hücre dışından okunmuş
(56 × 56): belge 6.1 "kenar hücreleri için 2 hücre dışarıdan" kuralı her ölçekte (500 m'de 2 hücre,
2 km'de 2 blok = 8 hücre).
- s = 1: δ₁ = 500 m, ortadaki 44 × 44 → türevler 42 × 42 → θ, H, VRM 40 × 40.
- s = 4: h⁽⁴⁾_IJ = 4 × 4 blok ortalaması (bloklar pencere hücreleriyle hizalı), 14 × 14 → 10 × 10, δ₄ = 2 km.
Birimler: θ radyan, VRM birimsiz, H 1/m, h ve R metre.
"""
import numpy as np

import ayar as A
import uzaklik as U

GEN = 8  # ince hücre cinsinden okuma genişletmesi
OZELLIKLER = ["theta_1", "vrm_1", "H_1", "theta_4", "vrm_4", "H_4"]  # F_T adayları (f, s)


def delta_m(s):
    return float(A.ayar("izgara.delta_m")) * s


def turevler(h, d):
    """Belge 6.1 Horn birinci türevleri [51] ve ikinci türevler [127]; iç bölge (her kenardan 1 hücre eksik)."""
    c = h[..., 1:-1, 1:-1]
    E, W = h[..., 1:-1, 2:], h[..., 1:-1, :-2]
    N, S = h[..., 2:, 1:-1], h[..., :-2, 1:-1]
    NE, NW = h[..., 2:, 2:], h[..., 2:, :-2]
    SE, SW = h[..., :-2, 2:], h[..., :-2, :-2]
    hx = ((NE + 2 * E + SE) - (NW + 2 * W + SW)) / (8 * d)
    hy = ((NE + 2 * N + NW) - (SE + 2 * S + SW)) / (8 * d)
    hxx = (E - 2 * c + W) / d ** 2
    hyy = (N - 2 * c + S) / d ** 2
    hxy = (NE - NW - SE + SW) / (4 * d ** 2)
    return hx, hy, hxx, hyy, hxy


def egim(hx, hy):
    """θ = arctan √(h_x² + h_y²) (radyan)."""
    return np.arctan(np.sqrt(hx ** 2 + hy ** 2))


def vrm(hx, hy):
    """VRM_ij = 1 − (1/9) ‖Σ_{3×3} n‖, n = (−h_x, −h_y, 1)/√(1 + h_x² + h_y²). Girdi kenarından 1 hücre eksik çıkar."""
    nrm = np.sqrt(1 + hx ** 2 + hy ** 2)
    n = np.stack([-hx / nrm, -hy / nrm, 1.0 / nrm], axis=-1)
    t = sum(n[..., 1 + a: n.shape[-3] - 1 + a, 1 + b: n.shape[-2] - 1 + b, :] for a in (-1, 0, 1) for b in (-1, 0, 1))
    return 1.0 - np.linalg.norm(t, axis=-1) / 9.0


def egrilik(hx, hy, hxx, hyy, hxy):
    """Ortalama eğrilik H (z = h(x, y)); H > 0 çukur, H < 0 tümsek."""
    D = 1 + hx ** 2 + hy ** 2
    return ((1 + hy ** 2) * hxx - 2 * hx * hy * hxy + (1 + hx ** 2) * hyy) / (2 * D ** 1.5)


def blok4(h):
    """h⁽⁴⁾_IJ = (1/16) Σ_{u,v=0..3} h_{4I−u, 4J−v} (blokta NaN varsa NaN)."""
    *on, nj, ni = h.shape
    assert nj % 4 == 0 and ni % 4 == 0
    return h.reshape(*on, nj // 4, 4, ni // 4, 4).mean(axis=(-3, -1))


def _olcek(h, d):
    """Bir ölçekte: girdi (pencere + 2 hücre/blok her yanda) → θ, H, VRM (pencere), Ω_s."""
    hx, hy, hxx, hyy, hxy = turevler(h, d)
    ic = (Ellipsis, slice(1, -1), slice(1, -1))
    th = egim(hx[ic], hy[ic])
    H = egrilik(hx[ic], hy[ic], hxx[ic], hyy[ic], hxy[ic])
    V = vrm(hx, hy)
    with np.errstate(invalid="ignore"):
        omega = np.nanmax((np.abs(hxx[ic]) + np.abs(hxy[ic]) + np.abs(hyy[ic])).reshape(*h.shape[:-2], -1), axis=-1)
    return th, V, H, omega


def ozellikler(h_genis, govde):
    """h_genis: (..., 56, 56) metre. Dönüş sözlüğü:
    theta_1, vrm_1, H_1 (..., 40, 40); theta_4, vrm_4, H_4 (..., 10, 10); R (rölyef, m); lnR; Omega_1, Omega_4;
    dem_tam (genişletilmiş DEM'de NaN yok)."""
    h = np.asarray(h_genis, dtype=np.float64)
    N = int(A.ayar("izgara.N"))
    assert h.shape[-2:] == (N + 2 * GEN, N + 2 * GEN), h.shape
    sv = float(A.ayar("cisim.sigma_v_m")[govde])
    k = GEN - 2
    h1 = h[..., k:-k, k:-k]                        # 44 × 44
    t1, v1, H1, o1 = _olcek(h1, delta_m(1))
    t4, v4, H4, o4 = _olcek(blok4(h), delta_m(4))  # 14 × 14 → 10 × 10
    W = h[..., GEN:-GEN, GEN:-GEN]                 # pencerenin kendisi 40 × 40
    duz = W.reshape(*W.shape[:-2], -1)
    with np.errstate(invalid="ignore"):
        fark = np.nanmax(duz, axis=-1) - np.nanmin(duz, axis=-1)
    R = np.where(np.isfinite(fark), np.maximum(fark, sv), np.nan)
    return {"theta_1": t1, "vrm_1": v1, "H_1": H1, "theta_4": t4, "vrm_4": v4, "H_4": H4,
            "R": R, "lnR": np.log(R), "Omega_1": o1, "Omega_4": o4,
            "dem_tam": np.isfinite(h.reshape(*h.shape[:-2], -1)).all(axis=-1)}


def yuzdelik_vektorleri(oz):
    """Altı (f, s) özelliğinin 1000 noktalı yüzdelik vektörleri: (..., 6, M)."""
    Q = [U.yuzdelik(oz[f].reshape(*oz[f].shape[:-2], -1)) for f in OZELLIKLER]
    return np.stack(Q, axis=-2)


def ceyrek(x, pay, payda):
    """F⁻¹(pay/payda) genelleştirilmiş ters, tam sayı aritmetiği (k = ⌈n·pay/payda⌉)."""
    x = np.sort(np.asarray(x, float)[np.isfinite(x)])
    n = x.size
    if n == 0:
        return np.nan
    k = -(-(n * pay) // payda)
    return x[max(k, 1) - 1]


def iqr_hedef(oz_listesi):
    """Belge 6.1: IQR_T(f_s) = F⁻¹(0,75) − F⁻¹(0,25), N(T)'deki 21 pencerenin değerlerinin birleşimi.
    oz_listesi: her pencere için ozellikler() sözlüğü. Dönüş: (6,) dizi."""
    out = np.empty(len(OZELLIKLER))
    for i, f in enumerate(OZELLIKLER):
        v = np.concatenate([np.asarray(o[f], float).ravel() for o in oz_listesi])
        out[i] = ceyrek(v, 3, 4) - ceyrek(v, 1, 4)
    return out


def d1(Q_aday, lnR_aday, Q_hedef, lnR_hedef, iqr):
    """Belge 6.1: d₁(A, T) = (Σ_{F_T} W₁(f_s^A, f_s^T) / IQR_T(f_s) + |ln R_A − ln R_T|) / (|F_T| + 1).
    Q_aday (n, 6, M), lnR_aday (n,), Q_hedef (6, M), lnR_hedef skaler, iqr (6,). F_T = {IQR > 0}."""
    Q_aday = np.asarray(Q_aday, float)
    iqr = np.asarray(iqr, float)
    FT = np.isfinite(iqr) & (iqr > 0)
    w = np.mean(np.abs(Q_aday[:, FT, :] - np.asarray(Q_hedef, float)[None, FT, :]), axis=-1)  # (n, |F_T|)
    pay = np.sum(w / iqr[None, FT], axis=1) + np.abs(np.asarray(lnR_aday, float) - float(lnR_hedef))
    return pay / (FT.sum() + 1)


def z_topo(oz):
    """Belge 7.1 z vektörünün yükseklikten gelen ilk dört bileşeni: (θ̄, θ₀,₉, VRM̄, ln R) (500 m ölçeği)."""
    th = oz["theta_1"].reshape(*oz["theta_1"].shape[:-2], -1)
    v = oz["vrm_1"].reshape(*oz["vrm_1"].shape[:-2], -1)
    t09 = np.apply_along_axis(lambda a: ceyrek(a, 9, 10), -1, th)
    with np.errstate(invalid="ignore"):
        return np.stack([np.nanmean(th, axis=-1), t09, np.nanmean(v, axis=-1), oz["lnR"]], axis=-1)
''', encoding="utf-8")
(KOD / "testler" / "test_ozellik_topo.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
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
''', encoding="utf-8")

yol = KOD / "FONKSIYONLAR.md"
metin = yol.read_text(encoding="utf-8")
bas, son = "<!-- ozellik_topo.py -->", "<!-- /ozellik_topo.py -->"
blok = bas + "\n## ozellik_topo.py\n" + "\n".join("- " + s for s in [
    "6.1 h_x, h_y (Horn), h_xx, h_yy, h_xy → `ozellik_topo.turevler`",
    "6.1 θ → `ozellik_topo.egim`; VRM → `ozellik_topo.vrm`; H → `ozellik_topo.egrilik`",
    "6.1 h⁽⁴⁾ (4 × 4 blok) → `ozellik_topo.blok4`; iki ölçek ve R → `ozellik_topo.ozellikler`",
    "6.1 IQR_T(f_s), F_T → `ozellik_topo.iqr_hedef`; d₁ → `ozellik_topo.d1`",
    "8.1 Ω_s(W) → `ozellik_topo.ozellikler` (Omega_1, Omega_4)",
    "7.1 z'nin (θ̄, θ₀,₉, VRM̄, ln R) bileşenleri → `ozellik_topo.z_topo`"]) + "\n" + son
metin = (metin.split(bas)[0] + blok + metin.split(son)[1]) if bas in metin else (metin.rstrip() + "\n\n" + blok + "\n")
yol.write_text(metin, encoding="utf-8")

deg = KAYIT / "degisiklik.md"
satir = ("- 2026-11-14 | Belge 6.1 'kenar hücreleri için 2 hücre dışarıdan' her ölçekte uygulandı: DEM pencerenin 8 ince hücre "
         "dışından okunur (500 m'de 2 hücre, 2 km'de 2 blok) | neden: 2 km ölçeğinde VRM ve türev kenar bloklarında da tam "
         "komşulukla hesaplanır | etkisi: yok (yöntem aynı; Implementation)\n")
d = deg.read_text(encoding="utf-8")
if "her ölçekte uygulandı" not in d:
    deg.write_text(d + satir, encoding="utf-8")

r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "testler"],
                   cwd=KOD, capture_output=True, text=True)
cikti = r.stdout + r.stderr
(KAYIT / "D4_test_ozellik_topo.txt").write_text(cikti, encoding="utf-8")
print(cikti[-3000:])
durum = "PASS" if r.returncode == 0 else "FAIL"
with open(KAYIT / "14_kasim_log.txt", "a", encoding="utf-8") as f:
    f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\tozellik_topo.py+test\t{durum}\n")
print(f"\ntestler: {durum}")
