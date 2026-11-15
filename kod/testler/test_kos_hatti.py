# Developed with assistance from Claude (Anthropic).
"""kos.py hattı: blok deposu (kaldığı yerden devam, K16), şema denetimi, ızgara sayıları."""
import numpy as np
from pathlib import Path
import pytest

import izgara as Z
import kos


def _f(a, z):
    i = np.arange(a, z)
    return {"x": (i * 2.0).astype(np.float32), "Q": np.tile(i[:, None], (1, 3)).astype(np.float32), "b": (i % 2).astype(np.uint8)}


def test_depo_tam_kosu(tmp_path):
    d = kos.Depo(tmp_path / "d", 1000, blok=128)
    kos.bloklari_kos(d, _f, "test")
    assert d.tamam() and d.nb == 8
    np.testing.assert_array_equal(d.oku("x"), np.arange(1000) * 2.0)
    np.testing.assert_array_equal(d.oku("Q")[:, 1], np.arange(1000))


def test_depo_kesilip_devam_K16(tmp_path):
    sayac = {"n": 0}

    def kirik(a, z):
        sayac["n"] += 1
        if sayac["n"] == 4:
            raise KeyboardInterrupt("elektrik gitti")
        return _f(a, z)

    d = kos.Depo(tmp_path / "d", 1000, blok=128)
    with pytest.raises(KeyboardInterrupt):
        kos.bloklari_kos(d, kirik, "test")
    assert d.bitti.sum() == 3 and not d.tamam()
    cagri = []
    d2 = kos.Depo(tmp_path / "d", 1000, blok=128)          # yeniden başlat
    kos.bloklari_kos(d2, lambda a, z: (cagri.append(a), _f(a, z))[1], "test")
    assert cagri == [384, 512, 640, 768, 896]                # bitmiş 3 blok atlandı
    np.testing.assert_array_equal(d2.oku("x"), np.arange(1000) * 2.0)
    np.testing.assert_array_equal(d2.oku("b"), np.arange(1000) % 2)


def test_depo_sema_ve_boyut(tmp_path):
    d = kos.Depo(tmp_path / "d", 300, blok=100)
    d.yaz(0, _f(0, 100))
    with pytest.raises(AssertionError):
        d.yaz(1, {"x": np.zeros(100, np.float32)})          # eksik alan
    with pytest.raises(AssertionError):
        kos.Depo(tmp_path / "d", 301, blok=100)             # başka pencere sayısı
    yeni = kos.Depo(tmp_path / "d", 300, blok=100)
    assert np.isnan(yeni.oku("x")[150])                      # yazılmamış blok NaN, 0 değil


def test_izgara_sayilari():
    # belge 4.2: Ay ≈ 95 bin, Mars ≈ 361 bin (kesin sayılar ozet.json'a)
    assert Z.Halka("ay").n == 94864 and Z.Halka("mars").n == 360654 and Z.Halka("dunya").n == 1275482


def test_depo_iki_isci(tmp_path):
    # paralel koşu: ana süreç ilk bloğu yazar (şema), iki işçi b mod 2 bloklarını ayrı süreçte yapar; sonuç tek süreçliyle aynı
    import subprocess, sys, textwrap
    yol = tmp_path / "d"
    d = kos.Depo(yol, 1000, blok=100)
    d.yaz(0, _f(0, 100))
    kod = textwrap.dedent(f"""
        import sys; sys.path.insert(0, r"{Path(kos.__file__).parent}"); sys.path.insert(0, r"{Path(__file__).parent}")
        import numpy as np, kos
        from test_kos_hatti import _f
        no = int(sys.argv[1])
        d = kos.Depo(r"{yol}", 1000, blok=100, isci=no)
        kos.bloklari_kos(d, _f, "isci", isci_no=no, isci_sayi=2)
    """)
    ps = [subprocess.Popen([sys.executable, "-c", kod, str(i)]) for i in range(2)]
    assert all(p.wait() == 0 for p in ps)
    son = kos.Depo(yol, 1000, blok=100)
    assert son.tamam() and len(list(yol.glob("bitti*.npy"))) == 3
    np.testing.assert_array_equal(son.oku("x"), np.arange(1000) * 2.0)
    np.testing.assert_array_equal(son.oku("Q")[:, 2], np.arange(1000))


def test_diyagram_deposu(tmp_path, monkeypatch):
    import ozellik_topoloji as TP
    monkeypatch.setattr(kos, "DIY_KL", tmp_path)
    rng = np.random.default_rng(3)
    x = np.arange(40) * 500.0
    dg = [TP.diyagramlar(200 * np.sin(x[None, :] / rng.uniform(1500, 4000)) * np.cos(x[:, None] / 3000), "dunya",
                         yontem="union_find") for _ in range(5)] + [None]
    z = np.array([TP.n_onemli(d, "dunya") if d is not None else (0, 0) for d in dg], float)
    kos._diy_blok_yaz(0, dg, z)
    D = kos.DiyagramDeposu(blok=6)
    for i, d in enumerate(dg):
        if d is None:
            assert D[i] is None
        else:
            g = D[i]
            np.testing.assert_array_equal(g[0], d[0]); np.testing.assert_array_equal(g[1], d[1]); assert g[2] == d[2]
    z[1, 0] += 1
    with pytest.raises(AssertionError):
        kos._diy_blok_yaz(1, dg, z)                     # P3 sayılarıyla tutmayan diyagram yazılmaz
