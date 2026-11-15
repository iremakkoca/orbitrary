# Developed with assistance from Claude (Anthropic).
"""Belge 8.2 (C₁, I⊕, su/buz sıfır kuralı, ıslak/kuru, aydınlanma, mineraloji) ve 6.3–6.8 sentetik pencere testleri."""
import datetime
import math
import numpy as np
import pandas as pd
import pytest
import ayar as A
import katman as K
import ozellik_diger as O
import uzaklik as U

r = math.radians


@pytest.mark.parametrize("phi,delta,beklenen", [(0, 0, math.pi / 2), (45, 20, 1.5165),
                                                (80, 20, math.pi * math.cos(r(80)) * math.cos(r(20))),
                                                (80, -20, 0.0), (69.99, 20, 1.0102), (70.01, 20, 1.0092)])
def test_C1_8_2(phi, delta, beklenen):
    assert abs(float(O.C1(r(phi), r(delta))) - beklenen) < 1e-4


def test_C1_kutup_gunu_degeri_8_2():
    assert abs(float(O.C1(r(80), r(20))) - 0.5126) < 1e-4


def test_I_arti_8_2():
    assert abs(float(O.I_arti_ay(1.0, 0.2, 10.0)) - 0.08) < 1e-15
    # kutup gecesi: C₁ = 0 olan ay ortalamaya girmez
    aylar = O.I_arti_ay(np.array([1.0, 0.0, 1.0]), np.array([0.2, 0.2, 0.2]), np.array([10.0, 10.0, 5.0]))
    assert np.isnan(aylar[1]) and abs(np.nanmean(aylar) - (0.08 + 0.16) / 2) < 1e-15
    assert np.isnan(O.I_arti_ay(1.0, 0.2, 0.0)) and np.isnan(O.I_arti_ay(1.0, 0.2, -3.0))


def test_su_buz_sifir_kurali_8_2():
    # haritada değeri olmayan kara hücresi: kar/buz 0,2 → x = 0; 0,7 → hesap dışı
    x = O.sifir_kurali(np.array([np.nan, np.nan, 0.6, np.nan]), np.array([0.2, 0.7, 0.1, 0.0]), np.array([1.0, 1.0, 1.0, 0.2]))
    assert x[0] == 0.0 and np.isnan(x[1]) and abs(x[2] - 0.6) < 1e-7 and np.isnan(x[3])


def test_islak_kuru_8_2():
    poz = np.zeros((40, 40), bool); poz.ravel()[:800] = True
    veri = np.ones((40, 40), bool)
    assert O.pi_arti(poz, veri) == 0.5 and O.islak_mi(O.pi_arti(poz, veri))
    poz.ravel()[799] = False
    assert not O.islak_mi(O.pi_arti(poz, veri))
    assert not O.islak_mi(O.pi_arti(poz, np.zeros_like(veri)))  # kapsam dışı → kuru


@pytest.mark.parametrize("phi,delta,beklenen", [(0, 0, 1 / math.pi), (90, 23.44, math.sin(r(23.44))), (90, -23.44, 0.0)])
def test_aydinlanma_8_2(phi, delta, beklenen):
    assert abs(float(O.berger_gunluk(r(phi), r(delta))) - beklenen) < 1e-12
    assert abs(math.sin(r(23.44)) - 0.3978) < 1e-4


def test_berger_tablosu_ara_deger():
    for eps in (23.44, 1.54, 25.19):
        t = O.BergerTablosu(eps)
        lat = np.concatenate([np.random.default_rng(0).uniform(-90, 90, 300), 90 - eps + np.linspace(-0.01, 0.01, 50)])
        assert np.max(np.abs(t(lat) - O.berger_yillik(np.radians(lat), eps))) < 1e-8, eps
    # ekvatorda ε = 0 → f = 1/π
    assert abs(O.berger_yillik(0.0, 0.0)[0] - 1 / math.pi) < 1e-12


def test_deklinasyon():
    _, dh = O.gunes_boylami_ve_deklinasyon(datetime.date(2023, 6, 21))
    _, dk = O.gunes_boylami_ve_deklinasyon(datetime.date(2023, 12, 22))
    _, de = O.gunes_boylami_ve_deklinasyon(datetime.date(2023, 3, 20))
    assert abs(math.degrees(dh) - 23.44) < 0.05 and abs(math.degrees(dk) + 23.44) < 0.05 and abs(math.degrees(de)) < 0.5


def test_mars_mineraloji_8_2():
    assert abs(float(O.mars_hcp(0.2, 0.1, 0.1)) - 0.25) < 1e-15
    assert np.isnan(O.mars_hcp(0.2, 0.1, np.nan)) and np.isnan(O.mars_hcp(0.0, 0.0, 0.0))


