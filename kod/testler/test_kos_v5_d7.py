# Developed with assistance from Claude (Anthropic).
"""D7 (kimlik testi) ve V5 (ön elemenin kaybı) mantığı: sentetik Dünya ile (gerçek veri yok)."""
import numpy as np
import pytest

import kos
import onele
import ozellik_topo as T
import ozellik_topoloji as TP
from test_kos_puanla import RNG, _hedef, _sahte, nE


@pytest.fixture(scope="module")
def ortam():
    D = _sahte()
    x = np.arange(40) * 500.0
    diy = [TP.diyagramlar(150 * np.sin(x[None, :] / (2000 + 10 * i)) * np.cos(x[:, None] / 2600), "dunya", yontem="union_find")
           for i in range(200)]
    f = lambda i: diy[(int(i) * 7919) % 200]
    kos.dunya_diyagram = lambda D_, idx: [f(i) for i in idx]
    R = np.random.default_rng(9).permutation(nE)
    return D, onele.Olcek(D.z), R[:2000], R[:200], [f(i) for i in R[:200]], f


def test_skor_aday_kumesinden_bagimsiz(ortam):
    """Q-5 dayanağı: bir pencerenin s_k, ζ_k, uygunluğu aday kümesine bağlı değil (V5 tam sıralama = Katman A puanı)."""
    D, ol, R1, R28, diy, f = ortam
    hz = _hedef(True)
    Dk, _ = kos.dunya_uzakliklari(D, [hz], parca=700)
    KT = kos.hedef_kategorileri(hz)
    d1t = kos.d1_tum(D, [hz], parca=333)[:, 0]
    assert np.allclose(d1t, T.d1(D.Q1(np.arange(nE)), D.lnR, hz["Q1"], hz["lnR"], hz["iqr"]))
    St, Zt, Dt, ut = kos.skor_topolojisiz(D, Dk, 0, np.arange(nE), d1t, d1t[R1], R1, R28, KT)
    idx = np.sort(RNG.choice(nE, 300, replace=False))
    d1c = T.d1(D.Q1(idx), D.lnR[idx], hz["Q1"], hz["lnR"], hz["iqr"])
    d1r = T.d1(D.Q1(R1), D.lnR[R1], hz["Q1"], hz["lnR"], hz["iqr"])
    Sa, Za, Da, ua = kos.skor_topolojisiz(D, Dk, 0, idx, d1c, d1r, R1, R28, KT)
    assert np.allclose(St[idx], Sa, equal_nan=True, rtol=0, atol=1e-12)
    assert np.allclose(Zt[idx], Za, equal_nan=True, rtol=0, atol=1e-12)
    assert np.array_equal(ut[idx], ua) and np.isnan(St[:, 1]).all()


def test_v5_recall(ortam):
    D, ol, R1, R28, diy, f = ortam
    hz = [_hedef(True), _hedef(False)]
    Dk, _ = kos.dunya_uzakliklari(D, hz, parca=700)
    d1t = kos.d1_tum(D, hz)
    agac = onele.Agac(ol, D.z, None, kimlik=D.kim)
    Klar = (100, 200, 400, 800, nE)
    for j in range(2):
        r = kos.v5_hedef(D, hz[j], Dk, j, d1t[:, j], R1, R28, agac, Klar)
        rc = [r["recall"][str(K)] for K in Klar]
        assert all(0 <= x <= 1 for x in rc) and all(a <= b for a, b in zip(rc, rc[1:]))   # E_K iç içe → artan
        assert rc[-1] == 1.0                                                            # E_K = E′ → recall 1
        assert len(set(r["top3"])) == 3 and r["top3_P"] == sorted(r["top3_P"], reverse=True)
        # Top-3 elle: bütün E′ üzerinde P₀ en büyük (100 km kuralıyla)
        import puan as Pn
        KT = kos.hedef_kategorileri(hz[j])
        S, Z_, _, u = kos.skor_topolojisiz(D, Dk, j, np.arange(nE), d1t[:, j], d1t[R1, j], R1, R28, KT)
        P0, _ = Pn.P_Q(S, Z_, Pn.gorev_agirligi("genel"), u)
        assert r["top3_P"][0] == pytest.approx(np.nanmax(P0))


