# Developed with assistance from Claude (Anthropic).
"""kos.puanla ve dunya_uzakliklari: sentetik Dünya (gerçek veri yok) ile uçtan uca biçim ve kural denetimi."""
import types

import numpy as np
import pytest

import kos
import ozellik_topoloji as TP
import puan as Pn

RNG = np.random.default_rng(5)
nE = 3000


def _Q(n, kay=0.0):
    return np.sort(RNG.normal(kay, 1, (n, 1000)), axis=1).astype(np.float32)


def _sahte():
    D = types.SimpleNamespace()
    D.n = nE
    D.kim = np.arange(nE) * 3 + 7
    D.lat = RNG.uniform(-60, 70, nE); D.lon = RNG.uniform(-180, 180, nE)
    D.buz = RNG.random(nE); D.astro = RNG.random(nE) * 0.5; D.pv = RNG.random(nE); D.karbuz = RNG.random(nE) * 0.3
    D.z = RNG.normal(size=(nE, 6)); D.q3 = RNG.dirichlet(np.ones(6), nE)
    D.mob = RNG.random(nE); D.lnR = RNG.normal(5, 1, nE); D.R = np.exp(D.lnR)
    D.Om1 = RNG.random(nE) * 1e-3; D.Om4 = RNG.random(nE) * 1e-4
    D.dem_tam = np.ones(nE, bool); D.x4g = np.ones(nE)
    D.x4g[:30] = 0.2
    Q1 = np.stack([_Q(nE) for _ in range(6)], axis=1)
    arr = {"Q4": _Q(nE), "Q6": _Q(nE), "Q7": _Q(nE), "Q8": _Q(nE), "Q5_tgece": _Q(nE), "Q5_tmax": _Q(nE),
           "Q5_tort": _Q(nE), "Q5_iarti": _Q(nE)}
    arr["Q6"][100:400] = np.nan                       # buz tabakası benzeri
    D.Q = lambda ad: arr[ad]
    D.Q1 = lambda idx: Q1[np.asarray(idx, int)]
    D.konum = {int(k): i for i, k in enumerate(D.kim)}
    return D


def _hedef(islak=True):
    x = np.arange(40) * 500.0
    h = 200 * np.sin(x[None, :] / 3000) * np.cos(x[:, None] / 2500)
    return {"kimlik": "T", "ad": "T", "govde": "ay", "enlem": -86.0, "boylam": 0.0, "kaynak": "", "iqr": np.full(6, 0.5),
            "dg": TP.diyagramlar(h, "ay", yontem="union_find"), "pi_arti": 0.8 if islak else 0.1, "islak": islak,
            "F5": ["tmax", "tort", "tgece"], "Q1": np.stack([_Q(1)[0] for _ in range(6)]), "lnR": 5.0, "R": 150.0,
            "Omega_1": 1e-3, "Omega_4": 1e-4, "q3": np.array([0.7, 0.3, 0, 0, 0, 0]), "Q4": _Q(1)[0], "x4_gecerli": 1.0,
            "Q5_tmax": _Q(1)[0], "Q5_tort": _Q(1)[0], "Q5_tgece": _Q(1)[0], "Q6": _Q(1)[0], "Q7": _Q(1)[0], "Q8": _Q(1)[0],
            "z": RNG.normal(size=6)}


@pytest.fixture(scope="module")
def ortam(monkeypatch_module=None):
    D = _sahte()
    import onele
    x = np.arange(40) * 500.0
    diy = [TP.diyagramlar(150 * np.sin(x[None, :] / (2000 + 10 * i)) * np.cos(x[:, None] / 2600), "dunya", yontem="union_find")
           for i in range(200)]
    f = lambda i: diy[(int(i) * 7919) % 200]          # pencere → diyagram (deterministik; ref ile aday aynı)
    kos.dunya_diyagram = lambda D_, idx: [f(i) for i in idx]
    R = RNG.permutation(nE)
    return D, onele.Olcek(D.z), R[:2000], R[:200], [f(i) for i in R[:200]]


