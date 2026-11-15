# Developed with assistance from Claude (Anthropic).
"""Belge 8.1: Lemma 1 (a)–(e), Lemma 2 (Ψ₁, Ψ₂), Teorem 1 ve ε*, hareket kapısı — rastgele DEM + |e| ≤ ε gürültüsüyle
sınırların gerçekten tuttuğu ölçülür (her test birçok tekrar)."""
import math
import numpy as np
import pytest
import ayar as A
import ozellik_topo as T
import ozellik_topoloji as P
import teorem as TH
import uzaklik as U

n = 56
x = (np.arange(n) - n / 2 + 0.5)[None, :] * 500.0
y = (np.arange(n) - n / 2 + 0.5)[:, None] * 500.0


def _dem(g, olcek=300.0):
    # düzgün + pürüzlü arazi
    h = olcek * (np.sin(x / 4000 + g.uniform(0, 6)) * np.cos(y / 5000 + g.uniform(0, 6)))
    return h + g.normal(0, olcek / 10, (n, n))


def test_ornek_buyukluk_8_1():
    # δ = 500 m, ε = σv = 7,17 m → Λ = √2·7,17/500 ≈ 0,0203 rad ≈ 1,16°
    L = math.sqrt(2) / TH.delta_s(1) * 7.17
    assert abs(L - 0.0203) < 5e-5 and abs(math.degrees(L) - 1.16) < 5e-3


@pytest.mark.parametrize("tohum", range(10))
def test_lemma1_hucre_sinirlari(tohum):
    g = np.random.default_rng(tohum)
    eps = 7.17
    h = _dem(g)
    e = g.uniform(-eps, eps, (n, n))
    o, ot = T.ozellikler(h, "dunya"), T.ozellikler(h + e, "dunya")
    for s, tag in ((1, "_1"), (4, "_4")):
        L = TH.lambdalar(o["Omega" + tag], s, eps)
        assert np.max(np.abs(ot["theta" + tag] - o["theta" + tag])) <= L["theta"] * eps + 1e-12      # (a)
        assert np.max(np.abs(ot["vrm" + tag] - o["vrm" + tag])) <= L["vrm"] * eps + 1e-12            # (b)
        assert np.max(np.abs(ot["H" + tag] - o["H" + tag])) <= L["H"] * eps + 1e-12                  # (c)
    assert abs(ot["lnR"] - o["lnR"]) <= 2 * eps / TH.ell(o["R"], "dunya", eps) + 1e-12                 # (d)
    W = (Ellipsis, slice(T.GEN, -T.GEN), slice(T.GEN, -T.GEN))
    a, b = P.normalize(h[W], "dunya"), P.normalize((h + e)[W], "dunya")
    assert np.max(np.abs(a[0] - b[0])) <= 4 * eps / TH.ell_top(o["R"], "dunya", eps) + 1e-12            # (e)


@pytest.mark.parametrize("tohum", range(10))
def test_lemma2_psi1(tohum):
    # |d̃₁(A,B) − d₁(A,B)| ≤ Ψ₁(A,B;ε); IQR_T, F_T sabit (V2)
    g = np.random.default_rng(100 + tohum)
    eps = 7.17
    hA, hB = _dem(g), _dem(g, 150.0)
    oA, oB = T.ozellikler(hA, "dunya"), T.ozellikler(hB, "dunya")
    tA = T.ozellikler(hA + g.uniform(-eps, eps, (n, n)), "dunya")
    tB = T.ozellikler(hB + g.uniform(-eps, eps, (n, n)), "dunya")
    iqr = T.iqr_hedef([T.ozellikler(_dem(g), "dunya") for _ in range(21)])
    Q = lambda o: T.yuzdelik_vektorleri(o)
    d = T.d1(Q(oA)[None], np.array([oA["lnR"]]), Q(oB), oB["lnR"], iqr)[0]
    dt = T.d1(Q(tA)[None], np.array([tA["lnR"]]), Q(tB), tB["lnR"], iqr)[0]
    psi = TH.psi1(eps, "dunya", oA, oB, iqr)
    assert abs(dt - d) <= psi + 1e-12, (abs(dt - d), psi)


@pytest.mark.parametrize("tohum", range(5))
def test_lemma2_psi2(tohum):
    g = np.random.default_rng(200 + tohum)
    eps = 7.17
    W = (Ellipsis, slice(T.GEN, -T.GEN), slice(T.GEN, -T.GEN))
    hA, hB = _dem(g)[W], _dem(g, 150.0)[W]
    dA, dB = P.diyagramlar(hA, "dunya", "uf"), P.diyagramlar(hB, "dunya", "uf")
    dAt = P.diyagramlar(hA + g.uniform(-eps, eps, hA.shape), "dunya", "uf")
    dBt = P.diyagramlar(hB + g.uniform(-eps, eps, hB.shape), "dunya", "uf")
    RA, RB = max(np.ptp(hA), 7.17), max(np.ptp(hB), 7.17)
    assert abs(P.d2(dAt, dBt) - P.d2(dA, dB)) <= TH.psi2(eps, "dunya", RA, RB)