def test_d7_kimlik(ortam):
    """Hedef = sentetik Dünya penceresi e: e ilk sırada, d_k(e,T) = 0, s_k belge 5.4 tanımıyla (½ eşitlik dahil)."""
    D, ol, R1, R28, diy, f = ortam
    for e in (1234, 2500):
        hz = {"kimlik": "D7", "ad": f"w{e}", "govde": "dunya", "enlem": float(D.lat[e]), "boylam": float(D.lon[e]),
              "kaynak": "", "iqr": np.full(6, 0.5), "dg": f(e), "pi_arti": np.nan, "islak": False,
              "F5": ["tmax", "tort", "tgece", "iarti"], "Q1": D.Q1([e])[0], "lnR": float(D.lnR[e]), "R": float(D.R[e]),
              "Omega_1": float(D.Om1[e]), "Omega_4": float(D.Om4[e]), "q3": D.q3[e], "Q4": D.Q("Q4")[e],
              "x4_gecerli": float(D.x4g[e]), "Q6": D.Q("Q6")[e], "Q7": D.Q("Q7")[e], "Q8": D.Q("Q8")[e], "z": D.z[e]}
        for x in hz["F5"]:
            hz[f"Q5_{x}"] = D.Q(f"Q5_{x}")[e]
        Dk, eK = kos.dunya_uzakliklari(D, [hz], parca=700)
        o = kos.puanla(D, hz, Dk, eK, 0, ol, R1, R28, diy, "genel", 200, 0.0, [])
        g, ay = kos.d7_kontrol(D, hz, e, o, Dk, 0, R1, R28, diy)
        assert g and ay["ilk"], ay
        kat = {x["k"]: x for x in ay["kategoriler"]}
        assert kat[6]["durum"].startswith("hedefte yok")                   # kuru hedef: su/buz null (belge 6.6)
        assert all(kat[k]["d_e"] == 0 for k in (1, 3, 4, 5, 7, 8))
        assert kat[2]["esit_ref"] >= 0 and kat[1]["s_bir"]                  # sürekli dağılım: eşit referans yok → s = 1
    # bozuk durum: hedefin bir özelliği değişirse test FAIL vermeli
    e = 1234
    hz["Q4"] = D.Q("Q4")[e] + 0.5
    hz["kimlik"] = "D7b"
    Dk, eK = kos.dunya_uzakliklari(D, [hz], parca=700)
    o = kos.puanla(D, hz, Dk, eK, 0, ol, R1, R28, diy, "genel", 200, 0.0, [])
    g, ay = kos.d7_kontrol(D, hz, 2500, o, Dk, 0, R1, R28, diy)
    assert not g


def test_kayip_hedef(ortam):
    """Kön = bütün E′ → fark 0, Π_ön = 1; Kön küçükse fark ≥ 0 ve Π_ön ≤ 1; kuru hedefte Ice yok."""
    D, ol, R1, R28, diy, f = ortam
    G = kos.kapi_dizileri(D, 0.1)
    ag = {k: onele.Agac(ol, D.z, g, kimlik=D.kim) for k, g in G.items()}
    hz = [_hedef(True), _hedef(False)]
    Dk, _ = kos.dunya_uzakliklari(D, hz, parca=700)
    d1t = kos.d1_tum(D, hz)
    tam = kos.kayip_hedef(D, hz[0], Dk, 0, d1t[:, 0], R1, R28, G, ag, nE)
    assert all(v["fark"] == 0 and v["Pi_on"] == 1.0 for v in tam.values())
    kuc = kos.kayip_hedef(D, hz[0], Dk, 0, d1t[:, 0], R1, R28, G, ag, 50)
    assert all(v["fark"] >= 0 and 0 < v["Pi_on"] <= 1 for v in kuc.values())
    assert kos.kayip_hedef(D, hz[1], Dk, 1, d1t[:, 1], R1, R28, G, ag, 50)["ice"] is None
