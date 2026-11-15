# Developed with assistance from Claude (Anthropic).
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