def test_uzaklik_ve_puanla(ortam):
    D, ol, R1, R28, diy = ortam
    hz = [_hedef(True), _hedef(False)]
    Dk, eK = kos.dunya_uzakliklari(D, hz, parca=700)
    assert Dk[3].shape == (nE, 2) and np.isnan(Dk[4][:30]).all() and np.isnan(Dk[6][100:400]).all()
    assert np.isnan(Dk[6][:, 1]).all()                      # kuru hedefte su/buz null
    assert not eK[100:400, 5].any() and eK[400:, 5].all() and not eK[:30, 3].any()
    for g in kos.GOREVLER:
        o = kos.puanla(D, hz[0], Dk, eK, 0, ol, R1, R28, diy, g, 200, 0.1, [("a1", 40.0, 30.0)])
        assert o["durum"] == "computed" and len(o["ilk10"]) == 10
        P = [r["P"] for r in o["ilk10"]]
        lat = np.array([r["enlem"] for r in o["ilk10"]]); lon = np.array([r["boylam"] for r in o["ilk10"]])
        for i in range(10):
            for j in range(i):
                assert Pn.gc_km(lat[i], lon[i], lat[j], lon[j]) >= 100 - 1e-6   # Q-12
        for r in o["ilk10"]:
            assert len(r["s"]) == 8 and r["s"][1] is not None and r["en_yakin_analog"]["id"] == "a1"
            assert all((s is None) == (e is not None) for s, e in zip(r["s"], r["eksik_taraf"]))
            assert r["eps1_durum"] in ("bulundu", "hassasiyetten küçük", "eşit uzaklık var (ε* = 0)", "bulunamadı")
        assert len(o["sampiyonlar"]) == 8 and set(o["duyarlilik"]) == {"esit", "geometrik"}
    o = kos.puanla(D, hz[1], Dk, eK, 1, ol, R1, R28, diy, "ice", 200, 0.1, [])
    assert o["durum"] == "not applicable"
    o = kos.puanla(D, hz[1], Dk, eK, 1, ol, R1, R28, diy, "genel", 200, 0.1, [])
    assert all(r["s"][5] is None and r["eksik_taraf"][5] in ("hedef", "iki_taraf") for r in o["ilk10"])


def test_puanla_tam_mod(ortam):
    """MD 81: Kön = None → kapıdan geçen bütün E′ aday; d1t verilince sonuç d1t'siz hesapla aynı."""
    import ozellik_topo as T
    D, ol, R1, R28, diy = ortam
    hz = _hedef(True)
    Dk, eK = kos.dunya_uzakliklari(D, [hz], parca=700)
    d1t = T.d1(D.Q1(np.arange(nE)), D.lnR, hz["Q1"], hz["lnR"], hz["iqr"])
    for g in ("genel", "mobility", "astro"):
        a = kos.puanla(D, hz, Dk, eK, 0, ol, R1, R28, diy, g, None, 0.1, [])
        b = kos.puanla(D, hz, Dk, eK, 0, ol, R1, R28, diy, g, None, 0.1, [], d1t=d1t)
        G = kos.kapilar(D, g, hz, 0.1)[0]
        assert a["aday"] == int(G.sum()) == b["aday"]
        assert [r["kimlik"] for r in a["ilk10"]] == [r["kimlik"] for r in b["ilk10"]]
        assert np.allclose([r["P"] for r in a["ilk10"]], [r["P"] for r in b["ilk10"]])
        # tam modun ilk P'si, aynı kapıyla ön elemeli (Kön = 200) sonucun ilk P'sinden küçük olamaz (topolojisiz ilk 30 farkı hariç)
        c = kos.puanla(D, hz, Dk, eK, 0, ol, R1, R28, diy, g, 200, 0.1, [])
        assert a["aday"] >= c["aday"]
