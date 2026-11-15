# Developed with assistance from Claude (Anthropic).
# 17.4 sıra 6: kod\\ozellik_topoloji.py + testler (belge 6.2; 8.2 SW = 0, R = 0 → diyagram boş; K12; GUDHI = union-find)
import sys, subprocess, datetime
from pathlib import Path

KOK = Path.home() / "orbitrary"
KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / "ozellik_topoloji.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 6.2 Kategori 2 — Topoloji: ĥ, ȇ normalizasyonu, küpsel H₀ (GUDHI [45]), Sliced Wasserstein (Mθ = 50), d₂.

- R_top = max(max_W h − min_W h, κσv); ĥ = (h − min_W h)/R_top (çukurlar), ȇ = (max_W h − h)/R_top (tepeler).
- Küpsel kompleks: hücreler 2-küp; yüzlerin filtrasyon değeri komşu hücrelerin en küçüğü (GUDHI
  top_dimensional_cells). H₀ diyagramı; sonsuz sınıf ve sıfır kalıcılıklı çiftler çıkarılır.
- SW (belge 6.2, Carrière ve ark. [13]): (1/π) ∫_{−π/2}^{π/2} W₁(ν¹_θ, ν²_θ) dθ ≈ (1/Mθ) Σ_j W₁, θ_j orta noktalar.
  W₁ eşit kütleli sayma ölçüleri arasında sıralı izdüşüm farklarının mutlak değerlerinin TOPLAMI.
  Normalizasyon Carrière ve ark.'nın S¹ üzerindeki (1/2π) tanımıyla aynı (K12 tetiklenmez; testte gösterilir).
