# Developed with assistance from Claude (Anthropic).
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
