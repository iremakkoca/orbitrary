# Developed with assistance from Claude (Anthropic).
"""Belge 8.3 V1–V10 istatistik fonksiyonları."""
import numpy as np
import pytest
from scipy.stats import chi2, mannwhitneyu, spearmanr

import dogrula as D
import puan as Pn


def test_pi_ve_K14():
    P = np.array([0.1, 0.5, 0.5, 0.9, np.nan])
    assert D.pi_degeri(P, 0.5) == pytest.approx(3 / 5)
    assert D.pi_degeri(P, 0.95) == pytest.approx(4 / 5)
    assert D.pi_degeri(P, 0.5, kapidan_kaldi=True) == 0.0


def test_fisher_elle():
    pi = np.full(11, 0.5); n = 1000
    X, p = D.fisher_v1(pi, n)
    assert X == pytest.approx(-2 * 11 * np.log(0.5 + 1e-3)) and p == pytest.approx(chi2.sf(X, 22))
    X2, p2 = D.fisher_v2(np.full(22, 0.5), n)
    assert X2 == pytest.approx(-2 * 22 * np.log(0.5 + 1e-3))


def test_fisher_H0_altinda_duzgun():
    # Π ~ U(0,1) iken p ≈ U(0,1): ortalama 0,5, P(p < 0,05) ≈ 0,05 (büyük |E′|)
    rng = np.random.default_rng(1)
    p1 = np.array([D.fisher_v1(rng.random(11), 10 ** 7)[1] for _ in range(4000)])
    p2 = np.array([D.fisher_v2(rng.random(22), 10 ** 7)[1] for _ in range(4000)])
    for p in (p1, p2):
        assert abs(p.mean() - 0.5) < 0.02 and abs(np.mean(p < 0.05) - 0.05) < 0.012


def test_fisher_yon():
    # V1: analoglar üstte (Π büyük) → p küçük; V2: negatif kontroller altta (Π küçük) → X²₋ büyük → p küçük
    assert D.fisher_v1(np.full(11, 0.99), 10 ** 6)[1] < 1e-6
    assert D.fisher_v2(np.full(22, 0.01), 10 ** 6)[1] < 1e-6


def test_auc_kaba_kuvvet_ve_mw():
    rng = np.random.default_rng(2)
    a = rng.integers(0, 10, 11).astype(float); b = rng.integers(0, 10, 3000).astype(float)
    U = sum((x > y) + 0.5 * (x == y) for x in a for y in b)
    assert D.auc(a, b) == pytest.approx(U / (11 * 3000))
    assert D.auc(a, b) * 11 * 3000 == pytest.approx(mannwhitneyu(a, b).statistic)


def test_v3_tekrar_ve_GA():
    rng = np.random.default_rng(3)
    a = rng.random(11) + 0.3; b = rng.random(11000)
    r1, r2 = D.v3(a, b), D.v3(a, b)
    assert r1 == r2
    assert r1["GA95"][0] <= r1["AUC"] <= r1["GA95"][1] and r1["p"] < 0.05


def test_b_prime_ve_hedefler():
    B = D.b_prime(50000, 11)
    assert B.shape == (11, 1000) and all(len(set(r)) == 1000 for r in B)
    np.testing.assert_array_equal(B, D.b_prime(50000, 11))
    ay, ma = D.rastgele_hedefler(95000, 361000, "V5")
    assert len(ay) == len(set(ay)) == 100 and len(ma) == 100
    np.testing.assert_array_equal(ay, D.rastgele_hedefler(95000, 361000, "V5")[0])
    assert not np.array_equal(ay, D.rastgele_hedefler(95000, 361000, "V2")[0])   # farklı alt tohum → farklı küme


def test_v2_sec():
    rng = np.random.default_rng(5)
    o = rng.random(5000); t = rng.random(5000)
    oi, ti = D.v2_sec(o, t, 11)
    assert len(set(oi)) == 11 and np.all(o[oi] >= 0.9) and np.all(t[ti] >= 0.9)
    np.testing.assert_array_equal(oi, D.v2_sec(o, t, 11)[0])