def test_mineraloji_gecersiz_pencere_8_2():
    Q = np.zeros(1000)
    assert np.isnan(O.d4(Q, 0.40, Q, 1.0)) and O.d4(Q, 0.50, Q, 1.0) == 0.0 and np.isnan(O.d4(Q, 1.0, Q, 0.4))
    x = np.full((40, 40), np.nan); x.ravel()[:640] = 1.0
    assert O.gecerli_oran(x) == 0.4


def test_mafik_indeks():
    assert abs(float(O.mafik_indeks(0.95, 0.97, 0.96)) - 0.95 * 0.96 ** 3 / 0.97 ** 4) < 1e-15


def _sozluk(tmp_path, satirlar):
    p = tmp_path / "s.csv"
    pd.DataFrame(satirlar, columns=["cisim", "birim_kodu", "birim_aciklama", "grup", "kaynak"]).to_csv(p, index=False)
    return p


def test_sozluk_assertleri(tmp_path):
    p = _sozluk(tmp_path, [("mars", "a", "", "volkanik", ""), ("mars", "b", "", "yayla_yarim", ""), ("mars", "c", "", "", "")])
    with pytest.raises(AssertionError, match="grubu boş"):
        O.sozluk_matrisi("mars", ["a", "b", "c"], p)
    with pytest.raises(AssertionError, match="sözlükte olmayan"):
        O.sozluk_matrisi("mars", ["a", "z"], p)
    p2 = _sozluk(tmp_path, [("mars", "a", "", "volkanikk", "")])
    with pytest.raises(AssertionError, match="izinsiz"):
        O.sozluk_matrisi("mars", ["a"], p2)
    p3 = _sozluk(tmp_path, [("mars", "a", "", "volkanik", ""), ("mars", "b", "", "yayla_yarim", ""), ("mars", "w", "", "hesap_disi", "")])
    G = O.sozluk_matrisi("mars", ["a", "b", "w"], p3)
    assert G[0].tolist() == [1, 0, 0, 0, 0, 0] and G[1].tolist() == [0.5, 0, 0, 0.5, 0, 0] and G[2].sum() == 0


def test_grup_paylari_ve_kar_buz():
    G = np.array([[1, 0, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 0]], float)  # volkanik, tortul, hesap dışı
    pay = np.array([[0.5, 0.3, 0.2], [0, 0, 1.0], [np.nan, np.nan, np.nan]])
    q = O.hucre_grup_paylari(pay, G)
    assert np.allclose(q[0], [0.625, 0, 0, 0.375, 0, 0]) and np.isnan(q[1]).all() and np.isnan(q[2]).all()
    qk = O.hucre_grup_paylari(pay, G, kar_buz=np.array([0.2, 0.5, 0.0]))
    assert np.allclose(qk[0], [0.5, 0, 0, 0.3, 0, 0.2]) and np.allclose(qk[1], [0, 0, 0, 0, 0, 1]) and np.isnan(qk[2]).all()


def test_pencere_jeoloji_ve_tv():
    qh = np.full((2, 2, 6), np.nan)
    qh[0, 0] = [1, 0, 0, 0, 0, 0]; qh[0, 1] = [0, 0, 0, 1, 0, 0]; qh[1, 0] = [1, 0, 0, 0, 0, 0]
    q, gec = O.pencere_jeoloji(qh)
    assert np.allclose(q, [2 / 3, 0, 0, 1 / 3, 0, 0]) and gec == 0.75
    assert abs(O.d3(q, [0, 0, 0, 1, 0, 0]) - 2 / 3) < 1e-12


# ------------------------------------------------ sentetik katmanlarla pencere hattı
def _sahte(monkeypatch, katmanlar):
    for ad, k in katmanlar.items():
        monkeypatch.setitem(O._OD, ad, k)
    monkeypatch.setattr(O, "_SIRA", {})


def _cografi(ad, f, ppd, y0=90.0, nrow=None):
    nrow = int(180 * ppd) if nrow is None else nrow
    lat = y0 - (np.arange(nrow) + 0.5) / ppd
    lon = -180 + (np.arange(int(360 * ppd)) + 0.5) / ppd
    return K.Cografi(ad, f(lat[:, None], lon[None, :]).astype(np.float32), -180.0, 1 / ppd, y0, 1 / ppd, nrow, int(360 * ppd), "")


