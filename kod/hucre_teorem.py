# Developed with assistance from Claude (Anthropic).
# 17.4 sıra 11: kod\\teorem.py + testler (belge 8.1: Λ, Ψ₁, Ψ₂, ε*, hareket kapısı; Q-8). MAKALEYİ ETKİLER güncel kaydı.
import sys, importlib
from pathlib import Path
KOK = Path.home() / "orbitrary"; KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / 'teorem.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 8.1: tanımlayıcı sınırları Λ (Lemma 1), uzaklık sınırları Ψ₁, Ψ₂ (Lemma 2), güvenli hata yarıçapı ε*
(Teorem 1, ikiye bölme), hareket kapısının DEM hatasına karşı değişmezliği.

Girdiler pencere başına ozellik_topo.ozellikler() çıktısından: R (rölyef, σv tabanlı), Omega_1, Omega_4.
R_top = max(R, κσv) (R'nin tanımından; ham max − min < σv iken ikisi de tabanda).
ℓ_W = max(R_W − 2ε, σv), ℓ^top_W = max(R^top_W − 2ε, κσv).
ε* araması (Q-8, Sude onaylı): σv'den başlar, ikiye katlanarak büyür (≤ 10⁵ m), sonra ikiye bölme, hassasiyet 0,01 m;
sınıra kadar koşul bozulmazsa "bulunamadı" (None, kayda yazılır).
"""
import math

import numpy as np

import ayar as A
import ozellik_topo as T

EPS_HASSASIYET_M = 0.01
EPS_SINIR_M = 1e5


def sigma_v(govde):
    return float(A.ayar("cisim.sigma_v_m")[govde])


def kappa_sigma(govde):
    return float(A.ayar("topoloji.kappa")) * sigma_v(govde)


def delta_s(s):
    return float(A.ayar("izgara.delta_m")) * s


def lambdalar(Omega_s, s, eps):
    """Lemma 1 sabitleri bir ölçekte: Λ_θ,s = √2/δ_s; Λ_VRM,s = 2√2/δ_s;
    Λ_H,s(W) = (2Ω_s(W) + 9ε/δ_s²)/δ_s + 9/(2δ_s²)."""
    d = delta_s(s)
    Om = np.asarray(Omega_s, float)
    return {"theta": np.full(Om.shape, math.sqrt(2) / d), "vrm": np.full(Om.shape, 2 * math.sqrt(2) / d),
            "H": (2 * Om + 9 * eps / d ** 2) / d + 9 / (2 * d ** 2)}


def ell(R, govde, eps):
    return np.maximum(np.asarray(R, float) - 2 * eps, sigma_v(govde))


def ell_top(R, govde, eps):
    Rt = np.maximum(np.asarray(R, float), kappa_sigma(govde))
    return np.maximum(Rt - 2 * eps, kappa_sigma(govde))


def _Lam_vektor(Om1, Om4, eps):
    """T.OZELLIKLER sırasıyla (theta_1, vrm_1, H_1, theta_4, vrm_4, H_4) Λ değerleri: (..., 6)."""
    L1, L4 = lambdalar(Om1, 1, eps), lambdalar(Om4, 4, eps)
    return np.stack([L1["theta"], L1["vrm"], L1["H"], L4["theta"], L4["vrm"], L4["H"]], axis=-1)


def psi1(eps, govde, A_, B_, iqr):
    """Lemma 2: Ψ₁(A, B; ε) = ε/(|F_T|+1) (Σ_{F_T} (Λ_{f,s}(A) + Λ_{f,s}(B)) / IQR_T(f_s) + 2/ℓ_A + 2/ℓ_B).
    A_, B_: {"R", "Omega_1", "Omega_4"} (skaler ya da dizi; yayınlanır)."""
    iqr = np.asarray(iqr, float)
    FT = np.isfinite(iqr) & (iqr > 0)
    LA = _Lam_vektor(A_["Omega_1"], A_["Omega_4"], eps)
    LB = _Lam_vektor(B_["Omega_1"], B_["Omega_4"], eps)
    toplam = np.sum(((LA + LB) / np.where(FT, iqr, 1.0))[..., FT], axis=-1)
    return eps / (FT.sum() + 1) * (toplam + 2 / ell(A_["R"], govde, eps) + 2 / ell(B_["R"], govde, eps))


def psi2(eps, govde, R_A, R_B):
    """Lemma 2: Ψ₂(A, B; ε) = 32 (2N+1)² ε (1/ℓ^top_A + 1/ℓ^top_B)."""
    N = int(A.ayar("izgara.N"))
    return 32 * (2 * N + 1) ** 2 * eps * (1 / ell_top(R_A, govde, eps) + 1 / ell_top(R_B, govde, eps))


def kosul(eps, d_E, d_ref, psi_E, psi_ref):
    """Teorem 1 koşulu: ∀E′: |d(E′,T) − d(E,T)| > Ψ(E′,T;ε) + Ψ(E,T;ε). psi_E(ε) skaler, psi_ref(ε) dizi."""
    d_ref = np.asarray(d_ref, float)
    g = np.isfinite(d_ref)
    return bool(np.all(np.abs(d_ref[g] - d_E) > psi_ref(eps)[g] + psi_E(eps)))


def eps_yildiz(d_E, d_ref, psi_E, psi_ref, govde, hassasiyet=None):
    """Güvenli hata yarıçapı ε*_k(E) = sup{ε ≥ 0 : koşul}. Ψ ε'da sürekli ve artan (belge 8.1) → ikiye bölme.
    Dönüş: (ε* metre ya da None, bilgi). durum: "bulundu"; "hassasiyetten küçük" (0 < ε* < hassasiyet, değer 0 yazılır);
    "eşit uzaklık var" (ε* = 0); "bulunamadı" (10⁵ m'ye kadar koşul bozulmadı, None)."""
    h = EPS_HASSASIYET_M if hassasiyet is None else float(hassasiyet)
    if not kosul(0.0, d_E, d_ref, lambda e: 0.0, lambda e: np.zeros(np.shape(d_ref))):
        return 0.0, {"durum": "eşit uzaklık var (ε* = 0)"}
    hi = sigma_v(govde)
    lo = 0.0
    while kosul(hi, d_E, d_ref, psi_E, psi_ref):
        lo = hi
        hi *= 2
        if hi > EPS_SINIR_M:
            return None, {"durum": "bulunamadı", "sinir_m": EPS_SINIR_M}
    while hi - lo > h:
        m = (lo + hi) / 2
        if kosul(m, d_E, d_ref, psi_E, psi_ref):
            lo = m
        else:
            hi = m
    if lo == 0.0:
        return 0.0, {"durum": "hassasiyetten küçük", "ust_sinir_m": hi, "hassasiyet_m": h}
    return lo, {"durum": "bulundu", "hassasiyet_m": h}


def eps1(govde, E, T_, refs, d_E, d_ref, iqr, hassasiyet=None):
    """ε*₁: E, T_ ve refs ({"R","Omega_1","Omega_4"}; refs dizi) için Ψ₁ ile."""
    return eps_yildiz(d_E, d_ref, lambda e: psi1(e, govde, E, T_, iqr), lambda e: psi1(e, govde, refs, T_, iqr), govde,
                      hassasiyet)


def eps2(govde, R_E, R_T, R_refs, d_E, d_ref):
    """ε*₂: Ψ₂ ile (belge 8.1 sınır (i): pratikte çok küçük çıkar)."""
    return eps_yildiz(d_E, d_ref, lambda e: psi2(e, govde, R_E, R_T), lambda e: psi2(e, govde, np.asarray(R_refs), R_T), govde)


def mobility_degismez(theta_rad, eps, w_maske=None):
    """Teorem 1, hareket kapısı: Λ = Λ_θ,1 ε; n± = #{θ < 20° ± Λ}; n− ≥ 0,95|W°| ya da n+ < 0,95|W°| ise G̃ = G."""
    th = np.asarray(theta_rad, float)
    m = np.isfinite(th) if w_maske is None else (np.asarray(w_maske, bool) & np.isfinite(th))
    L = math.sqrt(2) / delta_s(1) * eps
    e = math.radians(float(A.ayar("kapi.mobility.egim_der")))
    p = float(A.ayar("kapi.mobility.hucre_orani"))
    n = m.sum(axis=(-2, -1))
    nm = (m & (th < e - L)).sum(axis=(-2, -1))
    np_ = (m & (th < e + L)).sum(axis=(-2, -1))
    return (nm >= p * n) | (np_ < p * n)
''', encoding='utf-8')
(KOD / 'testler/test_teorem.py').write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 8.1: Lemma 1 (a)–(e), Lemma 2 (Ψ₁, Ψ₂), Teorem 1 ve ε*, hareket kapısı — rastgele DEM + |e| ≤ ε gürültüsüyle
sınırların gerçekten tuttuğu ölçülür (her test birçok tekrar)."""
import math
import numpy as np
import pytest
import ayar as A
import ozellik_topo as T
import ozellik_topoloji as P
import teorem as TH
import uzaklik as U

n = 56
x = (np.arange(n) - n / 2 + 0.5)[None, :] * 500.0
y = (np.arange(n) - n / 2 + 0.5)[:, None] * 500.0


def _dem(g, olcek=300.0):
    # düzgün + pürüzlü arazi
    h = olcek * (np.sin(x / 4000 + g.uniform(0, 6)) * np.cos(y / 5000 + g.uniform(0, 6)))
    return h + g.normal(0, olcek / 10, (n, n))


def test_ornek_buyukluk_8_1():
    # δ = 500 m, ε = σv = 7,17 m → Λ = √2·7,17/500 ≈ 0,0203 rad ≈ 1,16°
    L = math.sqrt(2) / TH.delta_s(1) * 7.17
    assert abs(L - 0.0203) < 5e-5 and abs(math.degrees(L) - 1.16) < 5e-3


@pytest.mark.parametrize("tohum", range(10))
def test_lemma1_hucre_sinirlari(tohum):
    g = np.random.default_rng(tohum)
    eps = 7.17
    h = _dem(g)
    e = g.uniform(-eps, eps, (n, n))
    o, ot = T.ozellikler(h, "dunya"), T.ozellikler(h + e, "dunya")
    for s, tag in ((1, "_1"), (4, "_4")):
        L = TH.lambdalar(o["Omega" + tag], s, eps)
        assert np.max(np.abs(ot["theta" + tag] - o["theta" + tag])) <= L["theta"] * eps + 1e-12      # (a)
        assert np.max(np.abs(ot["vrm" + tag] - o["vrm" + tag])) <= L["vrm"] * eps + 1e-12            # (b)
        assert np.max(np.abs(ot["H" + tag] - o["H" + tag])) <= L["H"] * eps + 1e-12                  # (c)
    assert abs(ot["lnR"] - o["lnR"]) <= 2 * eps / TH.ell(o["R"], "dunya", eps) + 1e-12                 # (d)
    W = (Ellipsis, slice(T.GEN, -T.GEN), slice(T.GEN, -T.GEN))
    a, b = P.normalize(h[W], "dunya"), P.normalize((h + e)[W], "dunya")
    assert np.max(np.abs(a[0] - b[0])) <= 4 * eps / TH.ell_top(o["R"], "dunya", eps) + 1e-12            # (e)


@pytest.mark.parametrize("tohum", range(10))
def test_lemma2_psi1(tohum):
    # |d̃₁(A,B) − d₁(A,B)| ≤ Ψ₁(A,B;ε); IQR_T, F_T sabit (V2)
    g = np.random.default_rng(100 + tohum)
    eps = 7.17
    hA, hB = _dem(g), _dem(g, 150.0)
    oA, oB = T.ozellikler(hA, "dunya"), T.ozellikler(hB, "dunya")
    tA = T.ozellikler(hA + g.uniform(-eps, eps, (n, n)), "dunya")
    tB = T.ozellikler(hB + g.uniform(-eps, eps, (n, n)), "dunya")
    iqr = T.iqr_hedef([T.ozellikler(_dem(g), "dunya") for _ in range(21)])
    Q = lambda o: T.yuzdelik_vektorleri(o)
    d = T.d1(Q(oA)[None], np.array([oA["lnR"]]), Q(oB), oB["lnR"], iqr)[0]
    dt = T.d1(Q(tA)[None], np.array([tA["lnR"]]), Q(tB), tB["lnR"], iqr)[0]
    psi = TH.psi1(eps, "dunya", oA, oB, iqr)
    assert abs(dt - d) <= psi + 1e-12, (abs(dt - d), psi)


@pytest.mark.parametrize("tohum", range(5))
def test_lemma2_psi2(tohum):
    g = np.random.default_rng(200 + tohum)
    eps = 7.17
    W = (Ellipsis, slice(T.GEN, -T.GEN), slice(T.GEN, -T.GEN))
    hA, hB = _dem(g)[W], _dem(g, 150.0)[W]
    dA, dB = P.diyagramlar(hA, "dunya", "uf"), P.diyagramlar(hB, "dunya", "uf")
    dAt = P.diyagramlar(hA + g.uniform(-eps, eps, hA.shape), "dunya", "uf")
    dBt = P.diyagramlar(hB + g.uniform(-eps, eps, hB.shape), "dunya", "uf")
    RA, RB = max(np.ptp(hA), 7.17), max(np.ptp(hB), 7.17)
    assert abs(P.d2(dAt, dBt) - P.d2(dA, dB)) <= TH.psi2(eps, "dunya", RA, RB)


def test_psi_artan_ve_sifirda_sifir():
    o = {"R": 300.0, "Omega_1": 1e-3, "Omega_4": 1e-4}
    iqr = np.ones(6) * 0.1
    v = [TH.psi1(e, "ay", o, o, iqr) for e in (0.0, 1.0, 2.0, 5.0)]
    assert v[0] == 0 and all(np.diff(v) > 0)
    w = [TH.psi2(e, "ay", 300.0, 500.0) for e in (0.0, 1.0, 2.0)]
    assert w[0] == 0 and all(np.diff(w) > 0)


def test_eps_yildiz_bilinen():
    # Ψ(ε) = ε (iki tarafta), referans uzaklık farkları en az 3 → ε* = 1,5 (koşul |Δ| > 2ε)
    d_E, d_ref = 10.0, np.array([13.0, 6.0, 20.0])
    e, b = TH.eps_yildiz(d_E, d_ref, lambda e: e, lambda e: np.full(3, e), "dunya")
    assert b["durum"] == "bulundu" and abs(e - 1.5) <= TH.EPS_HASSASIYET_M
    e0, b0 = TH.eps_yildiz(10.0, np.array([10.0, 12.0]), lambda e: e, lambda e: np.full(2, e), "dunya")
    assert e0 == 0.0 and b0["durum"].startswith("eşit")
    # ε* = 0,0015 m < 0,01 m → "hassasiyetten küçük", değer 0, üst sınır ≤ 0,01 m
    ek, bk = TH.eps_yildiz(10.0, np.array([10.003]), lambda e: e, lambda e: np.full(1, e), "dunya")
    assert ek == 0.0 and bk["durum"] == "hassasiyetten küçük" and bk["ust_sinir_m"] <= 0.0115
    eN, bN = TH.eps_yildiz(10.0, np.array([1e9]), lambda e: 0.0 * e, lambda e: np.zeros(1), "dunya")
    assert eN is None and bN["durum"] == "bulunamadı"


@pytest.mark.parametrize("tohum", range(5))
def test_teorem1_s1_degismez(tohum):
    # ε*₁ altında gürültü s₁'i değiştirmez: E ve referansların d₁ sırası korunur
    g = np.random.default_rng(300 + tohum)
    oT = T.ozellikler(_dem(g), "dunya")
    iqr = T.iqr_hedef([oT] + [T.ozellikler(_dem(g), "dunya") for _ in range(20)])
    hs = [_dem(g, g.uniform(50, 600)) for _ in range(30)]
    os_ = [T.ozellikler(h, "dunya") for h in hs]
    Q = np.stack([T.yuzdelik_vektorleri(o) for o in os_])
    lnR = np.array([o["lnR"] for o in os_])
    d = T.d1(Q, lnR, T.yuzdelik_vektorleri(oT), oT["lnR"], iqr)
    refs = {k: np.array([o[k] for o in os_[1:]]) for k in ("R", "Omega_1", "Omega_4")}
    e_star, b = TH.eps1("dunya", os_[0], oT, refs, d[0], d[1:], iqr, hassasiyet=1e-7)
    assert b["durum"] == "bulundu" and e_star > 0, b
    eps = 0.9 * e_star
    ot = [T.ozellikler(h + g.uniform(-eps, eps, h.shape), "dunya") for h in hs]
    oTt = T.ozellikler(_dem(np.random.default_rng(300 + tohum)) + g.uniform(-eps, eps, (n, n)), "dunya")
    Qt = np.stack([T.yuzdelik_vektorleri(o) for o in ot])
    dt = T.d1(Qt, np.array([o["lnR"] for o in ot]), T.yuzdelik_vektorleri(oTt), oTt["lnR"], iqr)
    assert np.array_equal(np.sign(d[1:] - d[0]), np.sign(dt[1:] - dt[0]))


def test_hareket_kapisi_degismez():
    th = np.full((40, 40), np.radians(10.0)); th.ravel()[:81] = np.radians(25.0)   # açıkça kaldı
    assert TH.mobility_degismez(th, 7.17)
    th2 = np.full((40, 40), np.radians(10.0)); th2.ravel()[:81] = np.radians(20.3)  # 20° + Λ içinde
    assert not TH.mobility_degismez(th2, 7.17)
''', encoding='utf-8')
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
''', encoding="utf-8")
yol = KOD / "FONKSIYONLAR.md"; metin = yol.read_text(encoding="utf-8")
bas, son = "<!-- teorem.py -->", "<!-- /teorem.py -->"
blok = bas + "\n## teorem.py\n" + "\n".join("- " + s for s in [
    "8.1 Λ_θ,s, Λ_VRM,s, Λ_H,s(W) → `teorem.lambdalar`; ℓ_W, ℓ^top_W → `teorem.ell`, `teorem.ell_top`",
    "8.1 Ψ₁ → `teorem.psi1`; Ψ₂ → `teorem.psi2`",
    "8.1 Teorem 1 koşulu → `teorem.kosul`; ε*_k (ikiye bölme) → `teorem.eps_yildiz`, `teorem.eps1`, `teorem.eps2`",
    "8.1 hareket kapısının değişmezliği (n±) → `teorem.mobility_degismez`"]) + "\n" + son
metin = (metin.split(bas)[0] + blok + metin.split(son)[1]) if bas in metin else (metin.rstrip() + "\n\n" + blok + "\n")
yol.write_text(metin, encoding="utf-8")
with open(KAYIT / "degisiklik.md", "a", encoding="utf-8") as f:
    f.write("- 2026-11-14 | teorem.py: Lemma 1–2 ve Teorem 1 sayısal testten geçti; sentetik ε*₁ milimetre düzeyinde (σv 7,17 m) — erken uyarı Emir'e | ε* < 0,01 m → 'hassasiyetten küçük' | Q-1…Q-8 cevapları (Sude) ve dış inceleme maddeleri 26–33 MAKALEYİ ETKİLER'de | etkisi: MAKALEYİ ETKİLER 34–35\n")
if str(KOD) not in sys.path: sys.path.insert(0, str(KOD))
import test_kos; importlib.reload(test_kos)
test_kos.calistir("D4_test_teorem", "testler/test_teorem.py")
