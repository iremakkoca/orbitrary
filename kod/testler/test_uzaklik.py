# Developed with assistance from Claude (Anthropic).
"""Belge 8.2: W₁, TV, cisim içi sıra, pozitifler arasında sıra, ters sıra; v1.2 su/buz sırası testi."""
import numpy as np
import pytest
import uzaklik as U


def test_w1_kendisi_ve_kaydirma():
    # 8.2: bir dağılım ile kendisi → 0; bütün değerler 4 kaydırılmış → 4
    x = np.random.default_rng(0).normal(size=1600)
    qa = U.yuzdelik(x)
    assert U.w1(qa, qa) == 0.0
    assert abs(U.w1(qa, U.yuzdelik(x + 4.0)) - 4.0) < 1e-12


def test_w1_esit_uzunluk_sirali_formul():
    # 5.1: eşit uzunluklu sıralı vektörlerde W₁ = (1/n) Σ |x_(l) − y_(l)|  (n = M = 1000)
    g = np.random.default_rng(1)
    x, y = g.normal(size=1000), g.exponential(size=1000)
    assert np.array_equal(U.yuzdelik(x), np.sort(x))
    assert abs(U.w1(U.yuzdelik(x), U.yuzdelik(y)) - np.mean(np.abs(np.sort(x) - np.sort(y)))) < 1e-12


def test_w1_matris():
    g = np.random.default_rng(2)
    A_ = U.yuzdelik(g.normal(size=(7, 1600)))
    B_ = U.yuzdelik(g.normal(size=(5, 1600)))
    m = U.w1_matris(A_, B_, parca=3)
    assert m.shape == (7, 5)
    assert np.allclose(m, [[U.w1(a, b) for b in B_] for a in A_])


def test_yuzdelik_nan():
    x = np.array([np.nan, 1.0, 2.0, np.nan])
    assert np.array_equal(U.yuzdelik(x, 4), [1.0, 1.0, 2.0, 2.0])
    assert np.isnan(U.yuzdelik(np.full(5, np.nan))).all()


def test_tv_8_2():
    # 8.2: (0,84; 0,16; 0) ve (0,10; 0,60; 0,30) → 0,74
    assert abs(U.tv([0.84, 0.16, 0.0], [0.10, 0.60, 0.30]) - 0.74) < 1e-12
    a, b = np.array([0.84, 0.16, 0.0]), np.array([0.10, 0.60, 0.30])
    assert abs((1 - U.tv(a, b)) - np.minimum(a, b).sum()) < 1e-12  # 5.3: 1 − TV = Σ min
    assert np.isnan(U.tv([np.nan, 0.5, 0.5], [0.2, 0.3, 0.5]))


def test_cisim_ici_sira_8_2():
    # 8.2: (1, 1, 2, 3) → u(1) = 0,25; u(2) = 0,625
    u = U.Sira([1, 1, 2, 3])
    assert u(1.0) == 0.25 and u(2.0) == 0.625


def test_pozitifler_arasinda_sira_8_2():
    # 8.2: (0, 0, 1, 1, 2) → u⁺(0) = 0; u⁺(1) = 1/3; u⁺(2) = 5/6
    up = U.SiraPozitif([0, 0, 1, 1, 2])
    assert up(0.0) == 0.0 and abs(up(1.0) - 1 / 3) < 1e-15 and abs(up(2.0) - 5 / 6) < 1e-15


def test_ters_sira_8_2():
    # 8.2: aynı değerler, sıralama ters → 1 − u(x) ters sıraya eşit (çok sayıda eşit değerle)
    g = np.random.default_rng(3)
    r = g.integers(0, 5, 2000).astype(float)
    x = np.array([0.0, 1.0, 2.5, 4.0, -1.0, 7.0])
    assert np.allclose(U.Sira(r).ters(x), U.Sira(-r)(-x))


def test_su_buz_sifir_orani_8_2():
    # v1.2 8.2: Dünya'da sıfır oranı %85'ten %95'e → pozitiflerin sırası değişmez
    g = np.random.default_rng(4)
    pos = g.uniform(0.01, 1.0, 1000)
    r85 = np.concatenate([np.zeros(5667), pos])   # 5667 / 6667 ≈ %85
    r95 = np.concatenate([np.zeros(19000), pos])  # 19000 / 20000 = %95
    x = np.array([0.0, 0.05, 0.3, 0.9])
    assert np.array_equal(U.SiraPozitif(r85)(x), U.SiraPozitif(r95)(x))
    assert U.SiraPozitif(r95).sifir_orani == 0.95


def test_sira_nan_gecer():
    u = U.Sira([1.0, 2.0])
    assert np.isnan(u(np.nan)) and np.isnan(U.SiraPozitif([1.0])(np.nan))


def test_kure_noktalari_alanca_duzgun():
    lat, lon = U.kure_noktalari(np.random.default_rng(5), 400000)
    # z = sin φ düzgün → kuzey ve güney kutup başlıkları (|φ| > 60°) toplam alan payı 1 − sin 60° ≈ 0,134
    assert abs(np.mean(np.abs(lat) > 60) - (1 - np.sin(np.radians(60)))) < 0.003
    assert abs(np.mean(lon > 0) - 0.5) < 0.003


def test_referans_orneklem_tekrar_ve_kapsama():
    f = lambda la, lo: np.where(la > 0, la, np.nan)  # yalnız kuzey yarıküre kapsıyor
    v1, b1 = U.referans_orneklem("deneme", f, n_en_fazla=50000, parti=20000)
    v2, _ = U.referans_orneklem("deneme", f, n_en_fazla=50000, parti=20000)
    assert np.array_equal(v1, v2) and v1.size == 50000 and (v1 > 0).all()
    assert abs(b1["kapsama_orani"] - 0.5) < 0.02
    v3, _ = U.referans_orneklem("baska", f, n_en_fazla=50000, parti=20000)
    assert not np.array_equal(v1, v3)
    vb, bb = U.referans_orneklem("bant", f, bantlar=((70.0, 90.0),), n_en_fazla=10000, parti=5000)
    assert (vb >= 70).all() and bb["kapsama_orani"] == 1.0


@pytest.mark.parametrize("n", [1, 2, 3, 7, 500, 999, 1000, 1001, 1599, 1600, 2000, 4000])
def test_yuzdelik_genellestirilmis_ters(n):
    # F⁻¹(q) = en küçük x: F(x) ≥ q (ECDF); q = (m − ½)/M. Tam kesirlerle (fractions) bağımsız hesap.
    from fractions import Fraction
    g = np.random.default_rng(n)
    x = np.round(g.normal(size=(4, n)), 2)            # eşit değerler de olsun
    x[1, : n // 3] = np.nan                            # bir satırda eksik değer
    Q = U.yuzdelik(x)
    for i in range(4):
        xi = np.sort(x[i][np.isfinite(x[i])])
        N = len(xi)
        for m in (1, 2, 17, 18, 137, 500, 999, 1000):
            q = Fraction(2 * m - 1, 2000)
            k = next(j for j in range(1, N + 1) if Fraction(j, N) >= q)
            assert Q[i, m - 1] == xi[k - 1], (i, m)