- d₂(A, B) = SW(Dgm↓_A, Dgm↓_B) + SW(Dgm↑_A, Dgm↑_B).
- n↓, n↑ (belge 7.1 z): R_top (d − b) ≥ κσv olan nokta sayısı.
Girdi: pencerenin 40 × 40 hücre DEM'i (m), [j, i]. DEM'de NaN varsa topoloji hesaplanmaz (None).
"""
import math

import numpy as np

import ayar as A


def kappa_sigma(govde):
    return float(A.ayar("topoloji.kappa")) * float(A.ayar("cisim.sigma_v_m")[govde])


def normalize(h, govde):
    """(ĥ, ȇ, R_top) ya da DEM eksikse None."""
    h = np.asarray(h, dtype=np.float64)
    if not np.isfinite(h).all():
        return None
    lo, hi = h.min(), h.max()
    Rt = max(hi - lo, kappa_sigma(govde))
    return (h - lo) / Rt, (hi - h) / Rt, Rt


def h0_gudhi(f):
    """GUDHI CubicalComplex (top_dimensional_cells = f) H₀ sonlu çiftleri (b, d), d > b; sonsuz sınıf hariç."""
    import gudhi
    cc = gudhi.CubicalComplex(top_dimensional_cells=np.asarray(f, dtype=np.float64))
    cc.compute_persistence(homology_coeff_field=2, min_persistence=0.0)
    D = np.asarray(cc.persistence_intervals_in_dimension(0), dtype=np.float64).reshape(-1, 2)
    D = D[np.isfinite(D[:, 1]) & (D[:, 1] > D[:, 0])]
    return D[np.lexsort((D[:, 1], D[:, 0]))]


def h0_union_find(f):
    """Bağımsız başvuru: hücreler, 8-komşuluk (köşe paylaşan hücreler o köşede bağlanır), yaşlı kuralı.
    Aynı değerli hücrelerde sıra kararlı (değer, düz indeks)."""
    f = np.asarray(f, dtype=np.float64)
    nj, ni = f.shape
    duz = f.ravel()
    sira = np.lexsort((np.arange(duz.size), duz))
    ata = np.full(duz.size, -1, dtype=np.int64)
    dogum = np.empty(duz.size)

    def bul(a):
        k = a
        while ata[k] != k:
            k = ata[k]
        while ata[a] != k:
            ata[a], a = k, ata[a]
        return k

    ciftler = []
    for p in sira:
        ata[p] = p
        dogum[p] = duz[p]
        j, i = divmod(int(p), ni)
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                if dj == 0 and di == 0:
                    continue
                jj, ii = j + dj, i + di
                if 0 <= jj < nj and 0 <= ii < ni:
                    q = jj * ni + ii
                    if ata[q] < 0:
                        continue
                    ra, rb = bul(p), bul(q)
                    if ra == rb:
                        continue
                    # genç olan (doğumu büyük; eşitse sırada sonra gelen) ölür
                    if (dogum[ra], ra) < (dogum[rb], rb):
                        yasli, genc = ra, rb
                    else:
                        yasli, genc = rb, ra
                    if duz[p] > dogum[genc]:
                        ciftler.append((dogum[genc], duz[p]))
                    ata[genc] = yasli
    D = np.array(ciftler, dtype=np.float64).reshape(-1, 2)
    return D[np.lexsort((D[:, 1], D[:, 0]))]


def diyagramlar(h, govde, yontem="gudhi"):
    """(Dgm↓, Dgm↑, R_top) ya da DEM eksikse None."""
    n = normalize(h, govde)
    if n is None:
        return None
    hh, hc, Rt = n
    f = h0_gudhi if yontem == "gudhi" else h0_union_find
    return f(hh), f(hc), Rt


def _yonler(M_theta):
    j = np.arange(1, M_theta + 1)
    th = -math.pi / 2 + (j - 0.5) * math.pi / M_theta
    return np.stack([np.cos(th), np.sin(th)], axis=1)  # (Mθ, 2)


def sw(D1, D2, M_theta=None, yonler=None):
    """Belge 6.2 Sliced Wasserstein."""
    M_theta = int(A.ayar("uzaklik.M_theta")) if M_theta is None else int(M_theta)
    E = _yonler(M_theta) if yonler is None else yonler
    D1 = np.asarray(D1, float).reshape(-1, 2)
    D2 = np.asarray(D2, float).reshape(-1, 2)
    if D1.shape[0] == 0 and D2.shape[0] == 0:
        return 0.0
    P1 = np.concatenate([D1, np.repeat(((D2[:, 0] + D2[:, 1]) / 2)[:, None], 2, axis=1)], axis=0)
    P2 = np.concatenate([D2, np.repeat(((D1[:, 0] + D1[:, 1]) / 2)[:, None], 2, axis=1)], axis=0)
    a = np.sort(P1 @ E.T, axis=0)
    b = np.sort(P2 @ E.T, axis=0)
    return float(np.mean(np.sum(np.abs(a - b), axis=0)))


def d2(dA, dB):
    """d₂(A, B) = SW(↓) + SW(↑); dA, dB = (Dgm↓, Dgm↑, R_top). Biri None ise None (null)."""
    if dA is None or dB is None:
        return None
    return sw(dA[0], dB[0]) + sw(dA[1], dB[1])


def n_onemli(d, govde):
    """Belge 7.1: (n↓, n↑) = R_top (d − b) ≥ κσv olan nokta sayıları."""
    if d is None:
        return (np.nan, np.nan)
    Dd, Du, Rt = d
    e = kappa_sigma(govde)
    return (int(np.sum(Rt * (Dd[:, 1] - Dd[:, 0]) >= e)), int(np.sum(Rt * (Du[:, 1] - Du[:, 0]) >= e)))
''', encoding="utf-8")
(KOD / "testler" / "test_ozellik_topoloji.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 8.2: 'Topoloji: iki aynı diyagram → SW = 0', 'Rölyef: R = 0 → diyagram boş'; 6.2 normalizasyon, H₀, SW;
K12 (SW sabiti Carrière ve ark. ile aynı). Union-find başvurusu (GUDHI karşılaştırması ayrı dosyada)."""
import math
import numpy as np
import pytest
import ayar as A
import ozellik_topoloji as P


def test_ayni_diyagram_sw_sifir_8_2():
    D = np.array([[0.1, 0.5], [0.2, 0.9], [0.3, 0.35]])
    assert P.sw(D, D) == 0.0
    assert P.sw(np.zeros((0, 2)), np.zeros((0, 2))) == 0.0


def test_rolyef_sifir_diyagram_bos_8_2():
    for g in ("dunya", "ay", "mars"):
        d = P.diyagramlar(np.full((40, 40), 7.0), g, yontem="uf")
        assert d[0].shape == (0, 2) and d[1].shape == (0, 2) and d[2] == P.kappa_sigma(g)


