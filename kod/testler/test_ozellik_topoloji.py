# Developed with assistance from Claude (Anthropic).
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