def test_recall():
    assert D.recall([1, 2, 3], [3, 2, 9, 10]) == pytest.approx(2 / 3)
    assert D.recall([1, 2, 3], [1, 2, 3]) == 1.0


def test_spearman_matris():
    rng = np.random.default_rng(6)
    x = rng.random(500)
    S = np.column_stack([x, x ** 3, rng.random(500), -x, x, x, x, x])
    S[:50, 2] = np.nan
    r, n, yuksek = D.spearman_matris(S)
    assert r[0, 1] == pytest.approx(1) and r[0, 3] == pytest.approx(-1) and n[0, 2] == 450
    m = np.isfinite(S[:, 2])
    assert r[0, 2] == pytest.approx(spearmanr(S[m, 0], S[m, 2]).statistic)
    assert (1, 2, pytest.approx(1.0)) in [(k, l, v) for k, l, v in yuksek] and all(k != 3 and l != 3 for k, l, _ in yuksek)


def test_holm_elle():
    red, duz = D.holm([0.01, 0.04, 0.03, 0.005])
    np.testing.assert_array_equal(red, [True, False, False, True])
    np.testing.assert_allclose(duz, [0.03, 0.06, 0.06, 0.02])


def test_ablasyon_sabit_kategori():
    rng = np.random.default_rng(7)
    s = rng.random((300, 8)); s[:, 4] = 0.5
    z = rng.random((300, 8))
    t = D.ablasyon(s, z, Pn.kademeli_agirlik([5, 6, 8]), np.ones(300, bool))
    assert t[4] == pytest.approx(1.0) and np.all(t[[5, 7]] < 1)


def test_v4_v7_ozet():
    o = D.v4_ozet([[0.5, np.nan], [0.2, 0.3]], [[0.4, 0.1], [0.2, 0.5]], [0.95, 0.8], kesisim=[100, 98])
    assert o["ortalama_fark"] == pytest.approx([0.05, 0.2]) and o["tau_ort"] == pytest.approx(0.875) and o["K4_tetiklendi"]
    assert o["tau_ortanca"] == pytest.approx(0.875) and o["tau_y5"] == pytest.approx(0.8075) and o["tau_y95"] == pytest.approx(0.9425)
    assert o["kesisim"] == {"en_kucuk": 98, "ortanca": 99.0, "en_buyuk": 100}
    v = D.v7_ozet([0.9, 0.8, 1.0], [1, 0.5, 0.5])
    assert v["tau_ortanca"] == 0.9 and v["jaccard_ortanca"] == 0.5


def test_v10_yon():
    assert D.v10([1, 2, 3, 4], [0.9, 0.7, 0.5, 0.1]) == pytest.approx(1.0)


def test_tau_ortak_Q15():
    t, n = D.tau_ortak([1, 2, 3, 4], [0.9, 0.8, 0.7, 0.1], [4, 3, 2, 9], [0.0, 0.5, 0.6, 1.0])
    assert n == 3 and t == pytest.approx(1.0)        # ortak {2,3,4}: iki sıralama aynı
    t2, n2 = D.tau_ortak([1, 2, 3], [3, 2, 1.0], [1, 2, 3], [1, 2, 3.0])
    assert n2 == 3 and t2 == pytest.approx(-1.0)


def test_alt_tohum_V4_hedef_Q14():
    import ayar as A
    assert A.ayar("alt_tohum")["V4_hedef"] == 6
    ay4, _ = D.rastgele_hedefler(95000, 361000, "V4_hedef")
    ay5, _ = D.rastgele_hedefler(95000, 361000, "V5")
    assert len(set(ay4) & set(ay5)) < 10      # ayrı kümeler (rastlantısal ortak beklenen ≈ 0,1)

