# Developed with assistance from Claude (Anthropic).
"""ozellik_diger gerçek temiz\\ verisiyle: CMG türetilmiş ızgaralar, türetilmiş katmanlar, birim kontrolleri,
referanslar (küçük örnek), gerçek pencere temsilleri. Mars jeoloji sözlüğü Sude doldurana kadar bilerek FAIL verir."""
import math
import json
import numpy as np
import pytest
import ayar as A
import katman as K
import ozellik_diger as O
import uzaklik as U


def test_dunya_cmg_turetilmis():
    yol = O.dunya_cmg()
    # Aralıklar verinin kendi sınırlarından türetilir (14 Kasım; ilk sürümdeki elle konmuş MI ve I⊕ sınırları yanlıştı):
    # MI = ε₁₂ε₁₄³/ε₁₃⁴, ε ∈ [0,604; 1] (D2'de ölçülen) → [0,604⁴; 1/0,604⁴] = [0,133; 7,5]
    # I⊕ = C₁(1 − α)/ΔTg, ΔTg ≥ 0,02 K (LST ölçeği); C₁'in en büyüğü ε = 23,44°'de 1,6426 (φ ≈ ±28°, δ = ±23,44°)
    #   → (0; ≈ 82,1] (Sude, 14 Kasım; aşağıda C₁ formülünden hesaplanır)
    # LST: geçerli aralık 7500–65535 × 0,02 K = 150–1310,7 K (dosya valid_range)
    eps = A.ayar("cisim.eksen_egikligi_der")["dunya"]
    c1max = float(np.nanmax(O.C1(np.radians(np.linspace(-90, 90, 18001))[:, None],
                                 np.radians(np.linspace(-eps, eps, 4689))[None, :])))
    assert abs(c1max - 1.6426) < 1e-3, c1max
    aralik = {"tmax": (150, 1310.7), "tort": (150, 1310.7), "tgece": (150, 1310.7),
              "mi": (0.604 ** 4, 1 / 0.604 ** 4), "iarti": (0, c1max / 0.02)}
    for ad, (lo, hi) in aralik.items():
        j = json.loads(yol[ad].with_suffix(".json").read_text(encoding="utf-8"))
        assert j["gecerli"] > 1_000_000, (ad, j["gecerli"])
        assert lo <= j["en_kucuk"] and j["en_buyuk"] <= hi, (ad, j["en_kucuk"], j["en_buyuk"])
    t = json.loads(yol["iarti"].with_suffix(".json").read_text(encoding="utf-8"))["aylar"]
    d = [t[f"ay_{m:02d}"]["deklinasyon_der"] for m in range(1, 13)]
    assert max(d) > 23 and min(d) < -23  # haziran/aralık


@pytest.mark.parametrize("ad", ["cmg_mi", "cmg_tmax", "cmg_tort", "cmg_tgece", "cmg_iarti", "perm_sifir", "siltkil",
                                "berger_dunya", "berger_ay", "berger_mars", "ay_tgece", "hidrojen_th", "pgda", "mars_hcp"])
def test_turetilmis_katman_acilir(ad):
    k = O.ac(ad)
    v = k.ornekle(np.array([-85.0, 0.0, 45.0, 85.0]), np.array([30.0, 10.0, -100.0, 100.0]))
    assert v.shape == (4,)


def test_toryum_birim_ve_esik():
    # belge 6.6: Th ≥ 4,56 ppm = Ay'ın en yüksek toryumlu %10'u → alanca düzgün örnekte pay ≈ 0,10
    th = K.ac("lpgrs_w_th")
    lat, lon = U.kure_noktalari(np.random.default_rng(11), 200000)
    v = th.ornekle(lat, lon)
    assert np.nanmin(v) >= -1 and np.nanmax(v) < 30, (np.nanmin(v), np.nanmax(v))
    pay = float(np.mean(v >= A.ayar("su_buz.ay_toryum_ppm")))
    assert 0.08 <= pay <= 0.12, pay


def test_sifir_kurali_gercek():
    p = O.ac("perm_sifir")
    lat, lon = U.kure_noktalari(np.random.default_rng(12), 200000, -30, 30)
    v = p.ornekle(lat, lon)
    kara = np.isfinite(v)
    assert kara.mean() > 0.15 and np.mean(v[kara] == 0) > 0.99  # tropik karada permafrost yok → 0


@pytest.mark.parametrize("govde,oz", sorted(O.OZELLIK))
def test_referans_kucuk(govde, oz):
    s = O.sira(govde, oz, n_en_fazla=20000, onbellek=False)
    assert s.n > 1000, s.n
    if O.OZELLIK[(govde, oz)][2] == "u+":
        assert 0 <= s.sifir_orani < 1


@pytest.mark.parametrize("govde,lat,lon,kat", [("dunya", 35.58223, -111.63182, (3, 4, 5, 6, 7, 8)),   # 9.3 SP Crater
                                               ("ay", -85.399, 31.180, (3, 4, 5, 6, 7, 8)),         # B5 A3-05
                                               ("ay", 26.13239, 3.63330, (3, 4, 5, 6, 7, 8)),       # 9.1 M-A15
                                               ("mars", 18.44, 77.45, (4, 5, 6, 7, 8))])            # 9.2 R-JEZ
def test_gercek_pencere_temsili(govde, lat, lon, kat):
    T = O.pencere_temsili(govde, [math.radians(lat)], [math.radians(lon)], kategoriler=kat, n_ref=20000)
    if 3 in kat:
        assert abs(np.nansum(T["q3"][0]) - 1) < 1e-6 and T["q3_gecerli"][0] > 0.5
    # Q6: Ay'da toryum maskesi (Th ≥ 4,56 ppm) bütün pencereyi düşürebilir (ör. Imbrium çevresi); orada yalnız
    # "ya tamamen sonlu ya tamamen null" kontrol edilir.
    beklenen = {"Q4": True, "Q8": True, "Q7": not (govde == "ay" and abs(lat) > 70),
                "Q6": True if govde != "ay" else None}
    for k, sonlu in beklenen.items():
        hepsi, hic = np.isfinite(T[k]).all(), (~np.isfinite(T[k])).all()
        assert hepsi or hic, (k, "kısmi null")
        if sonlu is not None:
            assert hepsi == sonlu, (k, govde, lat)
    for f in O.termal_ozellikleri(govde, lat):
        assert np.isfinite(T[f"Q5_{f}"]).all(), f
    if govde != "dunya":
        assert "pi_arti" in T


def test_mars_jeoloji_sozlugu_tam():
    # Sude jeoloji_sozluk.csv'de Mars'ın 44 biriminin grubunu doldurunca geçer (belge 6.3, 15.1)
    G = O.sozluk_matrisi("mars", list(O.ac("sim3292").siniflar))
    assert G.shape == (44, 6)
    T = O.pencere_temsili("mars", [math.radians(18.44)], [math.radians(77.45)], kategoriler=(3,), n_ref=20000)
    assert abs(np.nansum(T["q3"][0]) - 1) < 1e-6
