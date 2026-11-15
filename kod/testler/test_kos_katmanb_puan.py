# Developed with assistance from Claude (Anthropic).
"""Katman B puanlama (KatmanB.hedef): seyrek uzaklık hesabı tam hesapla aynı; referans 3–7 = sabit 2000 (belge 3.2);
kuru hedefte Ice 'not applicable'; eksik taraf kodları; Katman A'nın puanla'sı değişmedi (aynı ortak fonksiyonlar)."""
import numpy as np
import pytest

import kos
import ozellik_topo as T
import ozellik_topoloji as TP
import puan as Pn
from test_kos_puanla import _hedef, _sahte, nE


@pytest.fixture(scope="module")
def ortam():
    D = _sahte()
    x = np.arange(40) * 500.0
    diy = [TP.diyagramlar(150 * np.sin(x[None, :] / (2000 + 10 * i)) * np.cos(x[:, None] / 2600), "dunya", yontem="union_find")
           for i in range(200)]
    f = lambda i: diy[(int(i) * 7919) % 200]
    kos.dunya_diyagram = lambda D_, idx: [f(i) for i in idx]
    R = np.random.default_rng(11).permutation(nE)
    R1, R28, RB = R[:2000], R[:200], np.random.default_rng(12).permutation(nE)[:2000]
    mp = pytest.MonkeyPatch()
    mp.setattr(kos, "referans_kumeleri", lambda n: (R1, R28))
    mp.setattr(kos, "referans_B", lambda n: RB)
    mp.setattr(kos, "ref_diyagramlari", lambda D_, R: [f(i) for i in R])
    kb = kos.KatmanB(D, 200, 0.1, f32=False)
    kb32 = kos.KatmanB(D, 200, 0.1)
    yield D, kb, R1, R28, RB, [f(i) for i in R28], kb32
    mp.undo()


def _beklenen(D, hz, g, kb, R1, R28, RB, diy28):
    """Tam (bütün E′) uzaklıklarla aynı akış: Katman B'nin seyrek hesabı bununla birebir aynı olmalı."""
    Dk, _ = kos.dunya_uzakliklari(D, [hz], parca=900)
    KT = kos.hedef_kategorileri(hz)
    q3 = np.asarray(hz["q3"], float)
    key = "geology%d" % int(np.nanargmax(q3)) if g == "geology" else g
    idx = np.asarray(kb.agac[key].sorgu(hz["z"], 200)[0])
    d1 = T.d1(D.Q1(np.arange(nE)), D.lnR, hz["Q1"], hz["lnR"], hz["iqr"])
    S, Zt, Dm, uyg = kos.skor_topolojisiz(D, Dk, 0, idx, d1[idx], d1[R1], R1, R28, KT, R37=RB)
    P, Q, ilk30, yeni, _ = kos.topoloji_ve_sira(D, hz, idx, S, Zt, Dm, uyg, Pn.gorev_agirligi(g), R28, diy28)
    t3 = Pn.aralikli_liste(yeni, D.lat[idx], D.lon[idx], 3, gecer=uyg)
    return idx[t3], P[t3], S[t3]


def test_seyrek_tam_ile_ayni(ortam):
    D, kb, R1, R28, RB, diy28, _ = ortam
    hz = _hedef(True)
    o = kb.hedef(hz)
    for gi, g in enumerate(kos.GOREVLER):
        top, P, S = _beklenen(D, hz, g, kb, R1, R28, RB, diy28)
        assert np.array_equal(o["top3"][gi], top), g
        assert np.allclose(o["P"][gi], P, rtol=1e-6) and np.allclose(o["s"][gi], S, rtol=1e-6, equal_nan=True), g
        assert (o["durum"][gi] == 0) and 0 < o["aday"][gi] <= 200
        for q in range(3):
            assert all((o["eksik"][gi, q, k] == 0) == np.isfinite(o["s"][gi, q, k]) for k in range(8))


def test_referans_37_sabit_2000(ortam):
    """Kategori 3–7 s_k'si RB'ye göre: tam E′ referansıyla (Katman A) farklı olabilir, RB ile elle hesap aynı."""
    D, kb, R1, R28, RB, diy28, _ = ortam
    hz = _hedef(True)
    o = kb.hedef(hz)
    Dk, _ = kos.dunya_uzakliklari(D, [hz], parca=900)
    e = int(o["top3"][0, 0])
    for k in (3, 4, 5, 7):
        d = Dk[k][:, 0]
        assert o["s"][0, 0, k - 1] == pytest.approx(float(Pn.s_k(d[[e]], d[RB], kos._konum(nE, RB)[[e]])[0]))


def test_kuru_hedef(ortam):
    D, kb, *_ = ortam
    hz = _hedef(False)
    o = kb.hedef(hz)
    gi = kos.GOREVLER.index("ice")
    assert o["durum"][gi] == 1 and (o["top3"][gi] == -1).all()
    gg = kos.GOREVLER.index("genel")
    assert (o["eksik"][gg, :, 5] > 0).all() and np.isnan(o["s"][gg, :, 5]).all()   # su/buz: hedef tarafı
    assert set(o["eksik"][gg, :, 5]) <= {1, 3}


def test_f32_harita(ortam):
    """MD 84: harita 32 bit — 64 bit hesapla Top-3 aynı, s farkı < 1e-5; ardışık hedeflerde dizi sıfırlama doğru."""
    D, kb, R1, R28, RB, diy28, kb32 = ortam
    ayni, toplam, en_buyuk = 0, 0, 0.0
    for islak in (True, False, True):
        hz = _hedef(islak)
        a, b = kb.hedef(hz), kb32.hedef(hz)
        ayni += int((a["top3"] == b["top3"]).sum()); toplam += a["top3"].size
        m = np.isfinite(a["s"])
        assert np.array_equal(m, np.isfinite(b["s"]))
        en_buyuk = max(en_buyuk, float(np.max(np.abs(a["s"][m] - b["s"][m]))))
        assert np.array_equal(a["eksik"], b["eksik"]) and np.array_equal(a["durum"], b["durum"])
    assert ayni == toplam and en_buyuk < 1e-5, (ayni, toplam, en_buyuk)
    # aynı hedef iki kez: sonuç aynı (önceki hedeften kalan değer yok)
    hz = _hedef(True)
    x, y = kb32.hedef(hz), kb32.hedef(hz)
    assert np.array_equal(x["top3"], y["top3"]) and np.allclose(x["s"], y["s"], equal_nan=True)
