# Developed with assistance from Claude (Anthropic).
"""Belge 6.1 Kategori 1 — Topografya: Horn eğimi, VRM, ortalama eğrilik H, rölyef R, iki ölçek, IQR, d₁.

Girdi: pencere DEM'i h, biçim [..., j, i] (j kuzey, i doğu), pencerenin GEN = 8 hücre dışından okunmuş
(56 × 56): belge 6.1 "kenar hücreleri için 2 hücre dışarıdan" kuralı her ölçekte (500 m'de 2 hücre,
2 km'de 2 blok = 8 hücre).
- s = 1: δ₁ = 500 m, ortadaki 44 × 44 → türevler 42 × 42 → θ, H, VRM 40 × 40.
- s = 4: h⁽⁴⁾_IJ = 4 × 4 blok ortalaması (bloklar pencere hücreleriyle hizalı), 14 × 14 → 10 × 10, δ₄ = 2 km.
Birimler: θ radyan, VRM birimsiz, H 1/m, h ve R metre.
"""
import numpy as np

import ayar as A
import uzaklik as U

GEN = 8  # ince hücre cinsinden okuma genişletmesi
OZELLIKLER = ["theta_1", "vrm_1", "H_1", "theta_4", "vrm_4", "H_4"]  # F_T adayları (f, s)


def delta_m(s):
    return float(A.ayar("izgara.delta_m")) * s


def turevler(h, d):
    """Belge 6.1 Horn birinci türevleri [51] ve ikinci türevler [127]; iç bölge (her kenardan 1 hücre eksik)."""
    c = h[..., 1:-1, 1:-1]
    E, W = h[..., 1:-1, 2:], h[..., 1:-1, :-2]
    N, S = h[..., 2:, 1:-1], h[..., :-2, 1:-1]
    NE, NW = h[..., 2:, 2:], h[..., 2:, :-2]
    SE, SW = h[..., :-2, 2:], h[..., :-2, :-2]
    hx = ((NE + 2 * E + SE) - (NW + 2 * W + SW)) / (8 * d)
    hy = ((NE + 2 * N + NW) - (SE + 2 * S + SW)) / (8 * d)
    hxx = (E - 2 * c + W) / d ** 2
    hyy = (N - 2 * c + S) / d ** 2
    hxy = (NE - NW - SE + SW) / (4 * d ** 2)
    return hx, hy, hxx, hyy, hxy


def egim(hx, hy):
    """θ = arctan √(h_x² + h_y²) (radyan)."""
    return np.arctan(np.sqrt(hx ** 2 + hy ** 2))


def vrm(hx, hy):
    """VRM_ij = 1 − (1/9) ‖Σ_{3×3} n‖, n = (−h_x, −h_y, 1)/√(1 + h_x² + h_y²). Girdi kenarından 1 hücre eksik çıkar."""
    nrm = np.sqrt(1 + hx ** 2 + hy ** 2)
    n = np.stack([-hx / nrm, -hy / nrm, 1.0 / nrm], axis=-1)
    t = sum(n[..., 1 + a: n.shape[-3] - 1 + a, 1 + b: n.shape[-2] - 1 + b, :] for a in (-1, 0, 1) for b in (-1, 0, 1))
    return 1.0 - np.linalg.norm(t, axis=-1) / 9.0


def egrilik(hx, hy, hxx, hyy, hxy):
    """Ortalama eğrilik H (z = h(x, y)); H > 0 çukur, H < 0 tümsek."""
    D = 1 + hx ** 2 + hy ** 2
    return ((1 + hy ** 2) * hxx - 2 * hx * hy * hxy + (1 + hx ** 2) * hyy) / (2 * D ** 1.5)


