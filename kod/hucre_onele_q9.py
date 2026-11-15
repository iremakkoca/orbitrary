# Developed with assistance from Claude (Anthropic).
# onele.py güncellemesi: Q-9 (hiçbir K r̄ ≥ 0,9 değilse 800), Q-10 (şart ortalama recall'a; GA hesaplanır). Sude onaylı 12:51.
import sys, importlib
from pathlib import Path
KOK = Path.home() / "orbitrary"; KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / "onele.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 7.1: ön eleme. z vektörü, dayanıklı (MAD) standartlaştırma, KD-ağacı (scipy.spatial.cKDTree), Kön seçimi.

z = (θ̄, θ₀,₉, VRM̄, ln R, n↓, n↑) — ilk dördü ozellik_topo.z_topo (500 m ölçeği), son ikisi ozellik_topoloji.n_onemli.
z̃_l = (z_l − medyan_{E′} z_l) / (1,4826 · MAD_{E′}(z_l))  [96]. Medyan ve MAD yalnız Dünya E′ üzerinden; hedefler de
aynı sabitlerle standartlaşır.

Onaylı karar Q-1 (Sude, 14 Kasım): MAD = 0 olan bileşen z'den çıkar ve kayda yazılır (Qn kullanılmaz).
E′_g = E′ içinde G_g = 1 olan pencereler (kapi.py: "could not be checked" G = 1 verir). Görev yoksa E′_g = E′.
z'si eksik (NaN) Dünya penceresi ağaca girmez ve sayısı kayda yazılır: n↓/n↑ yalnız DEM tamsa hesaplanır; DEM'i eksik
pencere topoloji kategorisi olmadığı için zaten uygun değildir (belge 7.2 uygunluk).
Eşitlik kırıcı: aynı uzaklıkta pencere kimliği küçük olan önce (sıra deterministik).
Kön: V5'te {100, 200, 400, 800} içinden ortalama recall ≥ 0,9 sağlayan en küçük değer (belge 7.1, 8.3; Q-10);
hiçbiri sağlamazsa 800 (Q-9).
"""
import numpy as np
from scipy.spatial import cKDTree

import ozellik_topo as T
import ozellik_topoloji as TP

MAD_SABITI = 1.4826                   # belge 7.1 [96]: normal dağılımda σ ile tutarlılık
K_ON_ADAYLARI = (100, 200, 400, 800)  # belge 7.1 / 8.3 V5
RECALL_ESIGI = 0.9                    # belge 7.1 / 8.3 V5
BILESENLER = ("theta_ort", "theta_09", "vrm_ort", "lnR", "n_asagi", "n_yukari")


def z_vektoru(oz, diyagram, govde):
    """Tek pencere: ozellik_topo.ozellikler() sözlüğü + ozellik_topoloji.diyagramlar() çıktısı → (6,)."""
    z4 = np.asarray(T.z_topo(oz), float).reshape(-1)
    assert z4.shape == (4,), z4.shape
    na, ny = TP.n_onemli(diyagram, govde)
    return np.concatenate([z4, [float(na), float(ny)]])


class Olcek:
    """Belge 7.1 dayanıklı standartlaştırma; Z_E: (n, 6) Dünya E′ z'leri (NaN satırlar medyan/MAD dışında)."""

    def __init__(self, Z_E):
        Z = np.asarray(Z_E, float)
        assert Z.ndim == 2 and Z.shape[1] == len(BILESENLER), Z.shape
        tam = np.isfinite(Z).all(axis=1)
        assert tam.sum() >= 2, "E′ içinde z'si tam pencere yok"
        Zt = Z[tam]
        self.n_E = int(len(Z))
        self.n_eksik = int((~tam).sum())
        self.medyan = np.median(Zt, axis=0)
        self.mad = np.median(np.abs(Zt - self.medyan[None, :]), axis=0)
        self.tut = self.mad > 0                              # Q-1
        self.dusen = [BILESENLER[l] for l in np.flatnonzero(~self.tut)]
        assert self.tut.any(), "z'nin bütün bileşenlerinde MAD = 0"

    def standart(self, Z):
        """(…, 6) → (…, m), m = tutulan bileşen sayısı."""
        Z = np.asarray(Z, float)
        return ((Z - self.medyan) / (MAD_SABITI * np.where(self.tut, self.mad, 1.0)))[..., self.tut]

    def kayit(self):
        return {"n_E_prime": self.n_E, "z_eksik_pencere": self.n_eksik,
                "medyan": dict(zip(BILESENLER, map(float, self.medyan))),
                "MAD": dict(zip(BILESENLER, map(float, self.mad))),
                "MAD_sifir_cikan_bilesenler": self.dusen, "MAD_sabiti": MAD_SABITI}