def test_normalizasyon_kappa_taban():
    h = np.zeros((40, 40)); h[5, 5] = 3.0  # rölyef 3 m < κσv(Dünya) = 14,34 m
    hh, hc, Rt = P.normalize(h, "dunya")
    assert Rt == 2 * 7.17 and abs(hh[5, 5] - 3 / 14.34) < 1e-12 and abs(hc[0, 0] - 3 / 14.34) < 1e-12
    assert P.normalize(np.where(h > 0, np.nan, h), "dunya") is None


def test_iki_cukur_bilinen_diyagram():
    # iki çukur (0 ve 0,2) arasında 0,6'lık eşik: Dgm↓ = {(0,2; 0,6)} (sonsuz sınıf çıkarılır)
    f = np.full((5, 9), 1.0)
    f[2, 1] = 0.0
    f[2, 7] = 0.2
    f[2, 2:7] = 0.6
    D = P.h0_union_find(f)
    assert D.tolist() == [[0.2, 0.6]]


def test_capraz_komsuluk():
    # köşe paylaşan iki hücre küpsel kompleksteki ortak köşe üzerinden max(a, b)'de birleşir
    # 0 ve 0,3 çapraz: ortak köşenin değeri min = 0 → 0,3 anında bağlanır, (0,3; 0,3) sıfır kalıcılık → çift yok
    f = np.array([[0.0, 1.0], [1.0, 0.3]])
    assert P.h0_union_find(f).shape == (0, 2)
    # 4-komşulukta ise ayrı kalır ve 1,0'da birleşirdi: (0,3; 1,0) — bu kod 8-komşuluk kullanır


def test_sw_tek_nokta_analitik_ve_K12():
    # D1 = {(b, d)}, D2 = ∅: W₁(θ) = |(d − b)/2 (sin θ − cos θ)| → SW = √2 (d − b)/π (yarım çember, 1/π)
    b, d = 0.1, 0.7
    D1, D2 = np.array([[b, d]]), np.zeros((0, 2))
    analitik = math.sqrt(2) * (d - b) / math.pi
    assert abs(P.sw(D1, D2) - analitik) / analitik < 2e-3            # Mθ = 50 orta nokta
    assert abs(P.sw(D1, D2, M_theta=4000) - analitik) / analitik < 1e-6
    # K12: Carrière ve ark. tanımı (1/2π) ∫_{S¹} — tam çember üzerinde aynı değer
    t = (np.arange(8000) + 0.5) * 2 * math.pi / 8000
    tam = P.sw(D1, D2, yonler=np.stack([np.cos(t), np.sin(t)], 1))
    assert abs(tam - P.sw(D1, D2, M_theta=4000)) < 1e-6


def test_sw_simetrik_ve_pozitif():
    g = np.random.default_rng(0)
    b1 = g.uniform(0, 0.5, 12); D1 = np.stack([b1, b1 + g.uniform(0.01, 0.5, 12)], 1)
    b2 = g.uniform(0, 0.5, 7); D2 = np.stack([b2, b2 + g.uniform(0.01, 0.5, 7)], 1)
    assert P.sw(D1, D2) > 0 and abs(P.sw(D1, D2) - P.sw(D2, D1)) < 1e-12


def test_d2_ve_null():
    g = np.random.default_rng(1)
    h = g.normal(0, 50, (40, 40))
    dA = P.diyagramlar(h, "mars", yontem="uf")
    assert P.d2(dA, dA) == 0.0 and P.d2(dA, None) is None
    dB = P.diyagramlar(h + g.normal(0, 5, (40, 40)), "mars", yontem="uf")
    assert P.d2(dA, dB) > 0


def test_n_onemli():
    f = np.full((5, 9), 100.0)
    f[2, 1] = 0.0; f[2, 7] = 20.0; f[2, 2:7] = 60.0
    d = P.diyagramlar(np.pad(f, ((0, 35), (0, 31)), constant_values=100.0), "dunya", yontem="uf")
    # Dgm↓: (20, 60) m kalıcılık 40 m ≥ κσv = 14,34 m → n↓ = 1
    assert P.n_onemli(d, "dunya")[0] == 1
    assert all(np.isnan(P.n_onemli(None, "dunya")))