def blok4(h):
    """h⁽⁴⁾_IJ = (1/16) Σ_{u,v=0..3} h_{4I−u, 4J−v} (blokta NaN varsa NaN)."""
    *on, nj, ni = h.shape
    assert nj % 4 == 0 and ni % 4 == 0
    return h.reshape(*on, nj // 4, 4, ni // 4, 4).mean(axis=(-3, -1))


def _olcek(h, d):
    """Bir ölçekte: girdi (pencere + 2 hücre/blok her yanda) → θ, H, VRM (pencere), Ω_s."""
    hx, hy, hxx, hyy, hxy = turevler(h, d)
    ic = (Ellipsis, slice(1, -1), slice(1, -1))
    th = egim(hx[ic], hy[ic])
    H = egrilik(hx[ic], hy[ic], hxx[ic], hyy[ic], hxy[ic])
    V = vrm(hx, hy)
    with np.errstate(invalid="ignore"):
        omega = np.nanmax((np.abs(hxx[ic]) + np.abs(hxy[ic]) + np.abs(hyy[ic])).reshape(*h.shape[:-2], -1), axis=-1)
    return th, V, H, omega


def ozellikler(h_genis, govde):
    """h_genis: (..., 56, 56) metre. Dönüş sözlüğü:
    theta_1, vrm_1, H_1 (..., 40, 40); theta_4, vrm_4, H_4 (..., 10, 10); R (rölyef, m); lnR; Omega_1, Omega_4;
    dem_tam (genişletilmiş DEM'de NaN yok)."""
    h = np.asarray(h_genis, dtype=np.float64)
    N = int(A.ayar("izgara.N"))
    assert h.shape[-2:] == (N + 2 * GEN, N + 2 * GEN), h.shape
    sv = float(A.ayar("cisim.sigma_v_m")[govde])
    k = GEN - 2
    h1 = h[..., k:-k, k:-k]                        # 44 × 44
    t1, v1, H1, o1 = _olcek(h1, delta_m(1))
    t4, v4, H4, o4 = _olcek(blok4(h), delta_m(4))  # 14 × 14 → 10 × 10
    W = h[..., GEN:-GEN, GEN:-GEN]                 # pencerenin kendisi 40 × 40
    duz = W.reshape(*W.shape[:-2], -1)
    with np.errstate(invalid="ignore"):
        fark = np.nanmax(duz, axis=-1) - np.nanmin(duz, axis=-1)
    R = np.where(np.isfinite(fark), np.maximum(fark, sv), np.nan)
    return {"theta_1": t1, "vrm_1": v1, "H_1": H1, "theta_4": t4, "vrm_4": v4, "H_4": H4,
            "R": R, "lnR": np.log(R), "Omega_1": o1, "Omega_4": o4,
            "dem_tam": np.isfinite(h.reshape(*h.shape[:-2], -1)).all(axis=-1)}


def yuzdelik_vektorleri(oz):
    """Altı (f, s) özelliğinin 1000 noktalı yüzdelik vektörleri: (..., 6, M)."""
    Q = [U.yuzdelik(oz[f].reshape(*oz[f].shape[:-2], -1)) for f in OZELLIKLER]
    return np.stack(Q, axis=-2)


def ceyrek(x, pay, payda):
    """F⁻¹(pay/payda) genelleştirilmiş ters, tam sayı aritmetiği (k = ⌈n·pay/payda⌉)."""
    x = np.sort(np.asarray(x, float)[np.isfinite(x)])
    n = x.size
    if n == 0:
        return np.nan
    k = -(-(n * pay) // payda)
    return x[max(k, 1) - 1]


def iqr_hedef(oz_listesi):
    """Belge 6.1: IQR_T(f_s) = F⁻¹(0,75) − F⁻¹(0,25), N(T)'deki 21 pencerenin değerlerinin birleşimi.
    oz_listesi: her pencere için ozellikler() sözlüğü. Dönüş: (6,) dizi."""
    out = np.empty(len(OZELLIKLER))
    for i, f in enumerate(OZELLIKLER):
        v = np.concatenate([np.asarray(o[f], float).ravel() for o in oz_listesi])
        out[i] = ceyrek(v, 3, 4) - ceyrek(v, 1, 4)
    return out


def d1(Q_aday, lnR_aday, Q_hedef, lnR_hedef, iqr):
    """Belge 6.1: d₁(A, T) = (Σ_{F_T} W₁(f_s^A, f_s^T) / IQR_T(f_s) + |ln R_A − ln R_T|) / (|F_T| + 1).
    Q_aday (n, 6, M), lnR_aday (n,), Q_hedef (6, M), lnR_hedef skaler, iqr (6,). F_T = {IQR > 0}."""
    Q_aday = np.asarray(Q_aday, float)
    iqr = np.asarray(iqr, float)
    FT = np.isfinite(iqr) & (iqr > 0)
    w = np.mean(np.abs(Q_aday[:, FT, :] - np.asarray(Q_hedef, float)[None, FT, :]), axis=-1)  # (n, |F_T|)
    pay = np.sum(w / iqr[None, FT], axis=1) + np.abs(np.asarray(lnR_aday, float) - float(lnR_hedef))
    return pay / (FT.sum() + 1)


def z_topo(oz):
    """Belge 7.1 z vektörünün yükseklikten gelen ilk dört bileşeni: (θ̄, θ₀,₉, VRM̄, ln R) (500 m ölçeği)."""
    th = oz["theta_1"].reshape(*oz["theta_1"].shape[:-2], -1)
    v = oz["vrm_1"].reshape(*oz["vrm_1"].shape[:-2], -1)
    t09 = np.apply_along_axis(lambda a: ceyrek(a, 9, 10), -1, th)
    with np.errstate(invalid="ignore"):
        return np.stack([np.nanmean(th, axis=-1), t09, np.nanmean(v, axis=-1), oz["lnR"]], axis=-1)