class Agac:
    """E′_g üzerinde KD-ağacı. Z_E (n, 6) Dünya E′ z'leri; G (n,) bool kapı (None → bütün E′); kimlik (n,) pencere no."""

    def __init__(self, olcek, Z_E, G=None, kimlik=None):
        Z = np.asarray(Z_E, float)
        n = len(Z)
        G = np.ones(n, bool) if G is None else np.asarray(G, bool)
        assert G.shape == (n,), G.shape
        self.kimlik = np.arange(n) if kimlik is None else np.asarray(kimlik)
        assert self.kimlik.shape == (n,) and len(np.unique(self.kimlik)) == n
        Zs = olcek.standart(Z)
        tam = np.isfinite(Zs).all(axis=1)
        sec = G & tam
        self.n_kapi = int(G.sum())
        self.n_kapi_z_eksik = int((G & ~tam).sum())
        self._idx = np.flatnonzero(sec)
        self._Z = Zs[sec]
        self.olcek = olcek
        self._agac = cKDTree(self._Z) if len(self._Z) else None

    def __len__(self):
        return len(self._idx)

    def sorgu(self, z_hedef, K):
        """E_K(T, g): ‖z̃(E) − z̃(T)‖₂ en küçük K aday. Dönüş (satır indeksleri, kimlikler, uzaklıklar), artan sırada."""
        K = int(K)
        assert K >= 1
        zt = self.olcek.standart(np.asarray(z_hedef, float).reshape(-1))
        if not np.isfinite(zt).all():
            raise ValueError("hedef z'sinde tutulan bileşende NaN: " +
                             str([b for b, t, v in zip(BILESENLER, self.olcek.tut, np.asarray(z_hedef, float)) if t and not np.isfinite(v)]))
        if self._agac is None:
            return np.array([], int), self.kimlik[:0], np.array([])
        k = min(K, len(self._idx))
        d, _ = self._agac.query(zt, k=k)
        dK = float(np.max(np.atleast_1d(d)))
        aday = np.asarray(self._agac.query_ball_point(zt, r=dK * (1 + 1e-9) + 1e-12), int)
        dist = np.sqrt(np.sum((self._Z[aday] - zt[None, :]) ** 2, axis=1))
        sat = self._idx[aday]
        o = np.lexsort((self.kimlik[sat], dist))[:k]
        return sat[o], self.kimlik[sat[o]], dist[o]

    def kayit(self):
        return {"kapidan_gecen": self.n_kapi, "kapidan_gecen_z_eksik": self.n_kapi_z_eksik, "agac_boyu": len(self)}


def recall_ozet(recall):
    """Belge 8.3 V5: r̄ ± 1,96 · s_d / √n (s_d örneklem standart sapması, ddof = 1). Dönüş (r̄, alt, üst)."""
    r = np.asarray(recall, float)
    assert r.ndim == 1 and len(r) >= 2 and np.isfinite(r).all() and ((r >= 0) & (r <= 1)).all()
    m = float(r.mean()); y = 1.96 * float(r.std(ddof=1)) / np.sqrt(len(r))
    return m, m - y, m + y


def kon_sec(recall_ortalama):
    """Belge 7.1 / V5 + Q-9, Q-10 (Sude, onaylı): şart ortalama recall'a uygulanır; {100, 200, 400, 800} içinde
    r̄ ≥ 0,9 olan en küçük K. Hiçbiri sağlamazsa K = 800 (denenenlerin en büyüğü), koşu durmaz, liste genişletilmez.
    Dönüş (K, esik_saglandi)."""
    assert set(recall_ortalama) == set(K_ON_ADAYLARI), recall_ortalama
    for K in K_ON_ADAYLARI:
        if float(recall_ortalama[K]) >= RECALL_ESIGI:
            return K, True
    return K_ON_ADAYLARI[-1], False