''', encoding="utf-8")
(KOD / "testler" / "test_topoloji_gudhi.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""GUDHI CubicalComplex H₀ = bağımsız union-find (8-komşuluk, yaşlı kuralı): rastgele, eşit değerli ve gerçek pencereler."""
import math
import numpy as np
import pytest
import ozellik_topoloji as P


def _ayni(a, b):
    assert a.shape == b.shape, (a.shape, b.shape)
    assert np.allclose(a, b, rtol=0, atol=1e-12)


@pytest.mark.parametrize("tohum", range(100))
def test_gudhi_union_find_rastgele(tohum):
    g = np.random.default_rng(tohum)
    f = g.normal(size=(40, 40))
    _ayni(P.h0_gudhi(f), P.h0_union_find(f))


@pytest.mark.parametrize("tohum", range(100))
def test_gudhi_union_find_esit_degerler(tohum):
    g = np.random.default_rng(1000 + tohum)
    f = np.round(g.normal(size=(40, 40)), 1)  # çok sayıda eşit değer
    _ayni(P.h0_gudhi(f), P.h0_union_find(f))


@pytest.mark.parametrize("govde,lat,lon,ad", [("ay", -89.0, 30.0, "lola"), ("mars", 18.44, 77.45, "mola"),
                                              ("dunya", 35.58223, -111.63182, "etopo")])
def test_gercek_pencere_topoloji(govde, lat, lon, ad):
    import izgara as Z
    import katman as K
    h, _, _ = K.hucreye(K.ac(ad), [math.radians(lat)], [math.radians(lon)], Z.yaricap(govde))
    dg = P.diyagramlar(h[0], govde, yontem="gudhi")
    du = P.diyagramlar(h[0], govde, yontem="uf")
    _ayni(dg[0], du[0]); _ayni(dg[1], du[1])
    assert dg[2] == du[2] and P.d2(dg, dg) == 0.0
    n = P.n_onemli(dg, govde)
    assert all(isinstance(v, int) and v >= 0 for v in n)
''', encoding="utf-8")

yol = KOD / "FONKSIYONLAR.md"
metin = yol.read_text(encoding="utf-8")
bas, son = "<!-- ozellik_topoloji.py -->", "<!-- /ozellik_topoloji.py -->"
blok = bas + "\n## ozellik_topoloji.py\n" + "\n".join("- " + s for s in [
    "6.2 R_top, ĥ, ȇ → `ozellik_topoloji.normalize`",
    "6.2 küpsel H₀ (GUDHI) → `ozellik_topoloji.h0_gudhi`; Dgm↓, Dgm↑ → `ozellik_topoloji.diyagramlar`",
    "6.2 SW (Mθ = 50) → `ozellik_topoloji.sw`; d₂ → `ozellik_topoloji.d2`",
    "7.1 n↓, n↑ → `ozellik_topoloji.n_onemli`",
    "(test başvurusu) H₀ union-find → `ozellik_topoloji.h0_union_find`"]) + "\n" + son
metin = (metin.split(bas)[0] + blok + metin.split(son)[1]) if bas in metin else (metin.rstrip() + "\n\n" + blok + "\n")
yol.write_text(metin, encoding="utf-8")

deg = KAYIT / "degisiklik.md"
satirlar = [
    "- 2026-11-14 | K12 kontrolü: belge 6.2 SW = (1/π)∫ yarım çember, Carrière ve ark. (1/2π)∫ S¹ ile aynı (θ ve θ+π izdüşümleri ayna) | K12 tetiklenmedi; Ψ₂ değişmez | test: test_sw_tek_nokta_analitik_ve_K12\n",
    "- 2026-11-14 | SW doğrultuları orta nokta: θ_j = −π/2 + (j − ½)π/Mθ (proje kararı) | etkisi: Implementation\n",
]
d = deg.read_text(encoding="utf-8")
yeni = [s for s in satirlar if s.split(" | ")[0][13:] + s.split(" | ")[1][:20] not in d and s.split(" | ")[1][:20] not in d]
if yeni:
    deg.write_text(d + "".join(yeni), encoding="utf-8")

r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "testler"],
                   cwd=KOD, capture_output=True, text=True)
cikti = r.stdout + r.stderr
(KAYIT / "D4_test_ozellik_topoloji.txt").write_text(cikti, encoding="utf-8")
print(cikti[-3000:])
durum = "PASS" if r.returncode == 0 else "FAIL"
with open(KAYIT / "14_kasim_log.txt", "a", encoding="utf-8") as f:
    f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\tozellik_topoloji.py+test (GUDHI=UF)\t{durum}\n")
print(f"\ntestler: {durum}")
