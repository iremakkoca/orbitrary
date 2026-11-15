# Developed with assistance from Claude (Anthropic).
"""Belge 6.2 Kategori 2 — Topoloji: ĥ, ȇ normalizasyonu, küpsel H₀ (GUDHI [45]), Sliced Wasserstein (Mθ = 50), d₂.

- R_top = max(max_W h − min_W h, κσv); ĥ = (h − min_W h)/R_top (çukurlar), ȇ = (max_W h − h)/R_top (tepeler).
- Küpsel kompleks: hücreler 2-küp; yüzlerin filtrasyon değeri komşu hücrelerin en küçüğü (GUDHI
  top_dimensional_cells). H₀ diyagramı; sonsuz sınıf ve sıfır kalıcılıklı çiftler çıkarılır.
- SW (belge 6.2, Carrière ve ark. [13]): (1/π) ∫_{−π/2}^{π/2} W₁(ν¹_θ, ν²_θ) dθ ≈ (1/Mθ) Σ_j W₁, θ_j orta noktalar.
  W₁ eşit kütleli sayma ölçüleri arasında sıralı izdüşüm farklarının mutlak değerlerinin TOPLAMI.
  Normalizasyon Carrière ve ark.'nın S¹ üzerindeki (1/2π) tanımıyla aynı (K12 tetiklenmez; testte gösterilir).
- d₂(A, B) = SW(Dgm↓_A, Dgm↓_B) + SW(Dgm↑_A, Dgm↑_B).
- n↓, n↑ (belge 7.1 z): R_top (d − b) ≥ κσv olan nokta sayısı.
Girdi: pencerenin 40 × 40 hücre DEM'i (m), [j, i]. DEM'de NaN varsa topoloji hesaplanmaz (None).
"""
import math

import numpy as np

import ayar as A


def kappa_sigma(govde):
    return float(A.ayar("topoloji.kappa")) * float(A.ayar("cisim.sigma_v_m")[govde])


def normalize(h, govde):
    """(ĥ, ȇ, R_top) ya da DEM eksikse None."""
    h = np.asarray(h, dtype=np.float64)
    if not np.isfinite(h).all():
        return None
    lo, hi = h.min(), h.max()
    Rt = max(hi - lo, kappa_sigma(govde))
    return (h - lo) / Rt, (hi - h) / Rt, Rt


def h0_gudhi(f):
    """GUDHI CubicalComplex (top_dimensional_cells = f) H₀ sonlu çiftleri (b, d), d > b; sonsuz sınıf hariç."""
    import gudhi
    cc = gudhi.CubicalComplex(top_dimensional_cells=np.asarray(f, dtype=np.float64))
    cc.compute_persistence(homology_coeff_field=2, min_persistence=0.0)
    D = np.asarray(cc.persistence_intervals_in_dimension(0), dtype=np.float64).reshape(-1, 2)
    D = D[np.isfinite(D[:, 1]) & (D[:, 1] > D[:, 0])]
    return D[np.lexsort((D[:, 1], D[:, 0]))]


def h0_union_find(f):
    """Bağımsız başvuru: hücreler, 8-komşuluk (köşe paylaşan hücreler o köşede bağlanır), yaşlı kuralı.
    Aynı değerli hücrelerde sıra kararlı (değer, düz indeks)."""
    f = np.asarray(f, dtype=np.float64)
    nj, ni = f.shape
    duz = f.ravel()
    sira = np.lexsort((np.arange(duz.size), duz))
    ata = np.full(duz.size, -1, dtype=np.int64)
    dogum = np.empty(duz.size)

    def bul(a):
        k = a
        while ata[k] != k:
            k = ata[k]
        while ata[a] != k:
            ata[a], a = k, ata[a]
        return k

    ciftler = []
    for p in sira:
        ata[p] = p
        dogum[p] = duz[p]
        j, i = divmod(int(p), ni)
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                if dj == 0 and di == 0:
                    continue
                jj, ii = j + dj, i + di
                if 0 <= jj < nj and 0 <= ii < ni:
                    q = jj * ni + ii
                    if ata[q] < 0:
                        continue
                    ra, rb = bul(p), bul(q)
                    if ra == rb:
                        continue
                    # genç olan (doğumu büyük; eşitse sırada sonra gelen) ölür
                    if (dogum[ra], ra) < (dogum[rb], rb):
                        yasli, genc = ra, rb
                    else:
                        yasli, genc = rb, ra
                    if duz[p] > dogum[genc]:
                        ciftler.append((dogum[genc], duz[p]))
                    ata[genc] = yasli
    D = np.array(ciftler, dtype=np.float64).reshape(-1, 2)
    return D[np.lexsort((D[:, 1], D[:, 0]))]


def diyagramlar(h, govde, yontem="gudhi"):
    """(Dgm↓, Dgm↑, R_top) ya da DEM eksikse None."""
    n = normalize(h, govde)
    if n is None:
        return None
    hh, hc, Rt = n
    f = h0_gudhi if yontem == "gudhi" else h0_union_find
    return f(hh), f(hc), Rt


_YON = {}


def _yonler(M_theta):
    """Belge 6.2 doğrultuları (önbellekli; aynı dizi)."""
    if M_theta not in _YON:
        _YON[M_theta] = _yonler_hesap(M_theta)
    return _YON[M_theta]


def _yonler_hesap(M_theta):
    j = np.arange(1, M_theta + 1)
    th = -math.pi / 2 + (j - 0.5) * math.pi / M_theta
    return np.stack([np.cos(th), np.sin(th)], axis=1)  # (Mθ, 2)


_MT = []


def sw(D1, D2, M_theta=None, yonler=None):
    """Belge 6.2 Sliced Wasserstein."""
    if M_theta is None:
        M_theta = _MT[0] if _MT else _MT.append(int(A.ayar("uzaklik.M_theta"))) or _MT[0]
    M_theta = int(M_theta)
    E = _yonler(M_theta) if yonler is None else yonler
    D1 = np.asarray(D1, float).reshape(-1, 2)
    D2 = np.asarray(D2, float).reshape(-1, 2)
    if D1.shape[0] == 0 and D2.shape[0] == 0:
        return 0.0
    P1 = np.concatenate([D1, np.repeat(((D2[:, 0] + D2[:, 1]) / 2)[:, None], 2, axis=1)], axis=0)
    P2 = np.concatenate([D2, np.repeat(((D1[:, 0] + D1[:, 1]) / 2)[:, None], 2, axis=1)], axis=0)
    a = np.sort(P1 @ E.T, axis=0)
    b = np.sort(P2 @ E.T, axis=0)
    return float(np.mean(np.sum(np.abs(a - b), axis=0)))


def d2(dA, dB):
    """d₂(A, B) = SW(↓) + SW(↑); dA, dB = (Dgm↓, Dgm↑, R_top). Biri None ise None (null)."""
    if dA is None or dB is None:
        return None
    return sw(dA[0], dB[0]) + sw(dA[1], dB[1])


def n_onemli(d, govde):
    """Belge 7.1: (n↓, n↑) = R_top (d − b) ≥ κσv olan nokta sayıları."""
    if d is None:
        return (np.nan, np.nan)
    Dd, Du, Rt = d
    e = kappa_sigma(govde)
    return (int(np.sum(Rt * (Dd[:, 1] - Dd[:, 0]) >= e)), int(np.sum(Rt * (Du[:, 1] - Du[:, 0]) >= e)))
