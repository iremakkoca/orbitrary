# Developed with assistance from Claude (Anthropic).
"""Belge 4.2–4.3: halka ızgarası, tıklama eşlemesi, haversine komşular,
Lambert eş-alanlı azimutal dönüşüm (ileri/geri), pencere hücre merkezleri.
Açılar radyan, uzunluklar km. Pencere dizileri [j, i]: j kuzeye, i doğuya artar (belge 4.1: i doğu, j kuzey)."""
import numpy as np
from scipy.spatial import cKDTree
import ayar as A


def yaricap(govde):
    return float(A.ayar("cisim.yaricap_km")[govde])


def _yuvarla(x):
    # Yarımı yukarı yuvarlar; JavaScript Math.round ile aynı (site aynı formülü kullanır).
    return np.floor(np.asarray(x, dtype=float) + 0.5)


def haversine(phi1, lam1, phi2, lam2, r):
    """Belge 4.2 gc(P1, P2)."""
    s = np.sin((phi2 - phi1) / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin((lam2 - lam1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(np.clip(s, 0.0, 1.0)))


def birim_vektor(phi, lam):
    c = np.cos(phi)
    return np.stack([c * np.cos(lam), c * np.sin(lam), np.sin(phi)], axis=-1)


class Halka:
    """Belge 4.2: M_B, Δφ, φ_i, m_i, λ_ij. Pencere kimliği = ofset[i] + j."""

    def __init__(self, govde):
        self.govde = govde
        self.r = yaricap(govde)
        D = float(A.ayar("izgara.Delta_km"))
        self.M = int(_yuvarla(np.pi * self.r / D))
        self.dphi = np.pi / self.M
        ih = np.arange(self.M)
        self.phi_halka = -np.pi / 2 + (ih + 0.5) * self.dphi
        self.m = np.maximum(1, _yuvarla(2 * np.pi * self.r * np.cos(self.phi_halka) / D)).astype(np.int64)
        self.ofset = np.concatenate([[0], np.cumsum(self.m)]).astype(np.int64)
        self.n = int(self.ofset[-1])
        self.i = np.repeat(ih, self.m)
        self.j = np.arange(self.n, dtype=np.int64) - self.ofset[self.i]
        self.phi = self.phi_halka[self.i]
        self.lam = (self.j + 0.5) * 2 * np.pi / self.m[self.i]
        self._agac = None

    def tikla(self, enlem_der, boylam_der):
        """Belge 4.2 tıklama eşlemesi (i*, j*) → pencere kimliği."""
        phi = np.radians(np.asarray(enlem_der, float))
        lam = np.radians(np.mod(np.asarray(boylam_der, float), 360.0))
        i = np.minimum(np.floor((phi + np.pi / 2) / self.dphi).astype(np.int64), self.M - 1)
        i = np.maximum(i, 0)
        j = np.minimum(np.floor(lam * self.m[i] / (2 * np.pi)).astype(np.int64), self.m[i] - 1)
        return self.ofset[i] + j

    def merkez_der(self, kimlik):
        k = np.asarray(kimlik)
        lon = np.degrees(self.lam[k])
        return np.degrees(self.phi[k]), np.where(lon > 180, lon - 360, lon)

    @property
    def agac(self):
        if self._agac is None:
            self._agac = cKDTree(birim_vektor(self.phi, self.lam))
        return self._agac

    def en_yakin(self, enlem_der, boylam_der, k=1):
        """KD-ağacıyla en yakın k merkez: (büyük çember km, kimlik)."""
        v = birim_vektor(np.radians(np.asarray(enlem_der, float)), np.radians(np.asarray(boylam_der, float)))
        d, idx = self.agac.query(v, k=k)
        return 2 * self.r * np.arcsin(np.clip(d / 2, 0, 1)), idx

    def komsular(self, enlem_der, boylam_der, n=None):
        """Belge 4.2: T'ye en yakın n pencere (T'nin kendisi hariç); uzaklık haversine ile."""
        n = int(A.ayar("izgara.n_komsu")) if n is None else int(n)
        _, idx = self.en_yakin(float(enlem_der), float(boylam_der), k=n + 1)
        p0, l0 = np.radians(float(enlem_der)), np.radians(float(boylam_der))
        d = haversine(p0, l0, self.phi[idx], self.lam[idx], self.r)
        tut = d > 1e-6
        idx, d = idx[tut][:n], d[tut][:n]
        assert len(idx) == n
        return idx, d


def lambert_ileri(phi, lam, phi0, lam0, r):
    """Belge 4.3 (Snyder [106]): (φ, λ) → (x, y), merkez (φ0, λ0)."""
    dl = lam - lam0
    den = 1 + np.sin(phi0) * np.sin(phi) + np.cos(phi0) * np.cos(phi) * np.cos(dl)
    k = np.sqrt(2 / np.maximum(den, 1e-300))
    x = r * k * np.cos(phi) * np.sin(dl)
    y = r * k * (np.cos(phi0) * np.sin(phi) - np.sin(phi0) * np.cos(phi) * np.cos(dl))
    return x, y


def lambert_geri(x, y, phi0, lam0, r):
    """Ters Lambert (Snyder [106]): (x, y) → (φ, λ ∈ [0, 2π))."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    rho = np.hypot(x, y)
    c = 2 * np.arcsin(np.clip(rho / (2 * r), -1, 1))
    sc, cc = np.sin(c), np.cos(c)
    with np.errstate(invalid="ignore", divide="ignore"):
        oran = np.where(rho > 0, y * sc * np.cos(phi0) / np.where(rho > 0, rho, 1.0), 0.0)
        phi = np.arcsin(np.clip(cc * np.sin(phi0) + oran, -1, 1))
        lam = lam0 + np.arctan2(x * sc, rho * np.cos(phi0) * cc - y * np.sin(phi0) * sc)
    phi = np.where(rho > 0, phi, phi0)
    lam = np.where(rho > 0, lam, lam0)
    return phi, np.mod(lam, 2 * np.pi)


def hucre_merkezleri(genisletme=0):
    """Belge 4.3: x_i = −L/2 + (i − ½)δ, i = 1−e … N+e (km)."""
    L = float(A.ayar("izgara.L_km"))
    d = float(A.ayar("izgara.delta_m")) / 1000.0
    N = int(A.ayar("izgara.N"))
    i = np.arange(1 - genisletme, N + genisletme + 1)
    return -L / 2 + (i - 0.5) * d


def pencere(phi0, lam0, r, genisletme=0):
    """Pencere hücre merkezlerinin (φ, λ) dizileri, biçim [j, i]."""
    c = hucre_merkezleri(genisletme)
    X, Y = np.meshgrid(c, c)
    return lambert_geri(X, Y, phi0, lam0, r)
