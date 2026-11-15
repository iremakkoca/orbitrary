# Developed with assistance from Claude (Anthropic).
"""Belge 8.2 'Görev ağırlığı' testi + ayar.json bütünlük testleri."""
import numpy as np
import pytest
import ayar as A

# Belge 7.3 tablosu, belgeden aynen (k = 1..8)
TABLO_7_3 = {
    "genel":    [.125] * 8,
    "mobility": [.267, .267, .04, .04, .04, .04, .267, .04],
    "geology":  [.04, .267, .267, .267, .04, .04, .04, .04],
    "ice":      [.04, .04, .04, .04, .267, .267, .04, .267],
    "astro":    [.04, .04, .04, .267, .267, .267, .04, .04],
}


def test_klasorler_var():
    for ad, yol in A.KLASOR.items():
        assert yol.is_dir(), ad


def test_her_parametrede_kaynak():
    n = 0
    for anahtar, y in A.yapraklar():
        assert isinstance(y["kaynak"], str) and y["kaynak"].strip(), anahtar
        if y["deger"] is None:
            assert y.get("durum"), anahtar
        n += 1
    assert n >= 60


def test_belirlenmemis_deger_okunamaz():
    for anahtar in ("onele.K_on", "kapi.jeoloji.X"):
        with pytest.raises(ValueError):
            A.ayar(anahtar)


def test_gorev_agirligi_8_2():
    # m = 3, n = 8: 0,2667 × 3 + 0,04 × 5 = 1
    for g in ("mobility", "geology", "ice", "astro"):
        w = A.agirliklar(g)
        ana = np.isin(np.arange(1, 9), A.ayar("agirlik.ana_kategoriler")[g])
        assert ana.sum() == 3
        assert np.allclose(w[ana], 0.80 / 3) and round(w[ana][0], 4) == 0.2667
        assert np.allclose(w[~ana], 0.04)
        assert abs(w.sum() - 1) < 1e-12


def test_tablo_7_3_formulle_ayni():
    for g, beklenen in TABLO_7_3.items():
        assert np.array_equal(np.round(A.agirliklar(g), 3), np.array(beklenen)), g


def test_esit_sema():
    for g in A.GOREVLER:
        assert np.allclose(A.agirliklar(g, "esit"), 0.125)


def test_tohum_ve_tekrar():
    assert A.TOHUM == 20261113
    assert np.array_equal(A.rng().random(5), np.random.default_rng(20261113).random(5))
    assert np.array_equal(A.rng(5).random(5), A.rng(5).random(5))
    assert not np.array_equal(A.rng(2).random(5), A.rng(3).random(5))


def test_sabitler_4_1():
    assert A.ayar("cisim.yaricap_km") == {"dunya": 6371.0, "ay": 1737.4, "mars": 3389.5}
    assert A.ayar("cisim.eksen_egikligi_der") == {"dunya": 23.44, "ay": 1.54, "mars": 25.19}
    assert A.ayar("cisim.sigma_v_m") == {"dunya": 7.17, "ay": 10.0, "mars": 1.0}
    assert A.ayar("izgara.N") * A.ayar("izgara.delta_m") == A.ayar("izgara.L_km") * 1000


def test_analog_uzaklik_v121():
    d = A.ayar("analog_uzaklik_km")
    assert d["bilinen_alti"] == 20.0 and d["yakin_ust"] == 100.0
