# Developed with assistance from Claude (Anthropic).
"""Katman B hedef tarafı (P3B): ham topografya alanları (IQR_T için) ve diyagram dosyaları; sentetik DEM ile."""
import numpy as np

import kos
import ozellik_diger as OD
import ozellik_topo as T
import ozellik_topoloji as TP


def _dem(n, tohum=3):
    rng = np.random.default_rng(tohum)
    x = np.arange(56) * 500.0
    return np.stack([300 * np.sin(x[None, :] / (2500 + 97 * i)) * np.cos(x[:, None] / (3100 + 41 * i))
                     + rng.normal(0, 5, (56, 56)) for i in range(n)])


def _yamala(monkeypatch, h):
    monkeypatch.setattr(kos.K, "ac", lambda ad: ad)
    monkeypatch.setattr(kos.K, "hucreye", lambda kaynak, p, l, r, genisletme=0: (h[: len(p)], None, None))
    monkeypatch.setattr(OD, "pencere_temsili", lambda g, p, l: {"pi_arti": np.zeros(len(p))})
    monkeypatch.setattr(TP, "h0_gudhi", TP.h0_union_find)   # aynı sonuç (MAKALEYİ ETKİLER 5. bölüm); test GUDHI'siz de koşar


def test_p3_blok_ham_ve_diyagram(monkeypatch):
    n = 5
    h = _dem(n)
    _yamala(monkeypatch, h)
    dgl = []
    out = kos.p3_blok("ay", np.radians(np.linspace(-80, 80, n)), np.zeros(n), diy=dgl)
    oz = T.ozellikler(h, "ay")
    for f in T.OZELLIKLER:
        assert out[f"ham_{f}"].shape == (n, np.asarray(oz[f][0]).size)
        assert np.array_equal(out[f"ham_{f}"][2], np.asarray(oz[f][2], np.float32).ravel())
    assert len(dgl) == n
    assert all(TP.n_onemli(d, "ay") == tuple(int(v) for v in out["z"][i, 4:6]) for i, d in enumerate(dgl))
    # IQR_T ham alanlardan = belge 6.1'deki gibi pencere sözlüklerinden
    a = T.iqr_hedef([{f: out[f"ham_{f}"][i] for f in T.OZELLIKLER} for i in range(n)])
    b = T.iqr_hedef([{f: np.asarray(oz[f][i], np.float32) for f in T.OZELLIKLER} for i in range(n)])
    assert np.allclose(a, b)
    # Dünya bloğunda ham alan yok (Dünya kaydı değişmez)
    monkeypatch.setattr(kos, "kara_hucreleri", lambda p, l: np.ones((len(p), 40, 40)))
    import kapi
    monkeypatch.setattr(kapi, "degiskenler", lambda kara, egim_rad: {"mob": np.zeros(len(kara))})
    od = kos.p3_blok("dunya", np.zeros(2), np.zeros(2))
    assert not any(k.startswith("ham_") for k in od)


def test_p3b_fonk_diyagram_dosyasi(monkeypatch, tmp_path):
    n = 7
    h = _dem(n, 4)
    _yamala(monkeypatch, h)
    monkeypatch.setattr(kos, "ARA", tmp_path)
    (tmp_path / "diyagram_mars").mkdir()
    p, l = np.radians(np.linspace(-60, 60, n)), np.zeros(n)
    out = kos._p3b_fonk("mars", p, l)(0, n)
    dd = kos.DiyagramDeposu(kl=tmp_path / "diyagram_mars")
    W = h[:, T.GEN:-T.GEN, T.GEN:-T.GEN]
    for i in range(n):
        a, b = dd[i], TP.diyagramlar(W[i], "mars")
        assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]) and a[2] == b[2]
    assert out["ham_theta_1"].shape == (n, 1600)
