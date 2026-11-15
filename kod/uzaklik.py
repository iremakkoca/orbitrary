# Developed with assistance from Claude (Anthropic).
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
