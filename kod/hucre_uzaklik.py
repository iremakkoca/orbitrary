# Developed with assistance from Claude (Anthropic).
# 17.4 sıra 4: kod\\uzaklik.py + testler (belge 5.1–5.3; 8.2 W₁, TV, sıra, u⁺, ters sıra; v1.2 su/buz sırası)
import sys, subprocess, datetime
from pathlib import Path

KOK = Path.home() / "orbitrary"
KOD, KAYIT = KOK / "kod", KOK / "kayit"
(KOD / "uzaklik.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 5.1–5.3: yüzdelik vektörü ve Wasserstein-1, cisim içi sıra u ve u⁺, toplam varyasyon.

- yuzdelik(x): F⁻¹((m − ½)/M), m = 1…M (M = ayar uzaklik.M_yuzdelik); F⁻¹ ECDF'nin genelleştirilmiş tersi
  (inverted_cdf), böylece n = M ise sıralı değerlerin kendisi.
- w1(qa, qb) = (1/M) Σ |qa − qb|; w1_matris: adaylar × referans.
- Sira: u(x) = (#{p : f(p) < x} + ½ #{p : f(p) = x}) / |P|  (belge 5.2)
- SiraPozitif: u⁺(x) = 0 (x ≤ 0); x > 0 için yalnız pozitifler arasında aynı biçim.
- Ters sıra (Ay kaya bolluğu, Mars DCI): 1 − u(x) (belge 5.2, 6.7).
- tv(qa, qb) = ½ Σ_c |qa_c − qb_c|  (belge 5.3)
- referans_orneklem: P_f,B — alanca düzgün rastgele noktaların değerleri, en fazla 10⁶, sabit tohum.
"""
import zlib

import numpy as np

import ayar as A


def M():
    return int(A.ayar("uzaklik.M_yuzdelik"))


def yuzdelik(x, M_=None):
    """Bir pencerenin değerlerinden M noktalı yüzdelik vektörü (NaN'lar atılır; değer yoksa NaN vektör).
    x: (..., n) dizi → (..., M). F⁻¹(q) = x_(k), k = ⌈n · q⌉ (ECDF'nin genelleştirilmiş tersi); q = (2m − 1)/(2M)
    olduğundan k = ⌈n(2m − 1) / 2M⌉ tam sayı aritmetiğiyle hesaplanır (kayan nokta yuvarlaması yok)."""
    M_ = M() if M_ is None else int(M_)
    x = np.asarray(x, dtype=np.float64)
    tek = x.ndim == 1
    x2 = x.reshape(-1, x.shape[-1])
    s = np.sort(x2, axis=1)                       # NaN'lar sona
    n = np.isfinite(x2).sum(axis=1).astype(np.int64)
    pay = n[:, None] * (2 * np.arange(1, M_ + 1, dtype=np.int64) - 1)[None, :]
    k = -(-pay // (2 * M_))                       # ⌈pay / 2M⌉ (1 tabanlı)
    k = np.clip(k - 1, 0, np.maximum(n - 1, 0)[:, None])
    out = np.take_along_axis(s, k, axis=1)
    out[n == 0] = np.nan
    return out[0] if tek else out.reshape(x.shape[:-1] + (M_,))


def w1(qa, qb):
    """Belge 5.1: iki yüzdelik vektörü arasında W₁ = (1/M) Σ |qa − qb| (son eksende)."""
    return np.mean(np.abs(np.asarray(qa, float) - np.asarray(qb, float)), axis=-1)


def w1_matris(Q_aday, Q_ref, parca=256):
    """Adaylar (n, M) × referans (m, M) → (n, m) W₁ matrisi; parça parça (bellek)."""
    Q_aday = np.asarray(Q_aday, np.float64)
    Q_ref = np.asarray(Q_ref, np.float64)
    out = np.empty((Q_aday.shape[0], Q_ref.shape[0]))
    for i in range(0, Q_aday.shape[0], parca):
        out[i:i + parca] = np.mean(np.abs(Q_aday[i:i + parca, None, :] - Q_ref[None, :, :]), axis=2)
    return out


class Sira:
    """Belge 5.2 cisim içi sıra u_f,B(x) (eşitlerde ortalama sıra)."""

    def __init__(self, referans):
        r = np.asarray(referans, dtype=np.float64).ravel()
        r = r[np.isfinite(r)]
        assert r.size > 0, "referans kümesi boş"
        self.r = np.sort(r)
        self.n = self.r.size

    def __call__(self, x):
        x = np.asarray(x, dtype=np.float64)
        sol = np.searchsorted(self.r, x, side="left")
        sag = np.searchsorted(self.r, x, side="right")
        u = (sol + 0.5 * (sag - sol)) / self.n
        return np.where(np.isfinite(x), u, np.nan)

    def ters(self, x):
        """Belge 5.2 / 6.7: ters çevrilen özelliklerde 1 − u(x)."""
        return 1.0 - self(x)


class SiraPozitif:
    """Belge 5.2 yalnız pozitifler arasında sıra u⁺: x ≤ 0 → 0; x > 0 → pozitif referans içinde u."""

    def __init__(self, referans):
        r = np.asarray(referans, dtype=np.float64).ravel()
        r = r[np.isfinite(r)]
        pos = r[r > 0]
        assert pos.size > 0, "pozitif referans yok"
        self.p = np.sort(pos)
        self.n = self.p.size
        self.sifir_orani = float(np.mean(r <= 0)) if r.size else float("nan")

    def __call__(self, x):
        x = np.asarray(x, dtype=np.float64)
        sol = np.searchsorted(self.p, x, side="left")
        sag = np.searchsorted(self.p, x, side="right")
        u = (sol + 0.5 * (sag - sol)) / self.n
        u = np.where(x > 0, u, 0.0)
        return np.where(np.isfinite(x), u, np.nan)


def tv(qa, qb):
    """Belge 5.3: TV = ½ Σ_c |qa_c − qb_c| (son eksen sınıflar). Bir tarafta NaN varsa NaN (null)."""
    qa = np.asarray(qa, float)
    qb = np.asarray(qb, float)
    d = 0.5 * np.sum(np.abs(qa - qb), axis=-1)
    gecersiz = np.isnan(qa).any(axis=-1) | np.isnan(qb).any(axis=-1)
    return np.where(gecersiz, np.nan, d)


def ozellik_rng(ad):
    """P_f,B için özellik başına sabit alt akış: tohum 20261113, alt tohum P_fB, özellik adının CRC32'si."""
    alt = int(A.ayar("alt_tohum")["P_fB"])
    return np.random.default_rng(np.random.SeedSequence(A.TOHUM, spawn_key=(alt, zlib.crc32(ad.encode("utf-8")))))


def kure_noktalari(rng, n, lat_min=-90.0, lat_max=90.0):
    """Küre üzerinde [lat_min, lat_max] bandında alanca düzgün n nokta (derece)."""
    z = rng.uniform(np.sin(np.radians(lat_min)), np.sin(np.radians(lat_max)), n)
    return np.degrees(np.arcsin(z)), rng.uniform(-180.0, 180.0, n)


def referans_orneklem(ad, f, bantlar=((-90.0, 90.0),), n_en_fazla=None, parti=200_000, deneme_carpani=50):
    """P_f,B (belge 5.2): f(lat, lon) → değerler. Bantlar alanlarıyla orantılı çekilir; sonlu değerler toplanır,
    en fazla n_en_fazla (ayar uzaklik.P_fB_en_fazla_piksel). Dönüş: (değerler, bilgi)."""
    n_en_fazla = int(A.ayar("uzaklik.P_fB_en_fazla_piksel")) if n_en_fazla is None else int(n_en_fazla)
    rng = ozellik_rng(ad)
    alan = np.array([np.sin(np.radians(b)) - np.sin(np.radians(a)) for a, b in bantlar])
    assert (alan > 0).all()
    pay = alan / alan.sum()
    toplanan, cekilen = [], 0
    sonlu = 0
    while sonlu < n_en_fazla and cekilen < deneme_carpani * n_en_fazla:
        k = rng.choice(len(bantlar), size=parti, p=pay)
        lat = np.empty(parti)
        lon = np.empty(parti)
        for b in range(len(bantlar)):
            m = k == b
            lat[m], lon[m] = kure_noktalari(rng, int(m.sum()), *bantlar[b])
        v = np.asarray(f(lat, lon), dtype=np.float64).ravel()
        v = v[np.isfinite(v)]
        toplanan.append(v)
        sonlu += v.size
        cekilen += parti
    v = np.concatenate(toplanan)[:n_en_fazla] if toplanan else np.array([])
    return v, {"ad": ad, "cekilen_nokta": int(cekilen), "gecerli": int(v.size),
               "kapsama_orani": float(sonlu / max(cekilen, 1)), "bantlar": [list(b) for b in bantlar]}
''', encoding="utf-8")
(KOD / "testler" / "test_uzaklik.py").write_text(r'''# Developed with assistance from Claude (Anthropic).
"""Belge 8.2: W₁, TV, cisim içi sıra, pozitifler arasında sıra, ters sıra; v1.2 su/buz sırası testi."""
import numpy as np
import pytest
import uzaklik as U


def test_w1_kendisi_ve_kaydirma():
    # 8.2: bir dağılım ile kendisi → 0; bütün değerler 4 kaydırılmış → 4
    x = np.random.default_rng(0).normal(size=1600)
    qa = U.yuzdelik(x)
    assert U.w1(qa, qa) == 0.0
    assert abs(U.w1(qa, U.yuzdelik(x + 4.0)) - 4.0) < 1e-12


def test_w1_esit_uzunluk_sirali_formul():
    # 5.1: eşit uzunluklu sıralı vektörlerde W₁ = (1/n) Σ |x_(l) − y_(l)|  (n = M = 1000)
    g = np.random.default_rng(1)
    x, y = g.normal(size=1000), g.exponential(size=1000)
    assert np.array_equal(U.yuzdelik(x), np.sort(x))
    assert abs(U.w1(U.yuzdelik(x), U.yuzdelik(y)) - np.mean(np.abs(np.sort(x) - np.sort(y)))) < 1e-12


def test_w1_matris():
    g = np.random.default_rng(2)
    A_ = U.yuzdelik(g.normal(size=(7, 1600)))
    B_ = U.yuzdelik(g.normal(size=(5, 1600)))
    m = U.w1_matris(A_, B_, parca=3)
    assert m.shape == (7, 5)
    assert np.allclose(m, [[U.w1(a, b) for b in B_] for a in A_])


def test_yuzdelik_nan():
    x = np.array([np.nan, 1.0, 2.0, np.nan])
    assert np.array_equal(U.yuzdelik(x, 4), [1.0, 1.0, 2.0, 2.0])
    assert np.isnan(U.yuzdelik(np.full(5, np.nan))).all()


def test_tv_8_2():
    # 8.2: (0,84; 0,16; 0) ve (0,10; 0,60; 0,30) → 0,74
    assert abs(U.tv([0.84, 0.16, 0.0], [0.10, 0.60, 0.30]) - 0.74) < 1e-12
    a, b = np.array([0.84, 0.16, 0.0]), np.array([0.10, 0.60, 0.30])
    assert abs((1 - U.tv(a, b)) - np.minimum(a, b).sum()) < 1e-12  # 5.3: 1 − TV = Σ min
    assert np.isnan(U.tv([np.nan, 0.5, 0.5], [0.2, 0.3, 0.5]))


def test_cisim_ici_sira_8_2():
    # 8.2: (1, 1, 2, 3) → u(1) = 0,25; u(2) = 0,625
    u = U.Sira([1, 1, 2, 3])
    assert u(1.0) == 0.25 and u(2.0) == 0.625


def test_pozitifler_arasinda_sira_8_2():
    # 8.2: (0, 0, 1, 1, 2) → u⁺(0) = 0; u⁺(1) = 1/3; u⁺(2) = 5/6
    up = U.SiraPozitif([0, 0, 1, 1, 2])
    assert up(0.0) == 0.0 and abs(up(1.0) - 1 / 3) < 1e-15 and abs(up(2.0) - 5 / 6) < 1e-15


def test_ters_sira_8_2():
    # 8.2: aynı değerler, sıralama ters → 1 − u(x) ters sıraya eşit (çok sayıda eşit değerle)
    g = np.random.default_rng(3)
    r = g.integers(0, 5, 2000).astype(float)
    x = np.array([0.0, 1.0, 2.5, 4.0, -1.0, 7.0])
    assert np.allclose(U.Sira(r).ters(x), U.Sira(-r)(-x))


def test_su_buz_sifir_orani_8_2():
    # v1.2 8.2: Dünya'da sıfır oranı %85'ten %95'e → pozitiflerin sırası değişmez
    g = np.random.default_rng(4)
    pos = g.uniform(0.01, 1.0, 1000)
    r85 = np.concatenate([np.zeros(5667), pos])   # 5667 / 6667 ≈ %85
    r95 = np.concatenate([np.zeros(19000), pos])  # 19000 / 20000 = %95
    x = np.array([0.0, 0.05, 0.3, 0.9])
    assert np.array_equal(U.SiraPozitif(r85)(x), U.SiraPozitif(r95)(x))
    assert U.SiraPozitif(r95).sifir_orani == 0.95


def test_sira_nan_gecer():
    u = U.Sira([1.0, 2.0])
    assert np.isnan(u(np.nan)) and np.isnan(U.SiraPozitif([1.0])(np.nan))


def test_kure_noktalari_alanca_duzgun():
    lat, lon = U.kure_noktalari(np.random.default_rng(5), 400000)
    # z = sin φ düzgün → kuzey ve güney kutup başlıkları (|φ| > 60°) toplam alan payı 1 − sin 60° ≈ 0,134
    assert abs(np.mean(np.abs(lat) > 60) - (1 - np.sin(np.radians(60)))) < 0.003
    assert abs(np.mean(lon > 0) - 0.5) < 0.003


def test_referans_orneklem_tekrar_ve_kapsama():
    f = lambda la, lo: np.where(la > 0, la, np.nan)  # yalnız kuzey yarıküre kapsıyor
    v1, b1 = U.referans_orneklem("deneme", f, n_en_fazla=50000, parti=20000)
    v2, _ = U.referans_orneklem("deneme", f, n_en_fazla=50000, parti=20000)
    assert np.array_equal(v1, v2) and v1.size == 50000 and (v1 > 0).all()
    assert abs(b1["kapsama_orani"] - 0.5) < 0.02
    v3, _ = U.referans_orneklem("baska", f, n_en_fazla=50000, parti=20000)
    assert not np.array_equal(v1, v3)
    vb, bb = U.referans_orneklem("bant", f, bantlar=((70.0, 90.0),), n_en_fazla=10000, parti=5000)
    assert (vb >= 70).all() and bb["kapsama_orani"] == 1.0


@pytest.mark.parametrize("n", [1, 2, 3, 7, 500, 999, 1000, 1001, 1599, 1600, 2000, 4000])
def test_yuzdelik_genellestirilmis_ters(n):
    # F⁻¹(q) = en küçük x: F(x) ≥ q (ECDF); q = (m − ½)/M. Tam kesirlerle (fractions) bağımsız hesap.
    from fractions import Fraction
    g = np.random.default_rng(n)
    x = np.round(g.normal(size=(4, n)), 2)            # eşit değerler de olsun
    x[1, : n // 3] = np.nan                            # bir satırda eksik değer
    Q = U.yuzdelik(x)
    for i in range(4):
        xi = np.sort(x[i][np.isfinite(x[i])])
        N = len(xi)
        for m in (1, 2, 17, 18, 137, 500, 999, 1000):
            q = Fraction(2 * m - 1, 2000)
            k = next(j for j in range(1, N + 1) if Fraction(j, N) >= q)
            assert Q[i, m - 1] == xi[k - 1], (i, m)
''', encoding="utf-8")

yol = KOD / "FONKSIYONLAR.md"
metin = yol.read_text(encoding="utf-8")
bas, son = "<!-- uzaklik.py -->", "<!-- /uzaklik.py -->"
blok = bas + "\n## uzaklik.py\n" + "\n".join("- " + s for s in [
    "5.1 F⁻¹((m − ½)/M), M = 1000 → `uzaklik.yuzdelik`",
    "5.1 W₁ → `uzaklik.w1`; referansa karşı matris → `uzaklik.w1_matris`",
    "5.2 u_f,B(x) → `uzaklik.Sira`; 1 − u (ters) → `uzaklik.Sira.ters`",
    "5.2 u⁺_f,B(x) → `uzaklik.SiraPozitif`",
    "5.2 P_f,B (alanca düzgün, ≤ 10⁶, tohum) → `uzaklik.referans_orneklem`",
    "5.3 TV → `uzaklik.tv`"]) + "\n" + son
metin = (metin.split(bas)[0] + blok + metin.split(son)[1]) if bas in metin else (metin.rstrip() + "\n\n" + blok + "\n")
yol.write_text(metin, encoding="utf-8")

deg = KAYIT / "degisiklik.md"
satirlar = [
    "- 2026-11-14 | Belge 5.2 P_f,B: 'rastgele piksel' alanca düzgün rastgele noktaların piksel değerleri olarak uygulandı (verinin enlem bandıyla sınırlı, ≤ 10⁶, tohum 20261113 + özellik adı) | neden: enlem-boylam ızgarasında piksel seçimi kutupları 1/cos φ kadar fazla ağırlıklandırır; hücreler eşit alanlı | etkisi: Method 5.2 metni\n",
    "- 2026-11-14 | Belge 5.1 F⁻¹: ECDF'nin genelleştirilmiş tersi, k = ⌈n(2m − 1)/2M⌉ tam sayı aritmetiğiyle (numpy quantile'ın kayan nokta yuvarlaması kullanılmadı) | etkisi: yok (tanımın kendisi)\n",
]
d = deg.read_text(encoding="utf-8")
yeni = [s for s in satirlar if s.split(" | ")[1][:25] not in d]
if yeni:
    deg.write_text(d + "".join(yeni), encoding="utf-8")

r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "testler"],
                   cwd=KOD, capture_output=True, text=True)
cikti = r.stdout + r.stderr
(KAYIT / "D4_test_uzaklik.txt").write_text(cikti, encoding="utf-8")
print(cikti[-3000:])
durum = "PASS" if r.returncode == 0 else "FAIL"
with open(KAYIT / "14_kasim_log.txt", "a", encoding="utf-8") as f:
    f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\tuzaklik.py+test_uzaklik\t{durum}\n")
print(f"\ntestler: {durum}")