''', encoding="utf-8")
(KOD / "testler" / "test_onele.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 7.1 ön eleme testleri (Q-1 dahil)."""
import itertools

import numpy as np
import pytest

import onele as O
import ozellik_topo as T
import ozellik_topoloji as TP

RNG = np.random.default_rng(20261113)


def _Z(n, rng=RNG):
    Z = rng.normal(size=(n, 6)) * [3, 5, 0.01, 1, 4, 4] + [10, 20, 0.02, 5, 8, 8]
    Z[:, 4:] = np.round(np.abs(Z[:, 4:]))
    return Z


def _kaba(Z, G, zt, ol, K):
    Zs = ol.standart(Z)
    ok = G & np.isfinite(Zs).all(axis=1)
    idx = np.flatnonzero(ok)
    d = np.sqrt(((Zs[idx] - ol.standart(zt)) ** 2).sum(axis=1))
    o = np.lexsort((idx, d))[:K]
    return idx[o], d[o]


def test_z_vektoru_bilesenleri():
    x = np.arange(56) * 500.0
    h = 300 * np.sin(x[None, :] / 4000) * np.cos(x[:, None] / 3000) + 50 * np.random.default_rng(1).normal(size=(56, 56))
    oz = T.ozellikler(h, "dunya")
    W = h[T.GEN:-T.GEN, T.GEN:-T.GEN]
    dg = TP.diyagramlar(W, "dunya", yontem="union_find")
    z = O.z_vektoru(oz, dg, "dunya")
    assert z.shape == (6,)
    th = oz["theta_1"].ravel()
    assert z[0] == pytest.approx(np.mean(th))
    assert z[1] == pytest.approx(T.ceyrek(th, 9, 10))
    assert z[2] == pytest.approx(np.mean(oz["vrm_1"]))
    assert z[3] == pytest.approx(float(oz["lnR"]))
    assert tuple(z[4:]) == TP.n_onemli(dg, "dunya")


def test_z_vektoru_dem_eksik_nan():
    oz = T.ozellikler(np.ones((56, 56)), "dunya")
    z = O.z_vektoru(oz, None, "dunya")
    assert np.isnan(z[4:]).all() and np.isfinite(z[:4]).all()


def test_medyan_mad_elle():
    Z = np.array([[1, 2, 3, 4, 5, 6], [2, 4, 6, 8, 10, 12], [4, 8, 12, 16, 20, 24],
                  [np.nan, 0, 0, 0, 0, 0]], float)
    ol = O.Olcek(Z)
    assert ol.n_eksik == 1
    np.testing.assert_allclose(ol.medyan, [2, 4, 6, 8, 10, 12])
    np.testing.assert_allclose(ol.mad, [1, 2, 3, 4, 5, 6])
    np.testing.assert_allclose(ol.standart(np.array([4, 4, 6, 8, 10, 0.0])),
                               [2 / 1.4826, 0, 0, 0, 0, -12 / (6 * 1.4826)])


def test_mad_sifir_bilesen_cikar_Q1():
    Z = _Z(101)
    Z[:, 4] = 3.0
    Z[:60, 5] = 7.0   # yarıdan fazlası aynı → MAD = 0
    ol = O.Olcek(Z)
    assert ol.dusen == ["n_asagi", "n_yukari"]
    assert ol.standart(Z).shape == (101, 4)
    assert ol.kayit()["MAD_sifir_cikan_bilesenler"] == ["n_asagi", "n_yukari"]


@pytest.mark.parametrize("K", [1, 5, 37, 200])
def test_kd_kaba_kuvvetle_ayni(K):
    rng = np.random.default_rng(K)
    Z = _Z(3000, rng)
    Z[rng.choice(3000, 50, replace=False), 4] = np.nan
    G = rng.random(3000) < 0.6
    ol = O.Olcek(Z)
    ag = O.Agac(ol, Z, G)
    for _ in range(5):
        zt = _Z(1, rng)[0]
        s, kim, d = ag.sorgu(zt, K)
        s0, d0 = _kaba(Z, G, zt, ol, K)
        np.testing.assert_array_equal(s, s0)
        np.testing.assert_allclose(d, d0, rtol=1e-12)
        assert G[s].all() and np.all(np.diff(d) >= 0)


def test_esitlikte_kucuk_kimlik_once():
    base = _Z(400)
    Z = np.vstack([base, np.repeat(base[:1], 9, axis=0)])   # 10 aynı nokta
    kim = np.arange(len(Z))[::-1].copy()                    # kimlik sırası satır sırasının tersi
    ol = O.Olcek(Z)
    ag = O.Agac(ol, Z, kimlik=kim)
    s, k, d = ag.sorgu(base[0], 4)
    assert np.all(d == 0)
    hepsi = np.r_[0, np.arange(400, 409)]
    np.testing.assert_array_equal(k, np.sort(kim[hepsi])[:4])
    s2, k2, _ = ag.sorgu(base[0], 4)
    np.testing.assert_array_equal(k, k2)


def test_kimlik_D7_kendi_penceresi_ilk():
    Z = _Z(2000)
    ol = O.Olcek(Z)
    ag = O.Agac(ol, Z)
    for i in (0, 17, 1999):
        s, _, d = ag.sorgu(Z[i], 10)
        assert s[0] == i and d[0] == 0


def test_aday_sayisi_K_den_az():
    Z = _Z(500)
    G = np.zeros(500, bool); G[[3, 9, 44]] = True
    ag = O.Agac(O.Olcek(Z), Z, G)
    s, _, _ = ag.sorgu(Z[0], 100)
    assert sorted(s) == [3, 9, 44]
    bos = O.Agac(O.Olcek(Z), Z, np.zeros(500, bool))
    assert len(bos.sorgu(Z[0], 10)[0]) == 0


def test_kapi_ve_eksik_sayilari():
    Z = _Z(1000)
    Z[:10, 5] = np.nan
    G = np.ones(1000, bool); G[5:20] = False
    ag = O.Agac(O.Olcek(Z), Z, G)
    assert ag.kayit() == {"kapidan_gecen": 985, "kapidan_gecen_z_eksik": 5, "agac_boyu": 980}


def test_hedef_nan():
    Z = _Z(300)
    Z[:, 4] = 1.0
    ag = O.Agac(O.Olcek(Z), Z)
    zt = Z[0].copy(); zt[4] = np.nan          # çıkan bileşen: sorun yok
    assert len(ag.sorgu(zt, 5)[0]) == 5
    zt[5] = np.nan                            # tutulan bileşen: hata
    with pytest.raises(ValueError):
        ag.sorgu(zt, 5)


def test_olcek_ve_kaydirma_degismez():
    rng = np.random.default_rng(7)
    Z = _Z(2000, rng); zt = _Z(1, rng)[0]
    a = rng.uniform(0.1, 50, 6); b = rng.normal(0, 100, 6)
    s1 = O.Agac(O.Olcek(Z), Z).sorgu(zt, 50)[0]
    s2 = O.Agac(O.Olcek(Z * a + b), Z * a + b).sorgu(zt * a + b, 50)[0]
    np.testing.assert_array_equal(s1, s2)


def test_kon_sec_Q9_Q10():
    assert O.kon_sec({100: 0.85, 200: 0.91, 400: 0.95, 800: 0.97}) == (200, True)
    assert O.kon_sec({100: 0.9, 200: 0.95, 400: 0.95, 800: 0.97}) == (100, True)
    assert O.kon_sec({100: 0.5, 200: 0.6, 400: 0.7, 800: 0.89}) == (800, False)
    with pytest.raises(AssertionError):
        O.kon_sec({100: 0.9})


def test_recall_ozet():
    r = np.array([1, 2 / 3, 1, 1 / 3, 1.0])
    m, a, u = O.recall_ozet(r)
    y = 1.96 * np.std(r, ddof=1) / np.sqrt(5)
    assert m == pytest.approx(np.mean(r)) and a == pytest.approx(m - y) and u == pytest.approx(m + y)
    assert O.recall_ozet(np.ones(200)) == (1.0, 1.0, 1.0)
''', encoding="utf-8")
(KAYIT / "makaleyi_etkiler_14_kasim.md").write_text(r'''# MAKALEYİ ETKİLER — 14 Kasım 2026 (kod günü) toplu kayıt

Orbitrary · belge v1.2 (+ v1.2.1 talimatları). Kod yazılırken çıkan, makaleye giren her şey.
Kaynak: `kayit\degisiklik.md` (tarihli satırlar). Durum sütunu: **kaynaklı** = dış kaynağa dayanıyor; **onaylı** = ekip onayladı; **onay bekliyor** = proje kararı, dış kaynağı yok.

## 1. Parametre ve veri

| # | Ne değişti / netleşti | Belge bölümü | Durum | Makaleye not (Emir / Sude) |
|---|---|---|---|---|
| 1 | σv Ay = 10 m, Mars = 1 m (belgede değer yoktu; Dünya 7,17 m aynı) | 4.1, 8.4, T2 | kaynaklı: [105] Smith ve ark. 2010 "~10 m radial"; [104] Smith ve ark. 2001 "~1 m vertical" | T2'de σv = 7,17 / 10 / 1 m; Method'da iki kaynağa bu değerlerle atıf |
| 2 | MI geçerlilik aralığı [0,133; 7,5] = yayınım aralığından (0,604–1,000) türetilmiş matematiksel sınır | 6.4, 10.1 | onaylı (Sude) | ASTER en küçük yayınım 0,604 (belge 0,61 diyordu; talimat 7 UYARI) |
| 3 | I⊕ üst sınırı ≈ 82,1 = max C₁ (1,6426, ε = 23,44°) / 0,02 K | 6.5 | onaylı (Sude) | ölçülen en büyük 75,3 |

## 2. Yöntemin okunuşu (formül aynı, belgede tek anlama inmeyen yer netleşti)

| # | Karar | Belge bölümü | Durum | Makaleye not |
|---|---|---|---|---|
| 4 | P_f,B: "rastgele piksel" yerine alanca düzgün rastgele noktaların piksel değerleri (≤ 10⁶, tohum 20261113) | 5.2 | onaylı (Sude, 12:17) | "area-uniform random sample"; neden: enlem-boylam pikseli kutbu 1/cos φ ağırlıklandırır |
| 5 | Dünya Tmax = aylık gündüz LST'nin en büyüğü; T̄ = aylık (gündüz+gece)/2 yıllık ortalaması; Tgece = aylık gece yıllık ortalaması | 6.5 | onaylı (Sude, 12:17) | dayanak 6.5 "Aqua öğleden sonra geçişi maksimuma yakın" — veri MYD11C3 = Aqua (kaynak dosya MYD11C3.A2023…hdf; belge D1); Aqua ~13:30 / ~01:30 (NASA MODIS teknik sayfası). Sude'nin 'Terra ~10:30' düzeltmesi uygulanmadı: veri Terra değil |
| 6 | I⊕ aylık; C₁ = 0 ve ΔTg ≤ 0 ayları ortalamaya girmez (ΔTg ≤ 0 NaN, assert ve sayılar kayıtta) | 6.5 | ΔTg ≤ 0: onaylı (Sude); yıllık ortalama belgedeki gibi kalır | δ⊙: Michalsky 1988 (Astronomical Almanac düşük duyarlıklı algoritma) |
| 7 | ASTER MI her bandın 12 aylık ortalamasından; ortalamaya yalnız geçerli aylar (0 = yok → NaN) girer | 6.4 | onaylı (Sude, 12:17) | — |
| 8 | Ay aydınlanması: |φ| ≥ 65° PGDA ve < 65° Berger hücreleri kendi kapsamlarında ayrı sıralanır | 6.8 | onaylı (Sude, 12:17) | iki büyüklük farklı birimde; Limitations'a bir cümle |
| 9 | Sıfır kuralında kara hücresi = MCD12C1 kara payı ≥ 0,5 | 6.6 | onaylı, proje kararı (Sude, 12:17) | kar/buz < 0,5 ile aynı çoğunluk mantığı |
| 10 | Ay π⁺: hücrenin alt örneklerinin ≥ yarısında ice_depth ≠ −999 ise hücre pozitif | 6.6 | onaylı, proje kararı (Sude, 12:17) | — |

## 3. Test tanımı

| # | Ne | Belge bölümü | Not |
|---|---|---|---|
| 11 | "Halka ızgarası" testi: formül aralıkları her halkada 20 km ± %5; gerçek komşu uzaklığı kutup ilk halkası (m = 3, ~17,3 km) dışında ± %5; ≤ 5 km sapan tıklama kendi penceresi = en yakın merkez; her nokta kendi hücresine eşlenir, merkeze uzaklık hücre köşe uzaklığını aşmaz (kutup halka 0: 17,3 km, halka 1: 15,6 km, diğer ≤ 14,7 km); en yakın merkeze uzaklık < 15 km | 8.3, T5 | formülün en yakın merkezi verme oranı %96,2 (`kayit\izgara_bilgi.json`) |
| 12 | K12 kontrolü: belgedeki SW (1/π, yarım çember) = Carrière ve ark. (1/2π, S¹); sabit aynı, K12 tetiklenmedi, Ψ₂ değişmez | 6.2, 8.1, 11 | test: `test_sw_tek_nokta_analitik_ve_K12` |

## 4. Hedefler, jeoloji, doğrulama (Sude dönüşü)

| # | Ne | Belge bölümü | Not |
|---|---|---|---|
| 13 | R-UTO ikiye ayrıldı: R-UTO Viking 2 (47,64 / 134,29, NSSDCA), R-ZHU Zhurong (25,066 / 109,925, Liu ve ark. 2022) | 9.2 | iki iniş yeri ~1600 km uzak |
| 14 | R-OLY = IAU Gazetteer özellik merkezi; sitede "feature centre" | 9.2 | "zirve" denmez |
| 15 | R-JEZ belge değeri 18,44 / 77,45 kaldı (Wikipedia hassas değeri kullanılmadı) | 9.2 | kaynak: JPL basın kiti + belge |
| 16 | GLiM pb = gabro, norit, peridotit (Hartmann & Moosdorf 2012, Ek A4.1.4, para. [71]); anortozit geçmez; Ay → pb eşlemesi değişmez, gerekçe cümlesi düzeltildi | 6.3, 13.3 | açık kontrol kısmen kapandı |
| 17 | lApd (kutup kumulları), Hpe (kutup yapıları), Nhe (yayla yapıları) ön kayıtlı kurala göre gruplandı (DMU tanımından farklı) | 6.3, L12 | Limitations cümlesi |
| 18 | V1: 11 çiftin hepsi kaynakla tutuyor; JETT5 NTRS kimliği doğrulanamadı → makalede yalnız USGS kaynağıyla atıf; Dumont Dunes 11 Mayıs haber tarihi; JETT1 kesin tarih yok | 9.3 | onaylı (Sude) |

## 5. Implementation (yöntem aynı; makale Bölüm 8 için)

- Hücre ortalaması (4.4): hücreden ince katmanda hücre içinde s × s alt nokta (piksel kenarı başına ≥ 2, s ≤ 10) → alan ağırlıklı piksel ortalaması.
- Vektör jeoloji (4.4): her pencerede hücre başına 5 × 5 nokta, poligon içi testi (shapely, hazırlanmış poligon). GLiM rasterleştirilmedi.
- Topografya (6.1): "2 hücre dışarıdan" her ölçekte → DEM 8 ince hücre dışından okunur (2 km'de 2 blok).
- F⁻¹ (5.1): ECDF genelleştirilmiş tersi, k = ⌈n(2m − 1)/2M⌉ tam sayı aritmetiğiyle.
- SW doğrultuları orta nokta θ_j = −π/2 + (j − ½)π/Mθ.
- Diviner PRP hücreye: en yakın üçgen merkezi, ortanca komşu aralığının 3 katı eşik (proje kararı, onaylı Sude 12:17), arama eşikle sınırlı.
- H₀: GUDHI CubicalComplex; bağımsız union-find (8-komşuluk) ile 203 pencerede birebir aynı.
- Berger f(φ): 0,001° tablo + doğrusal ara değer (ölçülen en büyük hata 1,2e-9).

## 6. Bekleyen ölçüm (Sude Limitations cümlesini yazacak)

- I⊕: ΔTg < 1 K olan geçerli ayı bulunan piksel oranı 0,329 (2 913 886 / 8 638 888). I⊕ yüzdelikleri: %1 0,0112; %50 0,0541; %99 0,5152; %99,9 3,9962 (`kayit\iarti_teshis.json`).
- Ek ölçümler (en büyük ayın yıllık toplamdaki payı; |u_ort − u_ortanca|; en büyük farkın 10 pikseli) → `kayit\iarti_olcum.json`.

## 7. Son gönderimden sonra eklenenler (12:17'den itibaren)

| # | Ne | Belge bölümü | Durum | Not |
|---|---|---|---|---|
| 19 | Madde 5 "Terra ~10:30" düzeltmesi önerildi, uygulanmadı: veri MYD11C3 (Aqua, ~13:30 / ~01:30) | 6.5, D1 | Sude'ye bildirildi | Limitations'taki I⊕ cümlesinde Terra etkisi yazılmaz |
| 20 | K-1: kapılarda W° "kara hücresi" = kara payı ≥ 0,5 (madde 9 ile aynı) | 7.2 | onaylı, proje kararı (Sude) | — |
| 21 | K-2: Pv için 12 aylık ASTER NDVI → yıllık ortalama (geçerli aylar) → Pv; pencerede **ortanca** (belge 7.2 açıkça "medyan_{W°} P_v" diyor) | 7.2 | onaylı (Sude) | yıllık en büyük kullanılmaz (yağmur sonrası yeşeren çöller) |
| 22 | K-3: Geology kapısında kar/buz payı = W° üzerinde ortalama | 7.2 | onaylı (Sude) | alan payının beklenen değeri |
| 23 | K-4: hedefte verisi olmayan kategori iki taraftan da çıkar; "en fazla 1 eksik" yalnız hedefin verisi olan kategoriler üzerinden | 7.2 | onaylı (Sude) | — |
| 24 | K-5: X'in leave-one-out'u yalnız V1'in kendi Geology satırlarında; diğer hedeflerde X = 7 Geology çiftinin hepsiyle | 7.2, D7 | onaylı (Sude) | — |
| 25 | Gözlem: Ice kapısı (G_buz) yalnız permafrost ortalaması; kar/buz < 0,5 şartı yalnız Geology'de. Grönland/Antarktika içi (kar/buz ≥ 0,5 hücreleri sıfır kuralında hesap dışı) Ice'ta "could not be checked" ile geçer (belge 7.2 kural 2) | 7.2 | kayda yazıldı, değişiklik yok | sonuç tablosunda görünecek |

## 8. Açık sorular (onele / puan / teorem / dogrula) — 12:25 soruldu, 12:33 cevaplandı

Hepsi KAYNAK YOK — onay gerekir. Öneri İrem/Claude'un; karar ekibin.

| # | Soru | Belge | Öneri | Karar |
|---|---|---|---|---|
| Q-1 | z'de MAD = 0 ise | 7.1 | O bileşende Rousseeuw–Croux Qn [96]; Qn de 0 ise bileşen çıkar | **Değişti (Sude):** Qn kullanılmaz (Qn'nin de dayanma sınırı %50, aynı durumda 0 çıkar); MAD = 0 olan bileşen z'den çıkar, kayda yazılır. z yalnız ön elemede; kaybı V5 ölçer |
| Q-2 | Kategori şampiyonu hangi kümeden | 7.4 | E_K(T, g) içindeki uygun adaylar; k = 2 için son 30 aday | onaylı (Sude) |
| Q-3 | V2 "sınıf 2 ≥ %90" düzeyi | 8.3, D6 | Pencere ortalaması MCD12C1 sınıf payı ≥ %90 | onaylı (Sude) |
| Q-4 | V4/V5 "rastgele 200 hedef" cismi | 8.3 | 100 Ay + 100 Mars ızgara penceresi, tohum 20261113 (alt tohum V4/V5) | onaylı (Sude) |
| Q-5 | V5 tam sıralama topoloji dahil mi | 8.3, 7.4 | Topolojisiz (V1 gibi), iki taraf aynı puan | onaylı (Sude) |
| Q-6 | V7 gürültü nereye | 8.3 | Yalnız hedef + 20 komşusunun DEM'i; Dünya tarafı sabit; liste hedeflerinin hepsi | onaylı (Sude) |
| Q-7 | V6 "bütün (E, T) çiftleri" | 8.3 | Liste hedefleri × E_K adayları (8 s_k'nin hepsi olan) | onaylı (Sude) |
| Q-8 | ε* ikiye bölme hassasiyeti | 8.1 | 0,01 m; aralık σv'den başlayıp ikiye katlanır (≤ 10⁵ m) | onaylı (Sude); sınıra kadar bulunamazsa kayda "bulunamadı" |

## 9. Dış inceleme (12:33) — maddeler ve durumu

| # | Bulgu | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 26 | Makale v0.5'te "I⊕ = C₁/ΔT (MOD11C3 in v1.0)", "Aqua replaces Terra", "Replaces MOD11C3 (Terra) of v1.0" yazıyor; belge D1 ise bunu kaynakça hatası diyor. Bugünkü koşu MYD11C3 (testle doğrulandı). | D1, D12 | Hayır | Makaledeki sonuçlar v1.2 koşusundan gelecek; D12 gereği v1.0 karşılaştırma cümleleri makaleden çıkar (Emir/Sude) |
| 27 | Aqua gece geçişi 01:30, günlük minimum gün doğumuna yakın → ΔTg = T₁₃:₃₀ − T₀₁:₃₀ < T_max − T_min → I⊕ olduğundan büyük | 6.5 | Hayır | Limitations cümlesi sapmanın yönünü söyler (Sude) |
| 28 | Puan sıra tabanlı: her yerde aynı oranda sapma sırayı değiştirmez; etkiyi yalnız yerden yere değişen sapma yapar (tarama açısı, enlem, açık gün seçimi) | 5.2, 6.5 | Hayır | Limitations cümlesi "olduğundan büyük" yerine bunu söyler (Sude) |
| 29 | **I⊕ yıllık değeri: oranların ortalaması (belge) küçük paydalı aylara duyarlı; öneri: ortalamaların oranı Σ C₁(1−α) / Σ ΔTg ya da aylık ortanca.** MI'de "önce ortalama" gerekçesi burada da geçerli | 6.5 | **Evet** (yalnız ozellik_diger I⊕ formülü; teorem/onele/puan değil) | **EKİP KARARI, D8'den önce**, iarti_olcum.json ile, sonuçlara bakılmadan |
| 30 | Pv'de ortanca: Pv NDVI'nin azalmayan fonksiyonu → medyan Pv < 0,5 ⇔ medyan NDVI < 0,2 + 0,3√0,5 ≈ 0,412; belgedeki "NDVI < 0,41" cümlesi tam doğru | 7.2 | Hayır | Method'a gerekçe olarak (Emir) |
| 31 | Buz tabakası pencereleri Ice kapısından "could not be checked" geçer, s₆ tanımsız, ağırlık termal/aydınlanmaya kayar → Ay kutup hedeflerinde üst sıralara çıkabilir. Kavramsal soru: buz tabakası "donmuş zemin" mi? | 6.6, 7.2 | Şimdi hayır | Koşudan sonra Ice Top-3/ilk 10'da "could not be checked" oranı ozet.json'a otomatik yazılır; yorum ekip |
| 32 | Madde 8 (PGDA/Berger) gerekçesi: bu "cisim içi sıra"nın kendisi değil; Ay iki referansa bölünüyor, 65°'de süreksizlik (64,9° ve 65,1° çok farklı sıra alabilir) | 6.8 | Hayır | Limitations cümlesi süreksizliği açıkça söyler (Sude) |
| 33 | Sude'nin numaralandırması kayıttakiyle farklı ("6. MI" = madde 7, "7. aydınlanma" = 8, "8." = 9 ve 10) | — | Hayır | Bu belgede numaralar düzeltilmiş halde |

## 10. teorem.py (12:45)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 34 | Lemma 1 (a)–(e), Ψ₁, Ψ₂ ve Teorem 1 sayısal testten geçti (rastgele DEM + |e| ≤ ε; sınırlar her tekrarda tuttu; 0,9·ε* gürültüde s₁ sırası değişmedi). **Erken uyarı:** sentetik arazide ε*₁ ≈ 0,02–2 mm (σv = 7,17 m). Ψ₁'i H₄ terimi büyütüyor (IQR_T(H₄) ~1e-5). Gerçek dağılım D6/uzun koşuda (F15) | 8.1 | Hayır | Emir: "güvenli hata yarıçapı ölçülür ve raporlanır" cümlesini büyüklükten bağımsız doğru kalacak biçimde yazar; sayılar ozet.json'dan |
| 35 | ε* < 0,01 m (Q-8 hassasiyeti) ise kayda "0,01 m'den küçük" yazılır (0 yalnız gerçek eşitlikte) | 8.1, Q-8 | Hayır (kayıt biçimi) | — |

## 11. onele.py (12:55)

| # | Ne | Belge | Kodu etkiler mi | Durum / kim |
|---|---|---|---|---|
| 36 | Q-1 uygulandı: MAD = 0 olan z bileşeni çıkar; hangi bileşenin çıktığı `ozet.json`'a yazılır. **Olası durum:** n↓ ve n↑ sayım; Dünya pencerelerinin yarısından fazlasında aynı değer (ör. 0) çıkarsa MAD = 0 olur ve bileşen düşer. Sonuç P4'te görülür | 7.1, Q-1 | Hayır (karar onaylı) | makalede "z'den çıkan bileşenler" cümlesi ozet.json'dan |
| 37 | Okuma (formül aynı): z'si eksik (NaN) Dünya penceresi KD-ağacına girmez, sayısı kayda yazılır. Bu yalnız DEM'i eksik pencerelerde olur; bunlar topoloji kategorisi olmadığı için zaten uygun değil (7.2). Aynı uzaklıkta pencere kimliği küçük olan önce | 7.1, 7.2 | Hayır | kayda yazıldı |
| 38 | **Q-9 (onaylı, proje kararı, Sude 12:51):** V5'te {100, 200, 400, 800} hiçbiri ortalama recall ≥ 0,9 sağlamazsa Kön = 800 (denenenlerin en büyüğü), koşu durmaz. Listeye yeni değer eklenmez (sonuçtan sonra ayarı genişletmek önceden kilitleme ilkesine aykırı) | 7.1, 8.3 V5 | onele.kon_sec → (K, eşik sağlandı mı) | makaleye "recall did not reach 0.9 (mean ± CI)" sınırlılığı; ozet.json'da bayrak |
| 39 | **Q-10 (onaylı, proje kararı, Sude 12:51):** şart ortalama recall'a (r̄) uygulanır. GA = r̄ ± 1,96 s_d/√200 (s_d örneklem std, ddof = 1) hesaplanır, ozet.json'a yazılır; r̄ ≥ 0,9 ama alt uç < 0,9 ise makalede tek cümleyle belirtilir | 8.3 V5 | onele.recall_ozet | — |
| 40 | Hedef penceresinin z'sinde (tutulan bileşende) NaN varsa ön eleme yapılmaz, hata verir (sessiz karar yok). Ay/Mars DEM'leri küresel tam olduğu için beklenmiyor; olursa pilotta görülür | 7.1 | Hayır | kayda yazıldı |
''', encoding="utf-8")
yol = KOD / "FONKSIYONLAR.md"; metin = yol.read_text(encoding="utf-8")
eski = "- 7.1 / 8.3 V5 Kön seçimi → `onele.kon_sec`"
assert eski in metin
yol.write_text(metin.replace(eski, "- 7.1 / 8.3 V5 Kön seçimi (Q-9, Q-10) → `onele.kon_sec`; r̄ ± 1,96 s_d/√n → `onele.recall_ozet`"), encoding="utf-8")
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | onele.kon_sec: Q-9 hiçbir K r̄ ≥ 0,9 değilse 800 + bayrak, liste genişletilmez; Q-10 şart ortalama recall'a, GA (ddof = 1) hesaplanır (Sude onaylı 12:51) | etkisi: MAKALEYİ ETKİLER 38–39\n")
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_onele", "testler/test_onele.py")