def test_mars_pencere_hatti(monkeypatch):
    _sahte(monkeypatch, {
        "mars_hcp": _cografi("mars_hcp", lambda la, lo: 0.3 + 0.001 * la + 0 * lo, 4),
        "ti": _cografi("ti", lambda la, lo: 200 + la + 0.1 * lo, 20),
        "swim": _cografi("swim", lambda la, lo: np.sin(np.radians(lo)) + 0 * la, 20, y0=60.0, nrow=2400),
        "dci": _cografi("dci", lambda la, lo: 0.95 + 0 * la + 0 * lo, 16),
    })
    phi0, lam0 = np.radians([18.44, 18.44]), np.radians([77.45, 77.45])
    T = O.pencere_temsili("mars", phi0, lam0, kategoriler=(4, 5, 6, 7, 8), n_ref=20000)
    for k in ("Q4", "Q5_iarti", "Q6", "Q7", "Q8"):
        assert T[k].shape == (2, 1000) and np.isfinite(T[k]).all(), k
        assert np.array_equal(T[k][0], T[k][1])
    assert T["x4_gecerli"].tolist() == [1.0, 1.0]
    assert T["pi_arti"][0] == 1.0 and O.islak_mi(T["pi_arti"])[0]  # sin(77°) > 0 → bütün hücreler pozitif
    assert np.all((T["Q8"] >= 0) & (T["Q8"] <= 1))
    # aynı pencereye uzaklık 0
    assert O.d_dagilim(T["Q6"][0], T["Q6"][1]) == 0 and O.d4(T["Q4"][0], 1.0, T["Q4"][1], 1.0) == 0
    assert O.d5({"iarti": T["Q5_iarti"][0]}, {"iarti": T["Q5_iarti"][1]}, ["iarti"]) == 0


def test_ay_pencere_hatti_pi_arti_ve_aydinlanma(monkeypatch):
    # PRP bayrağı: boylam < 30° sansürlü (1), ≥ 30° değer (0); M-SP (−89, 30) penceresinde iki taraf da var
    bay = O.Fonksiyon("b", lambda la, lo: np.where(la < -75.9, np.where(lo < 30.0, 1.0, 0.0), np.nan), lambda la, rr: (0.2, 0.2))
    _sahte(monkeypatch, {
        "prp_ice_depth_bayrak": bay,
        "hidrojen_th": _cografi("h", lambda la, lo: 100 + 0 * la + 0 * lo, 2),
        "pgda": O.Fonksiyon("p", lambda la, lo: np.where(np.abs(la) >= 65, 0.3 + 0 * lo, np.nan), O._kaba),
        "berger_ay": O.Fonksiyon("b", lambda la, lo: 0.3 - 0.001 * np.abs(la) + 0 * lo, O._kaba),
        "ra": _cografi("ra", lambda la, lo: 0.01 + 0 * la + 0 * lo, 4, y0=70.0, nrow=560),
    })
    T = O.pencere_temsili("ay", np.radians([-89.0]), np.radians([30.0]), kategoriler=(6, 7, 8), n_ref=5000)
    assert 0.3 < T["pi_arti"][0] < 0.7               # yaklaşık yarısı pozitif
    assert np.isnan(T["Q7"]).all()                    # 70° ötesinde kaya bolluğu yok → null
    assert np.isfinite(T["Q8"]).all()                 # 65° ötesi PGDA sırası
    T2 = O.pencere_temsili("ay", np.radians([0.0]), np.radians([0.0]), kategoriler=(6, 8), n_ref=5000)
    assert np.isnan(T2["pi_arti"][0]) and not O.islak_mi(T2["pi_arti"])[0]  # 75,9° berisi → kuru


def test_termal_ozellikleri():
    assert O.termal_ozellikleri("ay", -85.0) == ["tmax", "tort", "tgece"]
    assert O.termal_ozellikleri("ay", -72.0) == ["tgece"] and O.termal_ozellikleri("ay", 10.0) == ["tgece"]
    assert O.termal_ozellikleri("mars", 18.0) == ["iarti"] and len(O.termal_ozellikleri("dunya", 0.0)) == 4
def test_I_arti_yillik_madde29():
    # Σ C₁(1 − α) / Σ ΔTg = aylık I⊕'nin ΔTg ağırlıklı ortalaması; geçersiz ay (NaN) toplamlara girmez
    rng = np.random.default_rng(29)
    c1 = rng.uniform(0.1, 1.6, (12, 50)); a = rng.uniform(0, 0.9, (12, 50)); dT = rng.uniform(0.02, 40, (12, 50))
    dT[0, :10] = -1.0; c1[1, 10:20] = 0.0; a[2, 20:30] = np.nan
    I = O.I_arti_ay(c1, a, dT)
    g = np.isfinite(I)
    Iy = O.I_arti_yillik(np.where(g, c1 * (1 - a), 0).sum(0), np.where(g, dT, 0).sum(0), g.sum(0))
    w = np.where(g, dT, 0)
    np.testing.assert_allclose(Iy, np.nansum(I * w, 0) / w.sum(0), rtol=1e-12)
    assert np.all(Iy <= np.nanmax(I, 0) + 1e-12) and np.all(Iy >= np.nanmin(I, 0) - 1e-12)
    assert np.isnan(O.I_arti_yillik(0.0, 0.0, 0))
