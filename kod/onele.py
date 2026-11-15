# Developed with assistance from Claude (Anthropic).
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