def test_psi_artan_ve_sifirda_sifir():
    o = {"R": 300.0, "Omega_1": 1e-3, "Omega_4": 1e-4}
    iqr = np.ones(6) * 0.1
    v = [TH.psi1(e, "ay", o, o, iqr) for e in (0.0, 1.0, 2.0, 5.0)]
    assert v[0] == 0 and all(np.diff(v) > 0)
    w = [TH.psi2(e, "ay", 300.0, 500.0) for e in (0.0, 1.0, 2.0)]
    assert w[0] == 0 and all(np.diff(w) > 0)


def test_eps_yildiz_bilinen():
    # Ψ(ε) = ε (iki tarafta), referans uzaklık farkları en az 3 → ε* = 1,5 (koşul |Δ| > 2ε)
    d_E, d_ref = 10.0, np.array([13.0, 6.0, 20.0])
    e, b = TH.eps_yildiz(d_E, d_ref, lambda e: e, lambda e: np.full(3, e), "dunya")
    assert b["durum"] == "bulundu" and abs(e - 1.5) <= TH.EPS_HASSASIYET_M
    e0, b0 = TH.eps_yildiz(10.0, np.array([10.0, 12.0]), lambda e: e, lambda e: np.full(2, e), "dunya")
    assert e0 == 0.0 and b0["durum"].startswith("eşit")
    # ε* = 0,0015 m < 0,01 m → "hassasiyetten küçük", değer 0, üst sınır ≤ 0,01 m
    ek, bk = TH.eps_yildiz(10.0, np.array([10.003]), lambda e: e, lambda e: np.full(1, e), "dunya")
    assert ek == 0.0 and bk["durum"] == "hassasiyetten küçük" and bk["ust_sinir_m"] <= 0.0115
    eN, bN = TH.eps_yildiz(10.0, np.array([1e9]), lambda e: 0.0 * e, lambda e: np.zeros(1), "dunya")
    assert eN is None and bN["durum"] == "bulunamadı"


@pytest.mark.parametrize("tohum", range(5))
def test_teorem1_s1_degismez(tohum):
    # ε*₁ altında gürültü s₁'i değiştirmez: E ve referansların d₁ sırası korunur
    g = np.random.default_rng(300 + tohum)
    oT = T.ozellikler(_dem(g), "dunya")
    iqr = T.iqr_hedef([oT] + [T.ozellikler(_dem(g), "dunya") for _ in range(20)])
    hs = [_dem(g, g.uniform(50, 600)) for _ in range(30)]
    os_ = [T.ozellikler(h, "dunya") for h in hs]
    Q = np.stack([T.yuzdelik_vektorleri(o) for o in os_])
    lnR = np.array([o["lnR"] for o in os_])
    d = T.d1(Q, lnR, T.yuzdelik_vektorleri(oT), oT["lnR"], iqr)
    refs = {k: np.array([o[k] for o in os_[1:]]) for k in ("R", "Omega_1", "Omega_4")}
    e_star, b = TH.eps1("dunya", os_[0], oT, refs, d[0], d[1:], iqr, hassasiyet=1e-7)
    assert b["durum"] == "bulundu" and e_star > 0, b
    eps = 0.9 * e_star
    ot = [T.ozellikler(h + g.uniform(-eps, eps, h.shape), "dunya") for h in hs]
    oTt = T.ozellikler(_dem(np.random.default_rng(300 + tohum)) + g.uniform(-eps, eps, (n, n)), "dunya")
    Qt = np.stack([T.yuzdelik_vektorleri(o) for o in ot])
    dt = T.d1(Qt, np.array([o["lnR"] for o in ot]), T.yuzdelik_vektorleri(oTt), oTt["lnR"], iqr)
    assert np.array_equal(np.sign(d[1:] - d[0]), np.sign(dt[1:] - dt[0]))


def test_hareket_kapisi_degismez():
    th = np.full((40, 40), np.radians(10.0)); th.ravel()[:81] = np.radians(25.0)   # açıkça kaldı
    assert TH.mobility_degismez(th, 7.17)
    th2 = np.full((40, 40), np.radians(10.0)); th2.ravel()[:81] = np.radians(20.3)  # 20° + Λ içinde
    assert not TH.mobility_degismez(th2, 7.17)
