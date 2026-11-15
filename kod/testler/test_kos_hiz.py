# Developed with assistance from Claude (Anthropic).
"""Katman B hızlandırmaları sonucu değiştirmez: d1_hizli = T.d1 (bayt bayt), tek dosyalı diyagram deposu = blok deposu,
sw önbelleği aynı sayı."""
import numpy as np

import kos
import ozellik_topo as T
import ozellik_topoloji as TP


def test_d1_hizli_birebir():
    rng = np.random.default_rng(3)
    Q = np.sort(rng.normal(size=(700, 6, 1000)), axis=2).astype(np.float32)
    QT = np.sort(rng.normal(size=(6, 1000)), axis=1).astype(np.float32)
    lnR = rng.normal(5, 1, 700)
    for iqr in (np.array([0.5, 0.2, 0.0, 1.3, np.nan, 2.0]), np.full(6, 0.7)):
        assert np.array_equal(kos.d1_hizli(Q, lnR, QT, 4.9, iqr), T.d1(Q, lnR, QT, 4.9, iqr))
        Q64 = Q.astype(float)
        assert np.array_equal(kos.d1_hizli(Q64, lnR, QT, 4.9, iqr), T.d1(Q64, lnR, QT, 4.9, iqr))


def test_diyagram_tek_ayni(tmp_path, monkeypatch):
    x = np.arange(40) * 500.0
    n = 2 * kos.BLOK + 9
    dg = [None if i % 37 == 0 else TP.diyagramlar(150 * np.sin(x[None, :] / (2000 + i)) * np.cos(x[:, None] / 2600), "dunya",
                                                  yontem="union_find") for i in range(n)]
    z = np.array([[0, 0] if d is None else TP.n_onemli(d, "dunya") for d in dg])
    kl = tmp_path / "blok"; kl.mkdir()
    for b in range(3):
        a, e = b * kos.BLOK, min(n, (b + 1) * kos.BLOK)
        kos._diy_blok_yaz(b, dg[a:e], z[a:e], kl=kl)
    kos.diyagram_tek(kl, tmp_path / "tek", n)
    t = kos.DiyagramTek(tmp_path / "tek")
    for i in range(n):
        assert (t[i] is None) == (dg[i] is None)
        if dg[i] is not None:
            assert np.array_equal(t[i][0], dg[i][0]) and np.array_equal(t[i][1], dg[i][1]) and t[i][2] == dg[i][2]
            assert TP.d2(t[i], dg[0 if i else 1] or dg[1]) == TP.d2(dg[i], dg[0 if i else 1] or dg[1])


def test_sw_onbellek_ayni():
    rng = np.random.default_rng(4)
    a, b = rng.random((30, 2)), rng.random((45, 2))
    E = TP._yonler_hesap(int(TP.A.ayar("uzaklik.M_theta")))
    assert TP.sw(a, b) == TP.sw(a, b, yonler=E) == TP.sw(a, b)
